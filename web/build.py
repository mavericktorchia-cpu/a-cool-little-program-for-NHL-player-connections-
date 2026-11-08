"""Build the website in docs/ (published by GitHub Pages).

    python web/build.py

Writes the five pages, plus the files they share:
  data.js     every roster, as one compact script (downloaded once, then cached)
  common.js   shared code  (web/site.css, the shared styles, is copied into each page)
  sw.js       offline support;  manifest.webmanifest + icons/  "add to home screen"
Shared files are linked with ?v=<content hash>, so browsers fetch them again only when they change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nhl_connections import api  # noqa: E402
from nhl_connections.data import DEFAULT_DATA_FILE, load  # noqa: E402

DOCS = ROOT / "docs"
SITE_URL = "https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/"
DESCRIPTION = (
    "Pick any two NHL players from any era and see the shortest chain of teammates "
    "between them, with the team and season behind every link."
)
# A red puck with a white center line (the same art as web/icons/).
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Ccircle cx='32' cy='32' r='30' fill='%23c8102e'/%3E"
    "%3Crect x='29' y='4' width='6' height='56' fill='%23fff'/%3E"
    "%3Ccircle cx='32' cy='32' r='10' fill='none' stroke='%23fff' stroke-width='5'/%3E%3C/svg%3E"
)
# (template, output, title, description) for each page
PAGES = [
    ("template.html", "index.html", "NHL Player Connections", DESCRIPTION),
    (
        "chain.html",
        "chain.html",
        "Build the Chain",
        "A daily NHL puzzle: link two players one teammate at a time, in as few links as you can.",
    ),
    (
        "mystery.html",
        "mystery.html",
        "Mystery Player",
        "A daily NHL guessing game: name the mystery player from as few clues as you can.",
    ),
    (
        "longer.html",
        "longer.html",
        "Who Played Longer?",
        "Two NHL players, one stat: pick who played more seasons, for more teams, or with more teammates.",
    ),
    (
        "roster.html",
        "roster.html",
        "Name the Roster",
        "A daily NHL quiz: name as many players as you can from one team's roster before the clock runs out.",
    ),
]


def head_extra(title: str, description: str, url: str) -> str:
    return f"""<meta name="description" content="{description}">
