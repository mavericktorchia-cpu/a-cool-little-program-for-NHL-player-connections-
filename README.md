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

## Quick start

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
  season, taken from the public NHL web API (`api-web.nhle.com`). Run
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
data/nhl_rosters.json.gz
tests/       # offline unit tests:  python -m unittest
```

## License

MIT
