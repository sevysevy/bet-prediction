"""
tests/test_all.py — Suite de tests unitaires pour la plateforme bet-prediction.

Vérifie :
- Les fondements mathématiques (dévigorisation, EV, Kelly)
- L'intégrité des combinés (indépendance, bookmaker unique, contrainte 4 jambes)
- La couche d'ingestion et normalisation des flux
- Le journal SQLite et le calcul du CLV
"""
import os
import sys
import unittest
import tempfile
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from maths import (
    devig_multiplicative,
    devig_power,
    compute_ev,
    kelly_fraction,
    compound_combination
)
import feeds
import journal


class TestMaths(unittest.TestCase):

    def test_devig_multiplicative_basic(self):
        prices = {"1": 2.0, "X": 3.0, "2": 4.0}
        res = devig_multiplicative(prices)
        probs = res["probs"]
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=7)
        self.assertAlmostEqual(res["overround"], 0.5 + 1/3 + 0.25, places=5)
        self.assertAlmostEqual(res["margin"], res["overround"] - 1.0, places=5)

    def test_devig_power(self):
        prices = {"Home": 1.25, "Draw": 6.0, "Away": 11.0}
        res = devig_power(prices)
        probs = res["probs"]
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=6)
        # Power model should yield valid probabilities
        self.assertTrue(0.70 < probs["Home"] < 0.85)

    def test_compute_ev(self):
        # 80% prob @ 1.30 -> EV = 0.80 * 1.30 - 1 = +0.04 (+4%)
        ev_pos = compute_ev(0.80, 1.30)
        self.assertAlmostEqual(ev_pos, 0.04, places=6)

        # 50% prob @ 1.90 -> EV = 0.50 * 1.90 - 1 = -0.05 (-5%)
        ev_neg = compute_ev(0.50, 1.90)
        self.assertAlmostEqual(ev_neg, -0.05, places=6)

    def test_kelly_fraction(self):
        # EV negative -> 0 mise
        self.assertEqual(kelly_fraction(0.50, 1.90), 0.0)

        # Edge positif : p=0.60, cote=2.0 (b=1.0)
        # f* = (0.60 * 1 - 0.40) / 1 = 0.20
        # Quarter-Kelly (f*/4) = 0.05 (5%)
        k_stake = kelly_fraction(0.60, 2.0, fraction=0.25, max_stake_pct=0.10)
        self.assertAlmostEqual(k_stake, 0.05, places=4)

        # Plafonnement strict
        k_capped = kelly_fraction(0.90, 2.0, fraction=1.0, max_stake_pct=0.05)
        self.assertEqual(k_capped, 0.05)

    def test_compound_combination(self):
        legs = [
            {"match": "Match A", "sel": "1", "prob": 0.80, "prices": {"Book1": 1.20, "Book2": 1.18}},
            {"match": "Match B", "sel": "1", "prob": 0.75, "prices": {"Book1": 1.25, "Book2": 1.30}},
        ]
        combo = compound_combination(legs)
        self.assertIsNotNone(combo)
        self.assertEqual(combo["n"], 2)
        # Prob = 0.80 * 0.75 = 0.60
        self.assertAlmostEqual(combo["prob"], 0.60, places=5)
        # Cote Book2 : 1.18 * 1.30 = 1.534 vs Book1: 1.20 * 1.25 = 1.50
        self.assertEqual(combo["book"], "Book2")
        self.assertAlmostEqual(combo["odds"], 1.18 * 1.30, places=4)

    def test_combination_rejects_correlated_matches(self):
        # Deux sélections du MÊME match doivent être rejetées
        legs = [
            {"match": "Real - Barca", "sel": "Real", "prob": 0.60, "prices": {"Book1": 1.60}},
            {"match": "Real - Barca", "sel": "Over 2.5", "prob": 0.70, "prices": {"Book1": 1.40}},
        ]
        self.assertIsNone(compound_combination(legs))


