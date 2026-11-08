"""Download every NHL roster and save it as one compact, gzipped JSON file.

File layout::

    {
      "built": "2026-11-07",
      "players": {"8471675": {"name": "Sidney Crosby", "pos": "C", "born": "1987-08-07"}, ...},
      "rosters": {"PIT-20052006": [8471675, ...], ...},
      "teams": {"ANA": "Anaheim Ducks", ...},                    # each code's current name
      "team_names": {"ANA-19931994": "Mighty Ducks of Anaheim"}  # seasons with a different name
    }
"""

from __future__ import annotations

import datetime as _dt
import gzip
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import api

# Shipped inside the package, so `pip install` brings the data along.
DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "rosters.json.gz"

# Names the NHL API doesn't keep apart from the current ones.
HISTORICAL_NAMES = [
    # (team code, first season, last season, name)
    ("ANA", 19931994, 20052006, "Mighty Ducks of Anaheim"),  # renamed Anaheim Ducks for 2006-07
    ("CHI", 19261927, 19851986, "Chicago Black Hawks"),  # spelled as one word from 1986-87
]

# A finished season may lose at most this share of its players between updates.
MAX_SHRINK = 0.10


class DataShrank(Exception):
    """A new download has less history than the saved file. Nothing was written."""


def _name(player: dict) -> str:
    first = (player.get("firstName") or {}).get("default", "")
    last = (player.get("lastName") or {}).get("default", "")
    return f"{first} {last}".strip()


def _clean_team_name(name: str) -> str:
    # The API labels some old clubs with a year, e.g. "Winnipeg Jets (1979)".
    return re.sub(r"\s*\(\d{4}\)$", "", name).strip()


def team_names(roster_keys: set[str], workers: int = 8) -> tuple[dict[str, str], dict[str, str]]:
    """Current name of every team code, and the names that differ in particular seasons.

    ``roster_keys`` are the "CODE-SEASON" rosters we have. Returns ({code: name}, {"CODE-SEASON": name}).
    """
    seasons = sorted({int(k.split("-")[1]) for k in roster_keys})
    records = api.teams()
    code_of = {t["id"]: t["triCode"] for t in records}
    current: dict[str, str] = {}
    for t in sorted(records, key=lambda t: t["id"]):  # a newer record for the same code wins
        current[t["triCode"]] = _clean_team_name(t["fullName"])

    by_season: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for season, names in zip(seasons, pool.map(api.season_team_names, seasons)):
            for team_id, name in names.items():
                code = code_of.get(team_id)
                if code:
                    by_season[f"{code}-{season}"] = _clean_team_name(name)
    for code, first, last, name in HISTORICAL_NAMES:
        for season in seasons:
            if first <= season <= last:
                by_season[f"{code}-{season}"] = name
    # Keep only rosters we have, and only where the name differs from the code's current name.
    exceptions = {
        k: v for k, v in sorted(by_season.items()) if k in roster_keys and v != current.get(k.split("-")[0])
    }
    return current, exceptions


def check_history(old: dict, new: dict, first_season: int | None = None) -> list[str]:
    """Problems that would make ``new`` lose history that ``old`` has. Empty means fine.

    Every finished season (all but the newest one in ``old``) must still be there, and none may
    lose more than MAX_SHRINK of its players.
    """
    old_rosters, new_rosters = old.get("rosters", {}), new.get("rosters", {})
    if not old_rosters:
        return []
    newest = max(int(k.split("-")[1]) for k in old_rosters)
    problems = []
    for key, members in sorted(old_rosters.items()):
        season = int(key.split("-")[1])
        if season >= newest or (first_season is not None and season < first_season):
            continue
        now = new_rosters.get(key)
        if now is None:
            problems.append(f"{key} is missing ({len(members)} players before)")
        elif len(now) < len(members) * (1 - MAX_SHRINK):
            problems.append(f"{key} dropped from {len(members)} to {len(now)} players")
    return problems


def download(
    path: Path = DEFAULT_DATA_FILE,
    workers: int = 8,
    first_season: int | None = None,
    allow_shrink: bool = False,
    log=print,
) -> Path:
    """Fetch every roster from the NHL API and write them to ``path``.

    Raises DataShrank (and writes nothing) if finished seasons would lose players, unless
    ``allow_shrink`` is set.
    """
    codes = api.team_codes()
    log(f"Found {len(codes)} franchises/team codes. Looking up their seasons...")

    jobs: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for team, seasons in zip(codes, pool.map(api.team_seasons, codes)):
            for season in seasons:
                if first_season is None or season >= first_season:
                    jobs.append((team, season))
    log(f"Downloading {len(jobs)} team-season rosters with {workers} threads...")

    results: dict[tuple[str, int], list[dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(api.season_players, team, season): (team, season) for team, season in jobs}
        for done, future in enumerate(as_completed(futures), 1):
            results[futures[future]] = future.result()
            if done % 100 == 0 or done == len(jobs):
                log(f"  {done}/{len(jobs)} rosters")

    # Newest seasons first, so each player's name and position come from their
    # latest season no matter which download happened to finish first.
    players: dict[str, dict] = {}
    rosters: dict[str, list[int]] = {}
    for (team, season), members in sorted(results.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
        if not members:
            continue
        rosters[f"{team}-{season}"] = sorted({p["id"] for p in members})
        for p in members:
            info = players.setdefault(
                str(p["id"]),
                {"name": _name(p), "pos": p.get("positionCode", ""), "born": p.get("birthDate", "")},
            )
            # Stats-only entries have no birth date; fill it in from any roster entry that does.
            if not info["born"] and p.get("birthDate"):
                info["born"] = p["birthDate"]

    # Players who only appear in season stats have no birth date yet; look those few up.
    missing = [pid for pid, info in players.items() if not info["born"]]
    if missing:
        log(f"Looking up birth dates for {len(missing)} players...")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for pid, born in zip(missing, pool.map(lambda pid: api.birth_date(int(pid)), missing)):
                players[pid]["born"] = born

    log("Looking up team names...")
    current_names, season_names = team_names(set(rosters), workers)

    payload = {
        "built": _dt.date.today().isoformat(),
        "players": dict(sorted(players.items(), key=lambda kv: int(kv[0]))),
        "rosters": dict(sorted(rosters.items())),
        "teams": dict(sorted(current_names.items())),
        "team_names": season_names,
    }
    if path.exists():
        old = load(path)
        problems = check_history(old, payload, first_season)
        if problems and not allow_shrink:
            shown = "\n  ".join(problems[:20]) + (f"\n  ...and {len(problems) - 20} more" if len(problems) > 20 else "")
            raise DataShrank(
                f"The new download has less history than {path}, so nothing was saved:\n  {shown}\n"
                "This usually means the NHL API returned incomplete data. Try again later, or run "
                "`python -m nhl_connections update --allow-shrink` if the change is expected."
            )
        if all(old.get(k) == payload[k] for k in ("players", "rosters", "teams", "team_names")):
            log(f"No roster changes since {old.get('built')}; left {path} as it was.")
            return path
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    # mtime=0 keeps the file byte-for-byte identical for identical data.
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
        fh.write(text.encode("utf-8"))
    log(f"Saved {len(rosters)} rosters and {len(players)} players to {path}")
    return path


def load(path: Path = DEFAULT_DATA_FILE) -> dict:
    """Load a data file written by :func:`download`."""
    if not path.exists():
        sys.exit(
            f"No roster data found at {path}.\n"
            "Run `python -m nhl_connections update` first to download it."
        )
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)
