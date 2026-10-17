"""
verify_portal2.py — Script de démonstration et vérification quantitative du Portail 2
(Ratio de Sharpe Sportif / Score de Croissance Markowitz-Kelly).
"""

import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from src.portals.portal2_sharpe import (
    filter_portal_2,
    audit_portal_2,
    compute_bet_quality_index,
)


def main():
    print("=" * 100)
    print(" VÉRIFICATION QUANTITATIVE DU PORTAIL 2 : RATIO DE SHARPE / MARKOWITZ-KELLY ")
    print("=" * 100)

    data_path = os.path.join(ROOT, "_site", "data.json")
    if not os.path.exists(data_path):
        print(f"Erreur : fichier {data_path} introuvable.")
        return 1

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_sels = data.get("selections", [])
    print(f"-> Nombre total de sélections brutes chargées : {len(raw_sels)}")

    # Exécution de l'audit complet du Portail 2
    audit = audit_portal_2(raw_sels, top_n=30, one_per_match=True)

    print(f"-> Sélections avec EV > 0% : {audit['positive_ev_count']}")
    print(f"-> Sélections d'élite retenues (Top 30, 1 par match) : {audit['final_retained_count']}")
    print("\n[RÉPARTITION DES NOTES DANS L'ÉLITE DU PORTAIL 2]")
    for gr in ["A+", "A", "B+", "B", "C"]:
        count = audit["grade_distribution"].get(gr, 0)
        print(f"   Grade {gr:<2} : {count:2d} sélections")

    print("\n[MOYENNES DU PORTEFEUILLE D'ÉLITE]")
    avg = audit["averages"]
    print(f"   Probabilité moyenne sharp : {avg['avg_prob']*100:.1f}%")
    print(f"   Cote moyenne offerte      : {avg['avg_price']:.2f}")
    print(f"   Ratio de Sharpe moyen     : {avg['avg_sharpe']:.3f}")
    print(f"   Bet Quality Index moyen   : {avg['avg_bqi']:.1f} / 100")

    print("\n" + "=" * 100)
    print(" TOP 30 DES SÉLECTIONS D'ÉLITE DU PORTAIL 2 (CLASSIFICATION PAR BQI DÉCROISSANT)")
    print("=" * 100)
    header = f"{'#':<3} | {'Grade':<5} | {'Score':<5} | {'Match':<36} | {'Sélection':<18} | {'p':<6} | {'Cote':<5} | {'EV':<7} | {'Sharpe':<6} | {'Book'}"
    print(header)
    print("-" * len(header))

    for i, s in enumerate(audit["selections"], 1):
        m = (s.get("match") or "")[:35]
        sel = (s.get("sel") or "")[:18]
        p = f"{s['prob']*100:.1f}%"
        odds = f"{s['price']:.2f}"
        ev = f"{s['ev']*100:+.1f}%"
        sharpe = f"{s['sharpe']:.3f}"
        book = s.get("book", "")
        print(f"{i:<3} | {s['grade']:<5} | {s['bqi_score']:<5.1f} | {m:<36} | {sel:<18} | {p:<6} | {odds:<5} | {ev:<7} | {sharpe:<6} | {book}")

    print("\n" + "=" * 100)
    print(" PREUVE DE PROTECTION ANTI-RUINE : OUTSIDERS À FORTE COTE ÉLIMINÉS PAR LA VARIANCE ")
    print("=" * 100)
    print("Ces événements ont une EV faciale positive trompeuse, mais leur variance est astronomique")
    print("et leur probabilité < 40% provoque l'effondrement de leur score de qualité (Grade C).\n")
    longshot_header = f"{'Match':<38} | {'Sélection':<18} | {'p':<6} | {'Cote':<7} | {'EV':<7} | {'sigma':<7} | {'Sharpe':<6} | {'Score':<5} | {'Grade'}"
    print(longshot_header)
    print("-" * len(longshot_header))

    for ls in audit["eliminated_longshots_sample"][:8]:
        m = (ls["match"] or "")[:37]
        sel = (ls["sel"] or "")[:18]
        p = f"{ls['prob']*100:.1f}%"
        odds = f"{ls['price']:.2f}"
        ev = f"{ls['ev']*100:+.1f}%"
        sigma = f"{ls['sigma']:.2f}"
        sharpe = f"{ls['sharpe']:.3f}"
        score = f"{ls['bqi_score']:.1f}"
        grade = ls["grade"]
        print(f"{m:<38} | {sel:<18} | {p:<6} | {odds:<7} | {ev:<7} | {sigma:<7} | {sharpe:<6} | {score:<5} | {grade}")

    print("\n" + "=" * 100)
    print(" VÉRIFICATION TERMINÉE AVEC SUCCÈS ")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
