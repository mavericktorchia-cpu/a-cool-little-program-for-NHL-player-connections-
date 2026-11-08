"""The teammate graph: players are linked if they shared an NHL roster."""

from __future__ import annotations

import unicodedata
from collections import Counter, deque
from dataclasses import dataclass


def normalize(text: str) -> str:
    """Lower-case and strip accents/punctuation so 'Stützle' matches 'stutzle'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text.lower()).split())


def pretty_season(season: int | str) -> str:
    """20232024 -> '2023-24'."""
    s = str(season)
    return f"{s[:4]}-{s[6:]}"


def pretty_stint(key: str) -> str:
    """'PIT-20052006' -> 'PIT 2005-06'."""
    team, season = key.split("-")
    return f"{team} {pretty_season(season)}"


@dataclass
class Link:
    """One step of a connection: ``a`` and ``b`` were teammates on ``stints``."""

    a: int
    b: int
    stints: list[str]


class AmbiguousName(Exception):
    def __init__(self, query: str, matches: list[int]):
        super().__init__(query)
        self.query = query
        self.matches = matches


class UnknownName(Exception):
    def __init__(self, query: str, suggestions: list[int]):
        super().__init__(query)
        self.query = query
        self.suggestions = suggestions


class TeammateGraph:
    def __init__(self, data: dict):
        self.players: dict[int, dict] = {int(pid): info for pid, info in data["players"].items()}
        self.rosters: dict[str, list[int]] = data["rosters"]
        self.built: str = data.get("built", "?")

        # player id -> list of "TEAM-SEASON" stints, in chronological order
        self.stints: dict[int, list[str]] = {pid: [] for pid in self.players}
        for key in sorted(self.rosters, key=lambda k: (k.split("-")[1], k)):
            for pid in self.rosters[key]:
                self.stints.setdefault(pid, []).append(key)

        self._by_name: dict[str, list[int]] = {}
        for pid, info in self.players.items():
            self._by_name.setdefault(normalize(info["name"]), []).append(pid)

    # ------------------------------------------------------------------ lookup
    def name(self, pid: int) -> str:
        return self.players[pid]["name"]

    def career(self, pid: int) -> str:
        """Short description used to tell same-named players apart."""
        stints = self.stints.get(pid, [])
        if not stints:
            return "no roster data"
        first = stints[0].split("-")[1][:4]
        last = stints[-1].split("-")[1][4:]
        teams = list(dict.fromkeys(s.split("-")[0] for s in stints))
        return f"{first}-{last}, {'/'.join(teams)}"

    def describe(self, pid: int) -> str:
        info = self.players[pid]
        pos = {"L": "LW", "R": "RW"}.get(info.get("pos") or "", info.get("pos") or "?")
        return f"{info['name']} ({pos}, {self.career(pid)}) [id {pid}]"

    def find(self, query: str) -> int:
        """Resolve a name (or numeric NHL id) to a single player id."""
        query = query.strip()
        if query.isdigit() and int(query) in self.players:
            return int(query)

        key = normalize(query)
        exact = self._by_name.get(key, [])
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise AmbiguousName(query, self._by_popularity(exact))

        words = key.split()
        partial = [
            pid
            for name, pids in self._by_name.items()
            if all(w in name.split() or any(part.startswith(w) for part in name.split()) for w in words)
            for pid in pids
        ]
        if len(partial) == 1:
            return partial[0]
        if partial:
            raise AmbiguousName(query, self._by_popularity(partial))

        raise UnknownName(query, self._suggest(key))

    def _by_popularity(self, pids: list[int]) -> list[int]:
        return sorted(pids, key=lambda p: -len(self.stints.get(p, [])))

    def _suggest(self, key: str, limit: int = 5) -> list[int]:
        import difflib

        names = difflib.get_close_matches(key, self._by_name.keys(), n=limit, cutoff=0.6)
        return [pid for n in names for pid in self._by_name[n]][:limit]

    # --------------------------------------------------------------- traversal
    def teammates(self, pid: int) -> dict[int, list[str]]:
        """Every teammate of ``pid`` mapped to the stints they shared."""
        result: dict[int, list[str]] = {}
        for stint in self.stints.get(pid, []):
            for other in self.rosters[stint]:
                if other != pid:
                    result.setdefault(other, []).append(stint)
        return result

    def shared_stints(self, a: int, b: int) -> list[str]:
        mine = set(self.stints.get(a, []))
        return [s for s in self.stints.get(b, []) if s in mine]

    def shortest_path(self, start: int, goal: int, avoid: set[int] | None = None) -> list[Link] | None:
        """Bidirectional breadth-first search for the fewest teammate hops."""
        if start == goal:
            return []
        avoid = (avoid or set()) - {start, goal}
        parents = {start: None}  # forward tree
        children = {goal: None}  # backward tree
        front, back = [start], [goal]
        seen_stints_front: set[str] = set()
        seen_stints_back: set[str] = set()

        def expand(frontier, tree, seen_stints):
            nxt = []
            for pid in frontier:
                for stint in self.stints.get(pid, []):
                    if stint in seen_stints:
                        continue
                    seen_stints.add(stint)
                    for other in self.rosters[stint]:
                        if other not in tree and other not in avoid:
                            tree[other] = pid
                            nxt.append(other)
            return nxt

        while front and back:
            # Always grow the smaller side: far fewer roster lookups.
            if len(front) <= len(back):
                front = expand(front, parents, seen_stints_front)
                meet = [p for p in front if p in children]
            else:
                back = expand(back, children, seen_stints_back)
                meet = [p for p in back if p in parents]
            if meet:
                return self._stitch(meet[0], parents, children)
        return None

    def _stitch(self, middle: int, parents: dict, children: dict) -> list[Link]:
        chain = [middle]
        node = parents[middle]
        while node is not None:
            chain.insert(0, node)
            node = parents[node]
        node = children[middle]
        while node is not None:
            chain.append(node)
            node = children[node]
        return [Link(a, b, self.shared_stints(a, b)) for a, b in zip(chain, chain[1:])]

    def distances(self, start: int) -> Counter:
        """How many players sit at each teammate-distance from ``start``."""
        dist = {start: 0}
        queue = deque([start])
        seen_stints: set[str] = set()
        while queue:
            pid = queue.popleft()
            for stint in self.stints.get(pid, []):
                if stint in seen_stints:
                    continue
                seen_stints.add(stint)
                for other in self.rosters[stint]:
                    if other not in dist:
                        dist[other] = dist[pid] + 1
                        queue.append(other)
        counts = Counter(dist.values())
        counts["unreachable"] = len(self.players) - len(dist)
        return counts
