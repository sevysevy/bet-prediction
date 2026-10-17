"""
tests/test_portal2.py — Tests unitaires et de validation quantitative pour le Portail 2
(Ratio de Sharpe Sportif / Score de Croissance Markowitz-Kelly).
"""

import os
import sys
import json
import math
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from src.portals.portal2_sharpe import (
    compute_bet_sigma,
    compute_bet_sharpe,
    compute_bet_quality_index,
    filter_portal_2,
    audit_portal_2,
    get_match_key,
)


class TestPortal2Sharpe(unittest.TestCase):
    def setUp(self):
        # Base selection d'élite : favori value à fort taux de réussite
        self.solid_favorite = {
            "match_id": "match_001",
            "match": "Paris SG - Lyon",
            "sel": "Paris SG",
            "prob": 0.70,
            "price": 1.50,
            "ev": 0.05,  # (0.70 * 1.50) - 1.0 = +5%
            "book": "Pinnacle",
            "status": "UPCOMING",
        }

        # Longshot monstrueux : 1% de chance, cote 251, fausse value 151% EV
        self.ruinous_longshot = {
            "match_id": "match_002",
            "match": "Strasbourg - Paris SG",
            "sel": "Strasbourg",
            "prob": 0.01,
            "price": 251.0,
            "ev": 1.51,  # 0.01 * 251 - 1 = +151%
            "book": "UndergroundBook",
            "status": "UPCOMING",
        }

        # Value pick solide de milieu de tableau (p=45%, cote=2.30, EV=+3.5%)
        self.solid_value = {
            "match_id": "match_003",
            "match": "Marseille - Rennes",
            "sel": "Marseille",
            "prob": 0.45,
            "price": 2.30,
            "ev": 0.035,
            "book": "1xBet",
            "status": "UPCOMING",
        }

    def test_sigma_calculation(self):
        """Vérifie la formule sigma = sqrt(p * (1 - p)) * (price - 1)."""
        # p=0.50, price=2.00 -> sqrt(0.25) * 1.0 = 0.50 * 1.0 = 0.50
        sigma = compute_bet_sigma(0.50, 2.00)
        self.assertAlmostEqual(sigma, 0.50, places=5)

        # Longshot : p=0.01, price=251.0 -> sqrt(0.0099) * 250 = ~0.099498 * 250 = ~24.8746
        sigma_longshot = compute_bet_sigma(0.01, 251.0)
        expected_longshot = math.sqrt(0.01 * 0.99) * 250.0
        self.assertAlmostEqual(sigma_longshot, expected_longshot, places=4)
        self.assertGreater(sigma_longshot, 20.0)

        # Favori : p=0.70, price=1.50 -> sqrt(0.21) * 0.50 = 0.45825 * 0.50 = 0.2291
        sigma_fav = compute_bet_sigma(0.70, 1.50)
        expected_fav = math.sqrt(0.70 * 0.30) * 0.50
        self.assertAlmostEqual(sigma_fav, expected_fav, places=4)

        # La volatilité du longshot est > 100x plus forte que celle du favori
        self.assertGreater(sigma_longshot / sigma_fav, 100.0)

    def test_sharpe_ratio_calculation(self):
        """Vérifie le calcul du Sharpe = EV / sigma."""
        # Pour le favori : EV=0.05, sigma=~0.2291 -> Sharpe = ~0.218
        sharpe_fav = compute_bet_sharpe(0.70, 1.50, 0.05)
        expected_sharpe = 0.05 / (math.sqrt(0.21) * 0.50)
        self.assertAlmostEqual(sharpe_fav, expected_sharpe, places=4)
        self.assertGreater(sharpe_fav, 0.20)

        # EV négative ou nulle -> Sharpe = 0.0
        self.assertEqual(compute_bet_sharpe(0.50, 1.90, -0.05), 0.0)
        self.assertEqual(compute_bet_sharpe(0.50, 2.00, 0.0), 0.0)

    def test_ruin_risk_elimination_of_longshot(self):
        """
        Démontre que le ratio de Sharpe + pénalisation p < 0.40 anéantit complètement
        le score de la cote monstre à 1% malgré un EV facial artificiellement colossal (+151%).
        """
        metrics_longshot = compute_bet_quality_index(
            prob=self.ruinous_longshot["prob"],
            price=self.ruinous_longshot["price"],
            ev=self.ruinous_longshot["ev"],
        )
        metrics_fav = compute_bet_quality_index(
            prob=self.solid_favorite["prob"],
            price=self.solid_favorite["price"],
            ev=self.solid_favorite["ev"],
        )

        # Le score de la cote monstre s'effondre à 0.0 ou < 0.1
        self.assertLess(metrics_longshot["bqi_score"], 0.5)
        self.assertEqual(metrics_longshot["grade"], "C")

        # Le score du favori solide est élevé (A+ ou A)
        self.assertGreaterEqual(metrics_fav["bqi_score"], 80.0)
        self.assertEqual(metrics_fav["grade"], "A+")

        # Classement : le favori écrase totalement l'outsider
        ranked = filter_portal_2([self.ruinous_longshot, self.solid_favorite], top_n=10)
        self.assertEqual(ranked[0]["sel"], "Paris SG")
        self.assertGreaterEqual(ranked[0]["bqi_score"], 80.0)

    def test_steep_penalty_for_p_below_40(self):
        """Vérifie que pour p < 0.40, la pénalité s'effondre polynomialement."""
        m_45 = compute_bet_quality_index(prob=0.45, price=2.30, ev=0.035)
        m_38 = compute_bet_quality_index(prob=0.38, price=2.75, ev=0.045)
        m_30 = compute_bet_quality_index(prob=0.30, price=3.50, ev=0.050)
        m_15 = compute_bet_quality_index(prob=0.15, price=7.00, ev=0.050)

        self.assertGreater(m_45["penalty"], 1.0)  # Strike rate bonus
        self.assertLess(m_38["penalty"], 1.0)
        self.assertLess(m_30["penalty"], 0.30)
        self.assertLess(m_15["penalty"], 0.01)

        # Effondrement du BQI score
        self.assertLess(m_15["bqi_score"], 5.0)

    def test_one_selection_per_match_rule(self):
        """
        Vérifie que si un match présente plusieurs cotes à EV positive,
        strictement 1 seule sélection (celle qui maximise le BQI) est retenue.
        """
        # Match avec Paris SG gagnant vs Nul
        sel_psg_win = {
            "match_id": "match_multi",
            "match": "Paris SG - Lyon",
            "sel": "Paris SG",
            "prob": 0.70,
            "price": 1.50,
            "ev": 0.05,
        }
        sel_psg_draw = {
            "match_id": "match_multi",
            "match": "Paris SG - Lyon",
            "sel": "Draw",
            "prob": 0.20,
            "price": 5.50,
            "ev": 0.10,  # EV faciale plus haute, mais variance excessive
        }

        filtered = filter_portal_2([sel_psg_win, sel_psg_draw], one_per_match=True)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["sel"], "Paris SG")

    def test_dynamic_reinclusion(self):
        """
        Vérifie la ré-inclusion dynamique : l'évaluation est sans état (stateless).
        Si une cote monte et devient value au pull suivant, elle est immédiatement incluse.
        """
        initial_feed = [
            {"match_id": "m1", "match": "Lens - Lille", "sel": "Lens", "prob": 0.50, "price": 1.95, "ev": -0.025}
        ]
        # Pull 1 : EV négative -> 0 sélection retenue
        res_pull1 = filter_portal_2(initial_feed)
        self.assertEqual(len(res_pull1), 0)

        # Pull 2 : la cote monte à 2.10 chez un bookmaker agressif -> EV=+5%
        updated_feed = [
            {"match_id": "m1", "match": "Lens - Lille", "sel": "Lens", "prob": 0.50, "price": 2.10, "ev": 0.05}
        ]
        res_pull2 = filter_portal_2(updated_feed)
        self.assertEqual(len(res_pull2), 1)
        self.assertEqual(res_pull2[0]["sel"], "Lens")
        self.assertIn(res_pull2[0]["grade"], ["A+", "A", "B+"])

    def test_real_data_json_integration(self):
        """
        Test d'intégration sur les données réelles du projet (_site/data.json).
        Vérifie que l'algorithme extrait entre 25 et 30 sélections d'élite qualifiées.
        """
        data_path = os.path.join(ROOT, "_site", "data.json")
        if not os.path.exists(data_path):
            self.skipTest(f"_site/data.json introuvable : {data_path}")

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_selections = data.get("selections", [])
        self.assertGreater(len(raw_selections), 100)

        # Exécution de l'audit Portal 2
        audit = audit_portal_2(raw_selections, top_n=30, one_per_match=True)

        self.assertGreaterEqual(audit["total_inputs"], 1000)
        self.assertGreaterEqual(audit["positive_ev_count"], 50)
        self.assertLessEqual(audit["final_retained_count"], 30)
        self.assertGreaterEqual(audit["final_retained_count"], 25)

        # Vérification des moyennes de l'élite retenue
        avg_prob = audit["averages"]["avg_prob"]
        avg_price = audit["averages"]["avg_price"]
        avg_sharpe = audit["averages"]["avg_sharpe"]

        # La sélection d'élite doit avoir une cote moyenne raisonnable (< 3.0) et un bon Sharpe
        self.assertLess(avg_price, 3.0)
        self.assertGreater(avg_sharpe, 0.02)

        # Vérification qu'aucune sélection du top 30 n'est de match dupliqué
        match_keys = [get_match_key(s) for s in audit["selections"]]
        self.assertEqual(len(match_keys), len(set(match_keys)))

        # Vérification de l'élimination des monstres
        self.assertGreater(len(audit["eliminated_longshots_sample"]), 0)
        first_elim = audit["eliminated_longshots_sample"][0]
        self.assertLess(first_elim["prob"], 0.40)


if __name__ == "__main__":
    unittest.main()
