#!/usr/bin/env python3
"""
tests/test_portal1.py — Suite de tests unitaires et d'intégration pour le Portail 1.

Valide :
1. Le filtrage des deux paliers stratégiques :
   - Palier 1 'Coffre-Fort' (p >= 0.65, cote >= 1.25)
   - Palier 2 'Pépites Value' (0.45 <= p < 0.65, EV > +0.01, 1.50 <= cote <= 2.30)
2. L'exclusion stricte de la corbeille à bruit (p < 0.40)
3. La garantie stricte d'une sélection UNIQUE par match (jamais de doublons 1/N/2)
4. L'arbitrage de sélection ('safest' vs 'attractive')
5. La ré-inclusion dynamique lorsque les cotes et probabilités mûrissent
6. La validation sur les données réelles de _site/data.json avec extraction des métriques
"""
from __future__ import annotations

import json
import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from portals.portal1_double_tier import (
    filter_portal_1,
    get_portal_1_summary,
    partition_by_tier,
    classify_selection,
    get_match_dedup_key,
    COFFRE_FORT_MIN_PROB,
    COFFRE_FORT_MIN_ODDS,
    PEPITE_MIN_PROB,
    PEPITE_MAX_PROB,
    PEPITE_MIN_EV,
    PEPITE_MIN_ODDS,
    PEPITE_MAX_ODDS,
    NOISE_PROB_THRESHOLD,
)


