"""Tiny client for the public NHL web API (no API key needed).

Only the Python standard library is used so the program runs anywhere.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

WEB_API = "https://api-web.nhle.com/v1"
STATS_API = "https://api.nhle.com/stats/rest/en"

USER_AGENT = "nhl-player-connections/1.0 (+https://github.com/mavericktorchia-cpu)"


class NotFound(Exception):
    """Raised when the API answers 404 (e.g. a team with no roster that season)."""


def get_json(url: str, retries: int = 4, timeout: float = 30.0):
    """GET ``url`` and decode JSON, retrying transient failures with backoff."""
    delay = 1.0
    last_error: Exception | None = None
    for _ in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(url) from exc
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"Giving up on {url}: {last_error}")


SKIP_CODES = {"NHL", "TBD"}  # placeholder entries in the team list, not real clubs


def teams() -> list[dict]:
    """Every NHL team record, past and present: id, triCode, fullName, franchiseId."""
    return [t for t in get_json(f"{STATS_API}/team")["data"] if t.get("triCode") and t["triCode"] not in SKIP_CODES]


def team_codes() -> list[str]:
    """Every NHL team tri-code, past and present (e.g. MTL, HFD, QUE, UTA)."""
    return sorted({t["triCode"] for t in teams()})


def season_team_names(season: int) -> dict[int, str]:
    """{team id: full name} for the teams that played the regular season ``season``."""
    try:
        data = get_json(f"{STATS_API}/team/summary?cayenneExp=seasonId={season}%20and%20gameTypeId=2&limit=100")
    except NotFound:
        return {}
    return {t["teamId"]: t["teamFullName"] for t in data.get("data") or [] if t.get("teamId") and t.get("teamFullName")}


def team_seasons(team: str) -> list[int]:
    """Seasons (like 20232024) that ``team`` played.

    The roster endpoint's season list skips some seasons (Utah's 2024-25, for one), so the
    season-stats list is merged in.
    """
    seasons: set[int] = set()
    try:
        seasons.update(get_json(f"{WEB_API}/roster-season/{team}") or [])
    except NotFound:
        pass
    try:
        seasons.update(entry["season"] for entry in get_json(f"{WEB_API}/club-stats-season/{team}") or [])
    except NotFound:
        pass
    return sorted(seasons)


def birth_date(player_id: int) -> str:
    """A player's birth date (YYYY-MM-DD) from their profile, or "" if unknown."""
    try:
        return get_json(f"{WEB_API}/player/{player_id}/landing").get("birthDate") or ""
    except NotFound:
        return ""


def roster(team: str, season: int) -> list[dict]:
    """All players on ``team``'s roster for ``season`` (forwards, D and goalies)."""
    try:
        data = get_json(f"{WEB_API}/roster/{team}/{season}")
    except NotFound:
        return []
    players = []
    for group in ("forwards", "defensemen", "goalies"):
        players.extend(data.get(group) or [])
    return players


# From 2023-24 on, the roster endpoint only lists a team's end-of-season roster (about 21
# players instead of 35+), and it returns nothing for Arizona's final season. The season stats
# endpoint lists everyone who played, so for those seasons we combine the two.
STATS_FROM_SEASON = 20232024


def club_stats_players(team: str, season: int) -> list[dict]:
    """Everyone who played a regular-season game for ``team`` in ``season``, shaped like roster entries."""
    try:
        data = get_json(f"{WEB_API}/club-stats/{team}/{season}/2")
    except NotFound:
        return []
    players = []
    for p in (data.get("skaters") or []) + (data.get("goalies") or []):
        players.append(
            {
                "id": p["playerId"],
                "firstName": p.get("firstName") or {},
                "lastName": p.get("lastName") or {},
                "positionCode": p.get("positionCode") or ("G" if p in (data.get("goalies") or []) else ""),
            }
        )
    return players


def season_players(team: str, season: int) -> list[dict]:
    """Roster for ``team`` in ``season``, topped up with everyone who played when the roster is incomplete."""
    players = roster(team, season)
    if season >= STATS_FROM_SEASON:
        known = {p["id"] for p in players}
        players += [p for p in club_stats_players(team, season) if p["id"] not in known]
    return players
