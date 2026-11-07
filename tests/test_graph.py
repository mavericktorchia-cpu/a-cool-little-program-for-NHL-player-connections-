import unittest

from nhl_connections.graph import AmbiguousName, TeammateGraph, UnknownName, normalize

# A tiny fake league:  A -- B -- C -- D,  plus E isolated,  plus two "Sam Smith"s.
DATA = {
    "players": {
        "1": {"name": "Alice Able", "pos": "C"},
        "2": {"name": "Bob Böhm", "pos": "D"},
        "3": {"name": "Carl Cole", "pos": "G"},
        "4": {"name": "Dana Dunn", "pos": "L"},
        "5": {"name": "Eve Early", "pos": "R"},
        "6": {"name": "Sam Smith", "pos": "C"},
        "7": {"name": "Sam Smith", "pos": "D"},
    },
    "rosters": {
        "AAA-20002001": [1, 2, 6],
        "AAA-20012002": [1, 2],
        "BBB-20022003": [2, 3],
        "CCC-20032004": [3, 4, 7],
        "ZZZ-19501951": [5],
    },
}


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.g = TeammateGraph(DATA)

    def test_normalize_strips_accents(self):
        self.assertEqual(normalize("  Tim STÜTZLE! "), "tim stutzle")

    def test_find_exact_partial_and_accents(self):
        self.assertEqual(self.g.find("alice able"), 1)
        self.assertEqual(self.g.find("bohm"), 2)
        self.assertEqual(self.g.find("dun"), 4)
        self.assertEqual(self.g.find("3"), 3)

    def test_find_ambiguous_and_unknown(self):
        with self.assertRaises(AmbiguousName) as ctx:
            self.g.find("sam smith")
        self.assertEqual(set(ctx.exception.matches), {6, 7})
        with self.assertRaises(UnknownName):
            self.g.find("nobody here")

    def test_shortest_path(self):
        links = self.g.shortest_path(1, 4)
        self.assertEqual([(l.a, l.b) for l in links], [(1, 2), (2, 3), (3, 4)])
        self.assertEqual(links[0].stints, ["AAA-20002001", "AAA-20012002"])

    def test_path_edge_cases(self):
        self.assertEqual(self.g.shortest_path(1, 1), [])
        self.assertIsNone(self.g.shortest_path(1, 5))
        self.assertIsNone(self.g.shortest_path(1, 4, avoid={3}))

    def test_path_through_alternative(self):
        links = self.g.shortest_path(6, 7)
        self.assertEqual([(l.a, l.b) for l in links], [(6, 2), (2, 3), (3, 7)])

    def test_teammates_and_distances(self):
        self.assertEqual(self.g.teammates(2), {1: ["AAA-20002001", "AAA-20012002"], 6: ["AAA-20002001"], 3: ["BBB-20022003"]})
        d = self.g.distances(1)
        self.assertEqual((d[1], d[2], d[3], d["unreachable"]), (2, 1, 2, 1))

    def test_career(self):
        self.assertEqual(self.g.career(2), "2000-2003, AAA/BBB")


if __name__ == "__main__":
    unittest.main()