class TestPortal1Unit(unittest.TestCase):
    """Tests unitaires ciblés sur les règles algorithmiques du Portail 1."""

    def test_noise_bin_exclusion(self):
        """Toute sélection avec probabilité < 0.40 doit être impérativement exclue."""
        noisy_selections = [
            {"match": "Match A - Team B", "sel": "Team B", "prob": 0.39, "price": 2.70, "ev": 0.05},
            {"match": "Match C - Team D", "sel": "Team D", "prob": 0.20, "price": 6.00, "ev": 0.20},
            {"match": "Match E - Team F", "sel": "Nul", "prob": 0.3999, "price": 3.10, "ev": 0.10},
        ]
        qualified = filter_portal_1(noisy_selections)
        self.assertEqual(len(qualified), 0, "Les sélections avec p < 0.40 doivent être rejetées")

    def test_coffre_fort_eligibility(self):
        """Vérifie l'attribution du Palier 1 'Coffre-Fort' et ses métadonnées."""
        sel_ok = {
            "match": "Real Madrid - Getafe",
            "kickoff": "2026-10-20T20:00:00Z",
            "sel": "Real Madrid",
            "prob": 0.78,
            "price": 1.30,
            "ev": 0.014,
            "book": "Pinnacle",
        }
        qualified = filter_portal_1([sel_ok])
        self.assertEqual(len(qualified), 1)
        res = qualified[0]
        self.assertEqual(res["tier"], "coffre_fort")
        self.assertEqual(res["badge"], "🛡️ Coffre-Fort")
        self.assertEqual(res["label"], "Bases Solides")
        self.assertEqual(res["strike_rate_estime"], 78.0)
        self.assertEqual(res["strike_rate_target"], "> 75%")

        # Test cote inférieure au seuil 1.25 -> doit être rejeté de Coffre-Fort
        sel_too_low_odds = dict(sel_ok, price=1.22)
        self.assertEqual(len(filter_portal_1([sel_too_low_odds])), 0)

        # Test proba inférieure à 0.65 -> doit être rejeté de Coffre-Fort
        sel_low_prob = dict(sel_ok, prob=0.64)
        self.assertEqual(len(filter_portal_1([sel_low_prob])), 0)

    def test_pepites_value_eligibility(self):
        """Vérifie l'attribution du Palier 2 'Pépites Value' et ses critères stricts."""
        sel_ok = {
            "match": "Arsenal - Chelsea",
            "kickoff": "2026-10-21T16:30:00Z",
            "sel": "Arsenal",
            "prob": 0.55,
            "price": 1.95,
            "ev": 0.0725,  # +7.25% EV
            "book": "1xBet",
        }
        qualified = filter_portal_1([sel_ok])
        self.assertEqual(len(qualified), 1)
        res = qualified[0]
        self.assertEqual(res["tier"], "pepite_value")
        self.assertEqual(res["badge"], "💎 Pépites Value")
        self.assertEqual(res["label"], "Pépites Value")
        self.assertEqual(res["strike_rate_estime"], 55.0)

        # Rejet si EV <= +0.01 (+1%)
        sel_low_ev = dict(sel_ok, ev=0.005)
        self.assertEqual(len(filter_portal_1([sel_low_ev])), 0)

        # Rejet si cote hors fourchette [1.50, 2.30]
        sel_odds_too_low = dict(sel_ok, price=1.45)
        self.assertEqual(len(filter_portal_1([sel_odds_too_low])), 0)
        sel_odds_too_high = dict(sel_ok, price=2.40)
        self.assertEqual(len(filter_portal_1([sel_odds_too_high])), 0)

        # Rejet si probabilité hors de [0.45, 0.65[
        sel_prob_too_low = dict(sel_ok, prob=0.44)
        self.assertEqual(len(filter_portal_1([sel_prob_too_low])), 0)
        sel_prob_too_high = dict(sel_ok, prob=0.66)  # Va dans Coffre-Fort si price >= 1.25
        res_high = filter_portal_1([sel_prob_too_high])
        self.assertEqual(res_high[0]["tier"], "coffre_fort")

    def test_single_selection_per_match_and_no_duplicates(self):
        """
        Règle absolue : 1 seule sélection maximale par match.
        Aucun doublon 1/N/2 ou cumul de marchés sur la même rencontre.
        """
        conflicting_selections = [
            # Marché 1X2 Victoire Domicile
            {"match": "PSG - Marseille", "kickoff": "2026-10-25T20:00:00Z", "sel": "PSG", "prob": 0.70, "price": 1.40, "ev": -0.02},
            # Marché Remboursé si Nul (même match)
            {"match": "PSG - Marseille", "kickoff": "2026-10-25T20:00:00Z", "sel": "DNB PSG", "prob": 0.82, "price": 1.26, "ev": 0.033},
            # Marché Buts +1.5 (même match)
            {"match": "PSG - Marseille", "kickoff": "2026-10-25T20:00:00Z", "sel": "+1.5 Buts", "prob": 0.75, "price": 1.28, "ev": -0.04},
        ]

        # En mode 'safest', la plus sûre (plus forte probabilité : 0.82) doit être sélectionnée
        res_safest = filter_portal_1(conflicting_selections, arbitration="safest")
        self.assertEqual(len(res_safest), 1, "Un seul pari doit être retenu par match")
        self.assertEqual(res_safest[0]["sel"], "DNB PSG")
        self.assertEqual(res_safest[0]["prob"], 0.82)

    def test_arbitration_modes(self):
        """
        Vérifie l'arbitrage en cas de match éligible à la fois en Coffre-Fort et en Pépite Value :
        - 'safest' : retient le pari Coffre-Fort (plus sûre)
        - 'attractive' : retient le pari Pépite Value (plus forte EV)
        """
        match_cands = [
            # Candidat Coffre-Fort (+1.5 Buts, très probable mais faible EV)
            {"match": "Lyon - Monaco", "kickoff": "2026-10-22T19:00:00Z", "sel": "+1.5 Buts", "prob": 0.76, "price": 1.28, "ev": -0.03},
            # Candidat Pépite Value (Victoire Monaco, proba 52% mais EV +5%)
            {"match": "Lyon - Monaco", "kickoff": "2026-10-22T19:00:00Z", "sel": "Monaco", "prob": 0.52, "price": 2.02, "ev": 0.0504},
        ]

        # 1. Mode 'safest'
        res_safest = filter_portal_1(match_cands, arbitration="safest")
        self.assertEqual(len(res_safest), 1)
        self.assertEqual(res_safest[0]["tier"], "coffre_fort")
        self.assertEqual(res_safest[0]["sel"], "+1.5 Buts")

        # 2. Mode 'attractive'
        res_attr = filter_portal_1(match_cands, arbitration="attractive")
        self.assertEqual(len(res_attr), 1)
        self.assertEqual(res_attr[0]["tier"], "pepite_value")
        self.assertEqual(res_attr[0]["sel"], "Monaco")

    def test_dynamic_reinclusion(self):
        """
        Vérifie la ré-inclusion dynamique :
        Lors d'un premier snapshot lointain, un match a des cotes instables (p=0.58, EV=-0.02).
        Lors du snapshot suivant plus proche du coup d'envoi, la probabilité mûrit (p=0.68, cote=1.42).
        Le filtre doit automatiquement le qualifier sans état résiduel.
        """
        match_t0 = [
            {"match": "Barcelone - Valence", "kickoff": "2026-10-30T20:00:00Z", "sel": "Barcelone", "prob": 0.58, "price": 1.65, "ev": -0.04}
        ]
        # t0 : Non éligible (EV négative pour le palier 45-65%, prob < 0.65 pour Coffre-Fort)
        self.assertEqual(len(filter_portal_1(match_t0)), 0)

        # t1 : Ligne mûrie (affinement des marchés sharp)
        match_t1 = [
            {"match": "Barcelone - Valence", "kickoff": "2026-10-30T20:00:00Z", "sel": "Barcelone", "prob": 0.72, "price": 1.35, "ev": -0.028}
        ]
        res_t1 = filter_portal_1(match_t1)
        self.assertEqual(len(res_t1), 1)
        self.assertEqual(res_t1[0]["tier"], "coffre_fort")
        self.assertEqual(res_t1[0]["strike_rate_estime"], 72.0)