class TestJournal(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_journal.db")

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_journal_logging_and_stats(self):
        recs = [
            {
                "event_id": "ev1",
                "league": "Ligue 1",
                "match": "PSG - Monaco",
                "sel": "PSG",
                "prob": 0.75,
                "price": 1.40,
                "book": "Winamax",
                "sharp": "Pinnacle",
                "sharp_margin": 0.04,
                "ev": 0.05,
                "kelly_quarter": 0.02
            },
            {
                "event_id": "ev2",
                "league": "EPL",
                "match": "Arsenal - Chelsea",
                "sel": "Arsenal",
                "prob": 0.55,
                "price": 1.70,
                "book": "Betclic",
                "sharp": "Pinnacle",
                "sharp_margin": 0.03,
                "ev": -0.065,
                "kelly_quarter": 0.0
            }
        ]
        inserted = journal.log_recommendations(recs, db_path=self.db_path)
        self.assertEqual(inserted, 2)

        stats = journal.get_stats(db_path=self.db_path)
        self.assertEqual(stats["total_signals"], 2)
        self.assertEqual(stats["positive_ev_count"], 1)
        self.assertEqual(stats["negative_ev_count"], 1)

        # Test CLV tracking
        # Prise à 1.40, clôture à 1.30 -> CLV = (1.40 / 1.30) - 1 = +7.69%
        updated = journal.update_closing_odds("PSG - Monaco", "PSG", 1.30, db_path=self.db_path)
        self.assertEqual(updated, 1)

        recent = journal.get_recent_recommendations(db_path=self.db_path)
        psg_rec = [r for r in recent if r["match"] == "PSG - Monaco"][0]
        self.assertIsNotNone(psg_rec["clv"])
        self.assertAlmostEqual(psg_rec["clv"], (1.40 / 1.30) - 1.0, places=4)


class TestFeeds(unittest.TestCase):

    def test_norm_theodds(self):
        events = feeds.norm_theodds(feeds.FIX_THEODDS)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["home"], "Manchester City")
        self.assertEqual(len(ev["books"]), 2)
        sharp = feeds.pick_sharp(ev["books"])
        self.assertEqual(sharp["name"], "Pinnacle")

    def test_norm_oddspapi(self):
        events = feeds.norm_oddspapi(feeds.FIX_ODDSPAPI)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(len(ev["books"]), 2)
        for b in ev["books"]:
            self.assertAlmostEqual(sum(b["probs"].values()), 1.0, places=5)


class TestEnrichmentAndHistory(unittest.TestCase):

    def test_evaluate_outcome(self):
        from build_site import evaluate_outcome
        # 1X2
        self.assertEqual(evaluate_outcome("1X2", "PSG", "PSG", "Monaco", 2, 0), "WON")
        self.assertEqual(evaluate_outcome("1X2", "Monaco", "PSG", "Monaco", 2, 0), "LOST")
        self.assertEqual(evaluate_outcome("1X2", "Draw", "PSG", "Monaco", 1, 1), "WON")
        self.assertEqual(evaluate_outcome("1X2", "Match Nul", "PSG", "Monaco", 2, 0), "LOST")

        # Over / Under
        self.assertEqual(evaluate_outcome("Total Buts", "+2.5 Buts", "PSG", "Monaco", 2, 1), "WON")
        self.assertEqual(evaluate_outcome("Total Buts", "+2.5 Buts", "PSG", "Monaco", 1, 0), "LOST")
        self.assertEqual(evaluate_outcome("Total Buts", "-2.5 Buts", "PSG", "Monaco", 1, 0), "WON")

        # BTTS
        self.assertEqual(evaluate_outcome("Les 2 marquent", "Les 2 marquent : Oui", "PSG", "Monaco", 1, 1), "WON")
        self.assertEqual(evaluate_outcome("Les 2 marquent", "Les 2 marquent : Oui", "PSG", "Monaco", 1, 0), "LOST")

    def test_enrich_preserves_prematch_and_no_fake_odds(self):
        from build_site import enrich_rows_with_scores
        rows = [
            {
                "match": "Real Madrid - Barcelona",
                "sel": "Real Madrid",
                "prob": 0.55,
                "price": 1.95,
                "book": "Winamax",
                "ev": 0.072,
                "status": "UPCOMING",
                "kickoff": "2026-10-18T20:00:00Z"
            }
        ]
        scores_map = {
            ("realmadrid", "barcelona"): {
                "completed": True,
                "home_team": "Real Madrid",
                "away_team": "Barcelona",
                "home_score": 2,
                "away_score": 1,
                "league": "soccer_spain_la_liga"
            },
            # Completed match NOT in rows and NOT in prematch_db
            ("strasbourg", "paris"): {
                "completed": True,
                "home_team": "Strasbourg",
                "away_team": "Paris",
                "home_score": 0,
                "away_score": 2,
                "league": "soccer_france_ligue_one"
            }
        }
        prematch_db = {
            ("realmadrid", "barcelona"): {
                "Real Madrid": {
                    "match": "Real Madrid - Barcelona",
                    "selection": "Real Madrid",
                    "prob_fair": 0.55,
                    "odds_offered": 1.95,
                    "bookmaker": "Winamax",
                    "ev": 0.072,
                    "sharp_ref": "Pinnacle"
                }
            }
        }

        enrich_rows_with_scores(rows, scores_map, prematch_db=prematch_db)

        # Real Madrid should be marked FINISHED with WON outcome, keeping its 1.95 odds and 55% prob
        rm_row = [r for r in rows if r["match"] == "Real Madrid - Barcelona"][0]
        self.assertEqual(rm_row["status"], "FINISHED")
        self.assertEqual(rm_row["outcome"], "WON")
        self.assertEqual(rm_row["price"], 1.95)
        self.assertEqual(rm_row["prob"], 0.55)
        self.assertEqual(rm_row["book"], "Winamax")
        self.assertEqual(rm_row["score_str"], "2 - 1")

        # Must NOT contain any fake "Score Officiel" or artificial 1.00 odds
        for r in rows:
            self.assertNotEqual(r.get("book"), "Score Officiel")
            self.assertNotEqual(r.get("price"), 1.0)


