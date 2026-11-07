"""Command-line interface: `python -m nhl_connections <command> ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import data as datafile
from .graph import AmbiguousName, TeammateGraph, UnknownName, pretty_stint


def _resolve(graph: TeammateGraph, query: str) -> int:
    try:
        return graph.find(query)
    except AmbiguousName as exc:
        lines = [f'"{exc.query}" matches more than one player. Use the id or a fuller name:']
        lines += [f"  {graph.describe(pid)}" for pid in exc.matches[:10]]
        if len(exc.matches) > 10:
            lines.append(f"  ...and {len(exc.matches) - 10} more")
        sys.exit("\n".join(lines))
    except UnknownName as exc:
        msg = f'No player found matching "{exc.query}".'
        if exc.suggestions:
            msg += " Did you mean:\n" + "\n".join(f"  {graph.describe(p)}" for p in exc.suggestions)
        sys.exit(msg)


def _stints(stints: list[str], limit: int = 3) -> str:
    shown = ", ".join(pretty_stint(s) for s in stints[:limit])
    if len(stints) > limit:
        shown += f" (+{len(stints) - limit} more)"
    return shown


def cmd_path(graph: TeammateGraph, args) -> None:
    start, goal = _resolve(graph, args.player_a), _resolve(graph, args.player_b)
    avoid = {_resolve(graph, name) for name in args.avoid or []}
    links = graph.shortest_path(start, goal, avoid)
    a, b = graph.name(start), graph.name(goal)
    if links is None:
        print(f"{a} and {b} are not connected through NHL teammates.")
        return
    if not links:
        print(f"That's the same player: {graph.describe(start)}")
        return

    hops = len(links)
    print(f"{a} -> {b}: {hops} degree{'s' if hops != 1 else ''} of separation\n")
    print(f"  {graph.name(links[0].a)}")
    for link in links:
        print(f"    | teammates on {_stints(link.stints)}")
        print(f"  {graph.name(link.b)}")


def cmd_teammates(graph: TeammateGraph, args) -> None:
    pid = _resolve(graph, args.player)
    mates = graph.teammates(pid)
    print(f"{graph.describe(pid)}")
    print(f"{len(mates)} different NHL teammates\n")
    ranked = sorted(mates.items(), key=lambda kv: (-len(kv[1]), graph.name(kv[0])))
    for other, stints in ranked[: args.limit]:
        print(f"  {graph.name(other):<28} {len(stints):>2} season(s): {_stints(stints)}")
    if len(ranked) > args.limit:
        print(f"\n  ...{len(ranked) - args.limit} more (use --limit to see them)")


def cmd_info(graph: TeammateGraph, args) -> None:
    pid = _resolve(graph, args.player)
    print(graph.describe(pid))
    print("Roster history: " + ", ".join(pretty_stint(s) for s in graph.stints.get(pid, [])))
    counts = graph.distances(pid)
    print("\nHow far every NHL player is from them (in teammate hops):")
    for hops in sorted(k for k in counts if k != "unreachable"):
        if hops:
            print(f"  {hops} hop{'s' if hops != 1 else ' '}: {counts[hops]:>6,} players")
    if counts["unreachable"]:
        print(f"  unreachable: {counts['unreachable']:,}")


def cmd_search(graph: TeammateGraph, args) -> None:
    try:
        print(graph.describe(graph.find(args.name)))
    except AmbiguousName as exc:
        for pid in exc.matches[: args.limit]:
            print(graph.describe(pid))
    except UnknownName as exc:
        print(f'No match for "{exc.query}".')
        for pid in exc.suggestions:
            print(f"  maybe: {graph.describe(pid)}")


def cmd_update(args) -> None:
    datafile.download(args.data, workers=args.workers, first_season=args.since)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nhl-connections",
        description="Find how any two NHL players are connected through teammates.",
    )
    parser.add_argument("--data", type=Path, default=datafile.DEFAULT_DATA_FILE, help="roster data file")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("path", help="shortest teammate chain between two players")
    p.add_argument("player_a")
    p.add_argument("player_b")
    p.add_argument("--avoid", action="append", metavar="PLAYER", help="find a path that skips this player")

    p = sub.add_parser("teammates", help="list everyone a player ever shared a roster with")
    p.add_argument("player")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("info", help="a player's roster history and how connected they are")
    p.add_argument("player")

    p = sub.add_parser("search", help="look up players by name")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=15)

    p = sub.add_parser("update", help="re-download all rosters from the NHL API")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--since", type=int, metavar="SEASON", help="only seasons from e.g. 20002001 on")

    args = parser.parse_args(argv)
    if args.command == "update":
        cmd_update(args)
        return

    graph = TeammateGraph(datafile.load(args.data))
    {"path": cmd_path, "teammates": cmd_teammates, "info": cmd_info, "search": cmd_search}[args.command](
        graph, args
    )


if __name__ == "__main__":
    main()