class TestPortal1IntegrationDataJson(unittest.TestCase):
    """Tests d'intégration directement sur les données en production _site/data.json."""

    @classmethod
    def setUpClass(cls):
        cls.data_path = os.path.join(ROOT, "_site", "data.json")
        if not os.path.exists(cls.data_path):
            raise unittest.SkipTest(f"Fichier _site/data.json introuvable : {cls.data_path}")
        with open(cls.data_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.raw_selections = cls.data.get("selections", [])

    def test_portal1_data_json_counts_and_integrity(self):
        """
        Exécute filter_portal_1 sur _site/data.json et vérifie :
        - Les règles d'intégrité de chaque sélection qualifiée
        - L'absence de doublons de match
        - L'exclusion des sélections bruitées
        - Les comptages exacts
        """
        self.assertGreater(len(self.raw_selections), 0)

        qualified_safest = filter_portal_1(self.raw_selections, arbitration="safest")
        qualified_attr = filter_portal_1(self.raw_selections, arbitration="attractive")

        # 1. Vérification des doublons de match : STRICTEMENT 1 PAR MATCH
        keys_safest = [get_match_dedup_key(s) for s in qualified_safest]
        self.assertEqual(len(keys_safest), len(set(keys_safest)), "Aucun doublon de match autorisé")

        # 2. Vérification de l'exclusion de la corbeille à bruit
        for s in qualified_safest:
            self.assertGreaterEqual(s["prob"], NOISE_PROB_THRESHOLD, "Toute sélection sous 0.40 doit être exclue")
            self.assertGreaterEqual(s["price"], 1.0)
            self.assertIn(s["tier"], ("coffre_fort", "pepite_value"))
            self.assertIn("strike_rate_estime", s)
            self.assertIn("badge", s)
            self.assertIn("label", s)

        # 3. Vérification des conditions spécifiques de chaque Palier
        cf_list, pv_list = partition_by_tier(qualified_safest)

        for s in cf_list:
            self.assertGreaterEqual(s["prob"], COFFRE_FORT_MIN_PROB)
            self.assertGreaterEqual(s["price"], COFFRE_FORT_MIN_ODDS)
            self.assertEqual(s["tier"], "coffre_fort")

        for s in pv_list:
            self.assertGreaterEqual(s["prob"], PEPITE_MIN_PROB)
            self.assertLess(s["prob"], PEPITE_MAX_PROB)
            self.assertGreater(s["ev"], PEPITE_MIN_EV - 1e-9)
            self.assertGreaterEqual(s["price"], PEPITE_MIN_ODDS)
            self.assertLessEqual(s["price"], PEPITE_MAX_ODDS)
            self.assertEqual(s["tier"], "pepite_value")

        # 4. Synthèse et vérification des comptes
        summary_safest = get_portal_1_summary(self.raw_selections, qualified_selections=qualified_safest, arbitration="safest")
        summary_attr = get_portal_1_summary(self.raw_selections, qualified_selections=qualified_attr, arbitration="attractive")

        self.assertEqual(summary_safest["total_raw_signals"], 1467)
        self.assertEqual(summary_safest["noise_bin_excluded"], 720)
        self.assertIn(summary_safest["total_qualified"], (112, 113))
        self.assertIn(summary_safest["palier_1_coffre_fort"]["count"], (107, 108))
        self.assertEqual(summary_safest["palier_2_pepites_value"]["count"], 5)

        # En mode 'attractive', Nottingham Forest - Arsenal bascule en Pépite Value (+EV)
        self.assertIn(summary_attr["total_qualified"], (112, 113))
        self.assertIn(summary_attr["palier_1_coffre_fort"]["count"], (106, 107))
        self.assertEqual(summary_attr["palier_2_pepites_value"]["count"], 6)

        # 5. Affichage d'échantillons concrets pour le rapport
        print("\n=== VALIDATION SUR _SITE/DATA.JSON ===")
        print(f"Total signaux bruts analysés : {summary_safest['total_raw_signals']}")
        print(f"Signaux exclus (bruit p < 40%) : {summary_safest['noise_bin_excluded']}")
        print(f"Sélections qualifiées Portail 1 : {summary_safest['total_qualified']} matches uniques")
        print(f"  * 🛡️ Coffre-Fort : {len(cf_list)} matches | Cote moy : {summary_safest['palier_1_coffre_fort']['avg_odds']} | Strike rate estimé : {summary_safest['palier_1_coffre_fort']['strike_rate_estime']}%")
        print(f"  * 💎 Pépites Value : {len(pv_list)} matches | Cote moy : {summary_safest['palier_2_pepites_value']['avg_odds']} | EV moy : {summary_safest['palier_2_pepites_value']['avg_ev']*100:+.2f}%")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    unittest.main()
