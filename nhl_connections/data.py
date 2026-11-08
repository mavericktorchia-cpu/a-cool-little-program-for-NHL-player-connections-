"""Download every NHL roster and save it as one compact, gzipped JSON file.

File layout::

    {
      "built": "2026-11-07",
      "players": {"8471675": {"name": "Sidney Crosby", "pos": "C", "born": "1987-08-07"}, ...},
      "rosters": {"PIT-20052006": [8471675, ...], ...}
    }
"""

from __future__ import annotations

import datetime as _dt
import gzip
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import api

DEFAULT_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "nhl_rosters.json.gz"


def _name(player: dict) -> str:
    first = (player.get("firstName") or {}).get("default", "")
    last = (player.get("lastName") or {}).get("default", "")
    return f"{first} {last}".strip()


def download(
    path: Path = DEFAULT_DATA_FILE,
    workers: int = 8,
    first_season: int | None = None,
    log=print,
) -> Path:
    """Fetch every roster from the NHL API and write them to ``path``."""
    teams = api.team_codes()
    log(f"Found {len(teams)} franchises/team codes. Looking up their seasons...")

    jobs: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for team, seasons in zip(teams, pool.map(api.team_seasons, teams)):
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

    payload = {
        "built": _dt.date.today().isoformat(),
        "players": dict(sorted(players.items(), key=lambda kv: int(kv[0]))),
        "rosters": dict(sorted(rosters.items())),
    }
    if path.exists():
        old = load(path)
        if old.get("players") == payload["players"] and old.get("rosters") == payload["rosters"]:
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