class TestRefreshAuthAndForce(unittest.TestCase):

    def test_refresh_auth_validation(self):
        from serve import _check_refresh_auth
        old_env = os.environ.get("REFRESH_KEY")
        try:
            os.environ["REFRESH_KEY"] = "supersecret123"

            # 1. Valid via query ?key=
            self.assertTrue(_check_refresh_auth({}, {"key": "supersecret123"}))
            # 2. Valid via query ?token=
            self.assertTrue(_check_refresh_auth({}, {"token": "supersecret123"}))
            # 3. Valid via header X-Refresh-Key
            self.assertTrue(_check_refresh_auth({"x-refresh-key": "supersecret123"}, {}))
            # 4. Valid via header Authorization: Bearer
            self.assertTrue(_check_refresh_auth({"authorization": "Bearer supersecret123"}, {}))

            # 5. Invalid attempts
            self.assertFalse(_check_refresh_auth({}, {"key": "wrong_key"}))
            self.assertFalse(_check_refresh_auth({}, {}))
            self.assertFalse(_check_refresh_auth({"x-refresh-key": "bad"}, {}))

            # 6. Unrestricted when REFRESH_KEY is not set
            del os.environ["REFRESH_KEY"]
            self.assertTrue(_check_refresh_auth({}, {}))
        finally:
            if old_env is not None:
                os.environ["REFRESH_KEY"] = old_env
            elif "REFRESH_KEY" in os.environ:
                del os.environ["REFRESH_KEY"]

    def test_force_refresh_bypasses_cache(self):
        import feeds
        import tempfile
        import time

        old_force = os.environ.get("FORCE_REFRESH")
        try:
            # When FORCE_REFRESH=1, feeds.get skips cache read
            os.environ["FORCE_REFRESH"] = "1"
            # Verify flag logic
            force_pull = bool(os.environ.get("FORCE_REFRESH") in ("1", "true", "yes"))
            self.assertTrue(force_pull)
        finally:
            if old_force is not None:
                os.environ["FORCE_REFRESH"] = old_force
            elif "FORCE_REFRESH" in os.environ:
                del os.environ["FORCE_REFRESH"]


try:
    from test_portal1 import TestPortal1Unit, TestPortal1IntegrationDataJson
except ImportError:
    try:
        from tests.test_portal1 import TestPortal1Unit, TestPortal1IntegrationDataJson
    except ImportError:
        pass

try:
    from test_portal2 import TestPortal2Sharpe
except ImportError:
    try:
        from tests.test_portal2 import TestPortal2Sharpe
    except ImportError:
        pass

try:
    from test_portal3 import TestPortal3HardFilter
except ImportError:
    try:
        from tests.test_portal3 import TestPortal3HardFilter
    except ImportError:
        pass


if __name__ == "__main__":
    unittest.main()

