import copy
from fractions import Fraction
import unittest

from standings import aggregate


def two_players(outcomes):
    matches = []
    for seed, outcome in enumerate(outcomes):
        for a, b in (("A", "B"), ("B", "A")):
            score_a, score_b = {"win": (100, 0), "loss": (0, 100), "draw": (50, 50)}[outcome]
            scores = [score_a, score_b] if a == "A" else [score_b, score_a]
            matches.append({"match": len(matches), "seed": seed, "bots": [a, b], "scores": scores})
    return {"matches": matches}


class OverallTests(unittest.TestCase):
    def test_stage_means_have_equal_weight(self):
        result = aggregate({"round1": two_players(["win"]), "round2": two_players(["loss"]),
                            "finals": two_players(["draw"])}, expected_rounds=1)
        for row in result["leaderboard"]:
            self.assertEqual(row["total_exact"], "4/3")
            self.assertEqual(row["rank"], 1)

    def test_unequal_or_unfinished_round_counts_rejected(self):
        data = {s: two_players(["draw"]) for s in ("round1", "round2", "finals")}
        with self.assertRaises(ValueError):
            aggregate(data, expected_rounds=2)
        data["finals"] = two_players(["draw", "draw"])
        with self.assertRaises(ValueError):
            aggregate(data)

    def test_game_score_magnitude_is_not_tournament_points(self):
        data = {s: two_players(["win"]) for s in ("round1", "round2", "finals")}
        data["round1"]["matches"][0]["scores"] = [100000, 99999]
        rows = aggregate(data)["leaderboard"]
        self.assertEqual((rows[0]["bot"], rows[0]["total_exact"]), ("A", "3"))
        self.assertEqual(rows[1]["total_exact"], "0")

    def test_missing_stage_or_fixture_rejected(self):
        with self.assertRaises(ValueError):
            aggregate({"round1": two_players(["draw"])})
        data = {s: two_players(["draw"]) for s in ("round1", "round2", "finals")}
        data["finals"]["matches"].pop()
        with self.assertRaises(ValueError):
            aggregate(data)

    def test_duplicate_match_and_nan_rejected(self):
        data = {s: two_players(["draw"]) for s in ("round1", "round2", "finals")}
        bad = copy.deepcopy(data)
        bad["round1"]["matches"].append(bad["round1"]["matches"][0])
        with self.assertRaises(ValueError):
            aggregate(bad)
        data["round1"]["matches"][0]["scores"] = [float("nan"), 2]
        with self.assertRaises(ValueError):
            aggregate(data)

    def test_changed_roster_rejected(self):
        data = {s: two_players(["draw"]) for s in ("round1", "round2", "finals")}
        for game in data["finals"]["matches"]:
            game["bots"] = ["C" if n == "B" else n for n in game["bots"]]
        with self.assertRaises(ValueError):
            aggregate(data)

    def test_shared_competition_ranks(self):
        matches = []
        for a in "ABC":
            for b in "ABC":
                if a == b:
                    continue
                scores = [0, 1] if a == "C" else [1, 0] if b == "C" else [1, 1]
                matches.append({"match": len(matches), "seed": 12, "bots": [a, b], "scores": scores})
        rows = aggregate({s: {"matches": matches} for s in ("round1", "round2", "finals")})["leaderboard"]
        self.assertEqual([r["rank"] for r in rows], [1, 1, 3])
        self.assertEqual(Fraction(rows[0]["total_exact"]), 2)


if __name__ == "__main__":
    unittest.main()
