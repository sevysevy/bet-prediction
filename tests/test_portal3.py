"""
tests/test_portal3.py — Tests unitaires et d'intégration pour le Portail 3 (Filtre Dur Sécuritaire).
"""

import os
import sys
import json
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from src.portals.portal3_hard_filter import (
    filter_portal_3,
    evaluate_candidate,
    audit_portal_3,
    DEFAULT_MIN_PROB,
    DEFAULT_MIN_ODDS,
    DEFAULT_MAX_ODDS,
    DEFAULT_MIN_EV,
    DEFAULT_MAX_SHARP_MARGIN,
)


class TestPortal3HardFilter(unittest.TestCase):
    def setUp(self):
        # Base selection parfaite satisfaisant tous les critères
        self.perfect_sel = {
            "match_id": "match_001",
            "match": "Real Madrid - Barcelona",
            "sel": "Real Madrid",
            "prob": 0.60,
            "price": 1.75,
            "ev": 0.05,
            "sharp_margin": 0.025,
            "sharp": "Pinnacle",
            "book": "Pinnacle",
            "kelly_quarter": 0.02,
            "status": "UPCOMING",
        }

    def test_perfect_selection_passes(self):
        ok, reason = evaluate_candidate(self.perfect_sel)
        self.assertTrue(ok)
        self.assertIsNone(reason)
        result = filter_portal_3([self.perfect_sel])
        self.assertEqual(len(result), 1)

    def test_strict_prob_threshold(self):
        """Vérifie l'exclusion stricte de tout ce qui est en dessous de 55% de probabilité."""
        # Limite exacte 55%
        sel_55 = dict(self.perfect_sel, prob=0.55)
        self.assertTrue(evaluate_candidate(sel_55)[0])

        # Juste en-dessous de 55%
        sel_549 = dict(self.perfect_sel, prob=0.5499)
        ok, reason = evaluate_candidate(sel_549)
        self.assertFalse(ok)
        self.assertIn("prob_insuffisante", reason)

        # 40% (outsider ou cote moyenne rejetée)
        sel_40 = dict(self.perfect_sel, prob=0.40)
        self.assertFalse(evaluate_candidate(sel_40)[0])

        # Test d'intégration filter_portal_3
        filtered = filter_portal_3([sel_55, sel_549, sel_40])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["prob"], 0.55)

    def test_strict_odds_boundaries(self):
        """Vérifie l'intervalle strict de cote : 1.35 <= cote <= 2.30."""
        # Limite basse : 1.35 acceptée
        sel_low = dict(self.perfect_sel, price=1.35, prob=0.76, ev=0.026)
        self.assertTrue(evaluate_candidate(sel_low)[0])

        # Micro-cote < 1.35 rejetée
        sel_too_low = dict(self.perfect_sel, price=1.349, prob=0.80, ev=0.079)
        ok, reason = evaluate_candidate(sel_too_low)
        self.assertFalse(ok)
        self.assertIn("cote_trop_faible", reason)

        # Limite haute : 2.30 acceptée
        sel_high = dict(self.perfect_sel, price=2.30, prob=0.55, ev=0.265)
        self.assertTrue(evaluate_candidate(sel_high)[0])

        # Cote trop risquée > 2.30 rejetée
        sel_too_high = dict(self.perfect_sel, price=2.301, prob=0.55, ev=0.265)
        ok, reason = evaluate_candidate(sel_too_high)
        self.assertFalse(ok)
        self.assertIn("cote_trop_elevee", reason)

    def test_ev_positive_or_zero(self):
        """Vérifie que l'EV doit être strictement >= 0.0%."""
        # EV neutre 0.0% acceptée
        sel_ev_zero = dict(self.perfect_sel, ev=0.0)
        self.assertTrue(evaluate_candidate(sel_ev_zero)[0])

        # EV positive acceptée
        sel_ev_pos = dict(self.perfect_sel, ev=0.015)
        self.assertTrue(evaluate_candidate(sel_ev_pos)[0])

        # EV négative rejetée même avec p élevée
        sel_ev_neg = dict(self.perfect_sel, prob=0.60, price=1.50, ev=-0.10)
        ok, reason = evaluate_candidate(sel_ev_neg)
        self.assertFalse(ok)
        self.assertIn("ev_negative", reason)

    def test_sharp_margin_limit(self):
        """Vérifie le respect de la marge sharp benchmark <= 5.0%."""
        # Marge <= 5% acceptée
        sel_margin_5 = dict(self.perfect_sel, sharp_margin=0.05)
        self.assertTrue(evaluate_candidate(sel_margin_5)[0])

        # Marge > 5% rejetée (marché illiquide ou peu efficient)
        sel_margin_high = dict(self.perfect_sel, sharp_margin=0.0505)
        ok, reason = evaluate_candidate(sel_margin_high)
        self.assertFalse(ok)
        self.assertIn("marge_sharp_excessive", reason)

    def test_one_selection_per_match(self):
        """Vérifie qu'exactement 1 seule sélection est conservée par match (sélection élite)."""
        # Match avec 2 sélections éligibles
        sel_a = dict(
            self.perfect_sel,
            match_id="m123",
            sel="Real Madrid (1X2)",
            prob=0.62,
            price=1.70,
            ev=0.054,
        )
        sel_b = dict(
            self.perfect_sel,
            match_id="m123",
            sel="Over 1.5 Goals",
            prob=0.78,
            price=1.38,
            ev=0.076,
        )

        # Par défaut (rank_by='ev'), sel_b doit être retenue (ev 0.076 > 0.054)
        retained = filter_portal_3([sel_a, sel_b], one_per_match=True, rank_by="ev")
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["sel"], "Over 1.5 Goals")

        # Avec rank_by='prob', sel_b a également la plus haute prob
        retained_prob = filter_portal_3([sel_a, sel_b], one_per_match=True, rank_by="prob")
        self.assertEqual(len(retained_prob), 1)
        self.assertEqual(retained_prob[0]["sel"], "Over 1.5 Goals")

    def test_dynamic_reinclusion(self):
        """
        Vérifie la ré-inclusion dynamique : l'algorithme est sans état (stateless).
        Une sélection dont la probabilité augmente ou dont la cote passe le filtre
        est réintégrée instantanément à chaque nouveau pull.
        """
        initial_feed = [
            dict(self.perfect_sel, match_id="match_live", prob=0.52, ev=-0.02),  # Éliminée au pull 1
        ]
        # Pull 1 : rejetée
        res_pull1 = filter_portal_3(initial_feed)
        self.assertEqual(len(res_pull1), 0)

        # Pull 2 : les cotes / probabilités évoluent (sharp money arrive sur le match)
        updated_feed = [
            dict(self.perfect_sel, match_id="match_live", prob=0.58, price=1.80, ev=0.044),
        ]
        # Pull 2 : ré-inclusion dynamique immédiate
        res_pull2 = filter_portal_3(updated_feed)
        self.assertEqual(len(res_pull2), 1)
        self.assertEqual(res_pull2[0]["match_id"], "match_live")
        self.assertAlmostEqual(res_pull2[0]["prob"], 0.58)

    def test_real_data_json_audit(self):
        """Vérifie l'application du Portail 3 sur les données actuelles de _site/data.json."""
        data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_site", "data.json")
        if not os.path.exists(data_path):
            self.skipTest("_site/data.json non présent")

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sels = data.get("selections", [])
        self.assertGreater(len(sels), 0)

        audit = audit_portal_3(sels)
        filtered = audit["selections"]

        # Assertions strictes sur toutes les sélections retournées
        seen_matches = set()
        for s in filtered:
            # 1. Prob >= 0.55
            self.assertGreaterEqual(s["prob"], 0.55)
            # 2. 1.35 <= price <= 2.30
            self.assertGreaterEqual(s["price"], 1.35)
            self.assertLessEqual(s["price"], 2.30)
            # 3. EV >= 0.0
            self.assertGreaterEqual(s["ev"], 0.0)
            # 4. sharp_margin <= 0.05
            if s.get("sharp_margin") is not None:
                self.assertLessEqual(s["sharp_margin"], 0.05)
            # 5. Unicité du match
            m = s.get("match_id") or s.get("match")
            self.assertNotIn(m, seen_matches)
            seen_matches.add(m)

        # Doit avoir qualifié au moins les 7 matches observés lors de l'analyse
        self.assertEqual(len(filtered), 7)


if __name__ == "__main__":
    unittest.main()