<link rel="icon" href="{FAVICON}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE_URL}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{SITE_URL}og.png">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-title" content="NHL Connections">
<meta name="theme-color" content="#eef3f7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0a131e" media="(prefers-color-scheme: dark)">
"""


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
        # [id, name, position, birth year or 0]
        "p": [
            [
                int(pid),
                data["players"][pid]["name"],
                data["players"][pid].get("pos", ""),
                int((data["players"][pid].get("born") or "0")[:4] or 0),
            ]
            for pid in ids
        ],
        "r": {key: [index[pid] for pid in members] for key, members in data["rosters"].items()},
        "t": team_names(),
    }


MANIFEST = {
    "name": "NHL Player Connections",
    "short_name": "NHL Connections",
    "description": DESCRIPTION,
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#eef3f7",
    "theme_color": "#0d1b2a",
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "shortcuts": [
        {"name": "Build the Chain", "url": "chain.html"},
        {"name": "Mystery Player", "url": "mystery.html"},
        {"name": "Who Played Longer?", "url": "longer.html"},
        {"name": "Name the Roster", "url": "roster.html"},
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_FILE)
    args = parser.parse_args()
    web = ROOT / "web"
    DOCS.mkdir(parents=True, exist_ok=True)

    # Shared files. The version is a hash of their contents.
    data_js = "window.NHL_DATA=" + json.dumps(compact(load(args.data)), separators=(",", ":"), ensure_ascii=False) + ";\n"
    common_js = (web / "common.js").read_text(encoding="utf-8")
    site_css = (web / "site.css").read_text(encoding="utf-8")
    # Any change to the data, shared code or a page gives a new version (and fresh offline copies).
    templates = "".join((web / t).read_text(encoding="utf-8") for t, _, _, _ in PAGES)
    templates += "".join(f.name for f in sorted((web / "fonts").glob("*.woff2")))
    version = hashlib.sha256((data_js + common_js + site_css + templates + (web / "sw.js").read_text(encoding="utf-8")).encode("utf-8")).hexdigest()[:10]
    for name, text in (("data.js", data_js), ("common.js", common_js)):
        (DOCS / name).write_text(text, encoding="utf-8")
        print(f"Wrote {DOCS / name} ({len(text.encode('utf-8')) / 1024:.0f} KB)")

    fonts = DOCS / "fonts"
    fonts.mkdir(exist_ok=True)
    font_files = sorted((web / "fonts").glob("*.woff2"))
    for font in font_files:
        shutil.copyfile(font, fonts / font.name)

    icons = DOCS / "icons"
    icons.mkdir(exist_ok=True)
    for icon in sorted((web / "icons").glob("*.png")):
        shutil.copyfile(icon, icons / icon.name)
    (DOCS / "manifest.webmanifest").write_text(json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")

    # Shared styles go straight into each page (saves a request before first paint).
    shared_head = "<style>\n" + site_css + "</style>\n"
    shared_scripts = f'<script src="data.js?v={version}"></script>\n<script src="common.js?v={version}"></script>\n'
    for template, output, title, description in PAGES:
        body = (web / template).read_text(encoding="utf-8")
        url = SITE_URL if output == "index.html" else SITE_URL + output
        # Title, fonts and styles belong in <head>; the rest of the template is the body.
        split = body.index('<div class="wrap">')
        head, content = body[:split], body[split:]
        style = head.index("<style>")
        head = head[:style] + shared_head + head[style:]  # page styles come after the shared ones
        # Preload the two faces seen first, so they're ready for the first paint.
        head = (
            '<link rel="preload" href="fonts/big-shoulders-display.woff2" as="font" type="font/woff2" crossorigin>\n'
            '<link rel="preload" href="fonts/barlow-400.woff2" as="font" type="font/woff2" crossorigin>\n'
        ) + head
        script = content.index("<script>")
        content = content[:script] + shared_scripts + content[script:]
        # Show the game area only once the page's own script has run (see html.loading in site.css).
        content = content.rstrip() + '\n<script>document.documentElement.classList.remove("loading");</script>\n'
        loading = (
            '<script>document.documentElement.classList.add("loading");'
            'setTimeout(function () { document.documentElement.classList.remove("loading"); }, 8000);</script>\n'
        )
        page = (
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' + loading +
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head_extra(title, description, url) + head + "</head>\n<body>\n" + content + "\n</body>\n</html>\n"
        )
        (DOCS / output).write_text(page, encoding="utf-8")
        print(f"Wrote {DOCS / output} ({len(page) / 1024:.0f} KB)")

    # Search engines: a sitemap of the five pages, and robots.txt pointing at it.
    urls = "".join(f"  <url><loc>{SITE_URL if out == 'index.html' else SITE_URL + out}</loc></url>\n" for _, out, _, _ in PAGES)
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n",
        encoding="utf-8",
    )
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")

    # A friendly "page not found". GitHub Pages serves it for any missing path, so links are absolute.
    links = "".join(f'<li><a href="{SITE_URL if out == "index.html" else SITE_URL + out}">{title}</a></li>' for _, out, title, _ in PAGES)
    (DOCS / "404.html").write_text(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<title>Offside: page not found</title>\n<link rel="icon" href="{FAVICON}">\n<meta name="robots" content="noindex">\n'
        "<style>\n" + site_css + ".lost ul { padding-left: 20px; display: grid; gap: 6px; font-size: 18px; } .lost a { color: var(--blue); }</style>\n"
        "</head>\n<body>\n<div class=\"wrap lost\">\n<header><div class=\"eyebrow\">Error 404</div>"
        "<h1>Offside. <span>No page here.</span></h1>"
        "<p class=\"lede\">That link doesn't go anywhere on this site. Try one of these instead:</p></header>\n"
        f"<ul>{links}</ul>\n</div>\n</body>\n</html>\n",
        encoding="utf-8",
    )

    # Offline support: cache every page and shared file under this version.
    precache = ["./"] + [out for _, out, _, _ in PAGES] + [
        f"common.js?v={version}", f"data.js?v={version}",
        "manifest.webmanifest", "icons/icon-192.png", "og.png",
    ] + [f"fonts/{f.name}" for f in font_files]
    sw = (web / "sw.js").read_text(encoding="utf-8")
    sw = sw.replace("__VERSION__", version).replace("__PRECACHE__", json.dumps(precache))
    (DOCS / "sw.js").write_text(sw, encoding="utf-8")
    print(f"Wrote {DOCS / 'sw.js'} (version {version})")


if __name__ == "__main__":
    main()
