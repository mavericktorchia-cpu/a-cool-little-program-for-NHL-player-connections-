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


def team_codes() -> list[str]:
    """Every NHL team tri-code, past and present (e.g. MTL, HFD, QUE, UTA)."""
    data = get_json(f"{STATS_API}/team")["data"]
    skip = {"NHL", "TBD"}  # placeholder entries, not real clubs
    return sorted({t["triCode"] for t in data if t.get("triCode") and t["triCode"] not in skip})


def team_seasons(team: str) -> list[int]:
    """Seasons (like 20232024) for which the API has a roster for ``team``."""
    try:
        return list(get_json(f"{WEB_API}/roster-season/{team}") or [])
    except NotFound:
        return []


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
