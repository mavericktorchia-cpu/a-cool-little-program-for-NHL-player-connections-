# 🏒 NHL Player Connections

*Six degrees of separation, for hockey.*

Pick any two NHL players from any era and this little program finds the
shortest chain of **teammates** linking them, showing the team and season
behind every link.

```
$ python -m nhl_connections path "Connor Bedard" "Maurice Richard"
Connor Bedard -> Maurice Richard: 6 degrees of separation

  Connor Bedard
    | teammates on CHI 2023-24, CHI 2024-25
  Nick Foligno
    | teammates on OTT 2007-08, OTT 2008-09
  Luke Richardson
    | teammates on TOR 1987-88
  Mike Allison
    | teammates on NYR 1980-81, NYR 1981-82
  Carol Vadnais
    | teammates on MTL 1966-67, MTL 1967-68
  Jean Beliveau
    | teammates on MTL 1950-51, MTL 1952-53, MTL 1953-54 (+6 more)
  Maurice Richard
```

It comes with every NHL roster from 1917-18 to today (about 1,800 team-seasons
and 8,700+ players) in a 250 KB file, so it runs offline and answers instantly.

## Web version

`docs/index.html` is the same thing as a web page: type two names, pick from
the suggestions, and see the chain. Click **Route around** on any player in
the middle to find a different chain that skips them, or hit **Random pair**.
It's one self-contained file (all the data is inside), so you can just open it
in a browser.

**Live site:** https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/

The GitHub Action in `.github/workflows/pages.yml` publishes the site:

* every push to `main` runs the tests, rebuilds the page and deploys it;
* every Monday it also re-downloads all NHL rosters, commits the new data if
  anything changed, and redeploys. You can trigger this from the *Actions* tab
  too (*Update data and deploy site* → *Run workflow*).

One-time setup: in *Settings → Pages*, set *Source* to **GitHub Actions**.

To rebuild by hand after `update`: `python web/build.py`. The link-preview
image `docs/og.png` comes from `web/og-card.html` (`node web/make-og.js`).

## Game: Build the Chain

`docs/chain.html` is a puzzle built on the same data. You get two players and
link them yourself, one teammate at a time. Each player you add must have
shared a roster with the one before. Try to match **par**, the shortest
possible chain.

* **Daily puzzle:** everyone gets the same pair each day, with a puzzle number,
  a saved streak, and a result you can copy and share.
* **Practice:** endless random chains at Easy (par 2), Medium (par 3) or Hard
  (par 4–6).
* Wrong names count as misses, **Undo** is free, and **Hint** first names a
  team and season to look at, then the next player's initials.

Play it at
https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/chain.html

## Game: Mystery Player

`docs/mystery.html` asks you to name a player from a scouting report of seven
clues: position and era, career length, birth year, a famous teammate, first
and last team, every team in order, then initials. You start with one clue.
Each wrong guess unlocks the next one and shows what your guess has in common
with the mystery player (position, debut decade, teams, career length, and
whether they were teammates). Solve it with as few clues as you can.

There's a daily player (the same for everyone, with a streak and shareable
result) and a practice mode with **Stars** or **Deep cuts**.

Play it at
https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/mystery.html

## Game: Who Played Longer?

`docs/longer.html` puts two players side by side and asks who wins a stat:
more **seasons** on NHL rosters, more **teams**, or more **different
teammates**. Tap a player to see both numbers.

* **Daily 10:** ten rounds, the same for everyone each day (4 seasons, 3 teams,
  3 teammates), with a shareable score. Daily rounds use retired players only,
  so the answers never change mid-day.
* **Endless:** the winner stays on and a new challenger steps in. The gap gets
  smaller as your streak grows. Your best streak is saved for each stat.

Play it at
https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/longer.html

## Game: Name the Roster

`docs/roster.html` gives you a team and a season, like the 1993–94 Boston
Bruins, and a clock. Type as many players from that roster as you can. A last
name is enough, and correct names fill in on a depth chart as soon as you
finish typing them. A wrong name tells you if that player was on the team in a
different season. When time runs out, everyone you missed is filled in.

* **Daily:** the same team-season for everyone (1980–81 to 2023–24), 3 minutes,
  with a shareable score.
* **Practice:** pick the era, the team and the clock (2, 3 or 5 minutes, or none).

Play it at
https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/roster.html

## Quick start (command line)

You only need Python 3.9 or newer. There's nothing to install.

```bash
git clone https://github.com/mavericktorchia-cpu/a-cool-little-program-for-NHL-player-connections-.git
cd a-cool-little-program-for-NHL-player-connections-
python -m nhl_connections path "Sidney Crosby" "Wayne Gretzky"
```

Optionally, `pip install .` adds an `nhl-connections` command you can run from anywhere.

## Commands

| Command | What it does |
| --- | --- |
| `path A B` | Shortest teammate chain between two players |
| `path A B --avoid C` | Same, but the chain may not go through player C (repeatable) |
| `teammates A [--limit N]` | Everyone A ever shared a roster with, most seasons together first |
| `info A` | A's roster history, plus how many players are 1, 2, 3... hops away |
| `search NAME` | Look up players (handy for telling namesakes apart) |
| `update` | Re-download every roster from the NHL API (about 1 minute) |

### Finding players

* Capitals and accents don't matter: `stutzle` finds Tim Stützle.
* Last names and partial names work: `bedard`, `mcdav`, `sid crosby`.
* Typos get suggestions: `mcdavd` → *Did you mean Connor McDavid?*
* When two players share a name (there are two Sebastian Ahos), you'll see a
  list with positions, years and teams. Use the number in brackets instead:

```
$ python -m nhl_connections path 8478427 ovechkin
Sebastian Aho -> Alex Ovechkin: 2 degrees of separation
...
```

### How connected is a player?

```
$ python -m nhl_connections info "Auston Matthews"
...
How far every NHL player is from them (in teammate hops):
  1 hop :    178 players
  2 hops:  3,273 players
  3 hops:  2,782 players
  ...
```

## How it works

* **Data:** `data/nhl_rosters.json.gz` holds every team's roster for every
  season, taken from the public NHL web API (`api-web.nhle.com`). From 2023-24
  on, the API's roster lists only show end-of-season rosters, so those seasons
  also add everyone who played a game, from the season stats. Run
  `python -m nhl_connections update` whenever you want the latest rosters.
* **Graph:** two players are connected if they appear on the same team's
  roster in the same season.
* **Search:** a bidirectional breadth-first search grows outward from both
  players at once and stops where the two sides meet. That always gives the
  fewest possible hops, and it takes milliseconds.

> **Note:** "teammates" means *on the same season roster*. Two players traded
> in opposite directions mid-season can count as teammates even if they never
> dressed for the same game.

## Project layout

```
nhl_connections/
  api.py     # minimal NHL API client (standard library only)
  data.py    # downloads and saves / loads the roster file
  graph.py   # teammate graph, name lookup, shortest path search
  cli.py     # command-line interface
web/       # page templates (template.html, chain.html, mystery.html, longer.html, roster.html) + build script
docs/      # built pages (GitHub Pages)
data/nhl_rosters.json.gz
tests/       # offline unit tests:  python -m unittest
```

## License

MIT. Fan project, not affiliated with or endorsed by the National Hockey League.
Player and roster data come from the NHL's public web API.
