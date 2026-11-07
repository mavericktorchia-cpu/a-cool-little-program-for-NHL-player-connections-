"""Build the web version: one self-contained HTML page with the roster data inside.

    python web/build.py                 # writes docs/index.html (ready for GitHub Pages)
    python web/build.py --fragment X    # also writes a body-only copy to X
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nhl_connections import api  # noqa: E402
from nhl_connections.data import DEFAULT_DATA_FILE, load  # noqa: E402

TEMPLATE = ROOT / "web" / "template.html"
OUTPUT = ROOT / "docs" / "index.html"


def team_names() -> dict[str, str]:
    """Tri-code -> full team name, for hover labels. Optional: skipped when offline."""
    try:
        teams = api.get_json(f"{api.STATS_API}/team")["data"]
    except Exception as exc:  # noqa: BLE001
        print(f"(skipping team names: {exc})")
        return {}
    names: dict[str, str] = {}
    for t in sorted(teams, key=lambda t: t["id"]):  # later ids win, e.g. UTA -> Utah Mammoth
        if t.get("triCode"):
            names[t["triCode"]] = t["fullName"]
    return names


def compact(data: dict) -> dict:
    """Shrink the data: players become a list, and rosters point into it by index."""
    ids = sorted(data["players"], key=int)
    index = {int(pid): n for n, pid in enumerate(ids)}
    return {
        "built": data.get("built", ""),
        "p": [[int(pid), data["players"][pid]["name"], data["players"][pid].get("pos", "")] for pid in ids],
        "r": {key: [index[pid] for pid in members] for key, members in data["rosters"].items()},
        "t": team_names(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--fragment", type=Path, help="also write the page without the <html> wrapper here")
    args = parser.parse_args()

    payload = json.dumps(compact(load(args.data)), separators=(",", ":"), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # never close the <script> tag early
    body = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload, 1)

    page = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(page) / 1024:.0f} KB)")
    if args.fragment:
        args.fragment.parent.mkdir(parents=True, exist_ok=True)
        args.fragment.write_text(body, encoding="utf-8")
        print(f"Wrote {args.fragment}")


if __name__ == "__main__":
    main()
