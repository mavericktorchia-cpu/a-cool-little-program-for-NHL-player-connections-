"""Tests for the roster downloader, with the NHL API replaced by a small fake league."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nhl_connections import data


def player(pid, first, last, pos="C", born="1990-01-01"):
    entry = {"id": pid, "firstName": {"default": first}, "lastName": {"default": last}, "positionCode": pos}
    if born:
        entry["birthDate"] = born
    return entry


class FakeNHL:
    """Two clubs over three seasons. Tests change ``rosters`` to simulate API trouble."""

    def __init__(self):
        self.rosters = {
            ("AAA", 20202021): [player(1, "Ann", "Able", "D"), player(2, "Bo", "Burke")],
            ("AAA", 20212022): [player(1, "Ann", "Able", "C"), player(3, "Cy", "Cole", born="")],
            ("BBB", 20212022): [player(2, "Bo", "Burke"), player(4, "Di", "Dunn")],
            ("BBB", 20222023): [player(4, "Di", "Dunn"), player(5, "Ed", "Erl")],
        }

    def patch(self):
        return mock.patch.multiple(
            data.api,
            team_codes=lambda: ["AAA", "BBB"],
            team_seasons=lambda team: sorted(s for t, s in self.rosters if t == team),
            season_players=lambda team, season: list(self.rosters.get((team, season), [])),
            birth_date=lambda pid: "1999-09-09",
            teams=lambda: [
                {"id": 1, "triCode": "AAA", "fullName": "Alpha Aces (1917)"},
                {"id": 2, "triCode": "BBB", "fullName": "Old Bravo"},
                {"id": 3, "triCode": "BBB", "fullName": "Bravo Bears"},
            ],
            season_team_names=lambda season: {1: "Alpha Aces (1917)", 3: "Bravo Bears" if season > 20212022 else "Bravo Cubs"},
        )


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "rosters.json.gz"
        self.nhl = FakeNHL()

    def tearDown(self):
        self.dir.cleanup()

    def download(self, **kwargs):
        with self.nhl.patch():
            return data.download(self.path, workers=2, log=lambda *a: None, **kwargs)

    def test_builds_players_rosters_and_team_names(self):
        self.download()
        saved = read(self.path)
        self.assertEqual(saved["rosters"]["AAA-20202021"], [1, 2])
        # Name and position come from the player's latest season.
        self.assertEqual(saved["players"]["1"], {"name": "Ann Able", "pos": "C", "born": "1990-01-01"})
        # A player without a birth date on any roster is looked up.
        self.assertEqual(saved["players"]["3"]["born"], "1999-09-09")
        # Current names: the newest record per code wins, and "(1917)" labels are removed.
        self.assertEqual(saved["teams"], {"AAA": "Alpha Aces", "BBB": "Bravo Bears"})
        # Only seasons whose name differs from the current one are listed.
        self.assertEqual(saved["team_names"], {"BBB-20212022": "Bravo Cubs"})

    def test_unchanged_download_leaves_the_file_alone(self):
        self.download()
        before = self.path.read_bytes()
        stamp = self.path.stat().st_mtime_ns
        self.download()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, stamp)

    def test_refuses_to_lose_finished_seasons(self):
        self.download()
        before = self.path.read_bytes()
        del self.nhl.rosters[("AAA", 20202021)]  # the API "forgets" a finished season
        with self.assertRaises(data.DataShrank) as ctx:
            self.download()
        self.assertIn("AAA-20202021 is missing", str(ctx.exception))
        self.assertEqual(self.path.read_bytes(), before)

    def test_refuses_big_drops_but_allows_the_newest_season_to_change(self):
        self.download()
        # The newest season may shrink (call-ups get sent back down)...
        self.nhl.rosters[("BBB", 20222023)] = [player(4, "Di", "Dunn")]
        self.download()
        # ...but a finished season may not lose half its players.
        self.nhl.rosters[("AAA", 20212022)] = [player(1, "Ann", "Able", "C")]
        with self.assertRaises(data.DataShrank):
            self.download()
        # Unless that's expected.
        self.download(allow_shrink=True)
        self.assertEqual(read(self.path)["rosters"]["AAA-20212022"], [1])

    def test_check_history_ignores_seasons_before_since(self):
        old = {"rosters": {"AAA-20202021": [1, 2], "AAA-20212022": [1, 3], "BBB-20222023": [4]}}
        new = {"rosters": {"AAA-20212022": [1, 3], "BBB-20222023": [4]}}
        self.assertEqual(len(data.check_history(old, new)), 1)
        self.assertEqual(data.check_history(old, new, first_season=20212022), [])

    def test_shipped_data_file_is_inside_the_package(self):
        self.assertEqual(data.DEFAULT_DATA_FILE.parent.name, "nhl_connections")
        self.assertTrue(data.DEFAULT_DATA_FILE.exists())


if __name__ == "__main__":
    unittest.main()
