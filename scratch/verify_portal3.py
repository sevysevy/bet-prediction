"""
verify_portal3.py — Script de vérification et de démonstration du Portail 3.
Applique le Filtre Dur Sécuritaire (Option 3) sur _site/data.json et affiche le rapport détaillé.
"""

import os
import sys
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.portals.portal3_hard_filter import (
    filter_portal_3,
    audit_portal_3,
    DEFAULT_MIN_PROB,
    DEFAULT_MIN_ODDS,
    DEFAULT_MAX_ODDS,
    DEFAULT_MIN_EV,
    DEFAULT_MAX_SHARP_MARGIN,
)


def main():
    data_path = os.path.join(ROOT, "_site", "data.json")
    if not os.path.exists(data_path):
        print(f"Erreur : fichier {data_path} introuvable.")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    selections = data.get("selections", [])
    print("=" * 80)
    print(" PORTAIL 3 : OPTION 3 (FILTRE DUR SÉCURITAIRE / ANTI-BRUIT STRICT)")
    print("=" * 80)
    print(f"Total sélections ingérées : {len(selections)}")
    print(f"Critères durs sans compromis :")
    print(f"  - Probabilité sharp p >= {DEFAULT_MIN_PROB * 100:.0f}%")
    print(f"  - Cote comprise entre {DEFAULT_MIN_ODDS:.2f} et {DEFAULT_MAX_ODDS:.2f}")
    print(f"  - Espérance mathématique EV >= {DEFAULT_MIN_EV * 100:+.1f}%")
    print(f"  - Marge sharp benchmark <= {DEFAULT_MAX_SHARP_MARGIN * 100:.1f}%")
    print(f"  - Règle 1 match = 1 sélection d'élite")
    print("-" * 80)

    # Audit global
    audit = audit_portal_3(selections)
    print(f"\nRÉSULTATS DU FILTRAGE GLOBAL :")
    print(f"  - Sélections candidates brutes qualifiées : {audit['qualified_raw']}")
    print(f"  - Matches uniques retenus : {audit['final_retained']}")
    print(f"  - Déduplications intra-match : {audit['deduplicated_by_match']}")
    print(f"\nMOTIFS DE REJET :")
    for cat, count in sorted(audit["rejections_by_category"].items(), key=lambda x: -x[1]):
        print(f"  - {cat:<25} : {count} sélections exclues")

    # Affichage des matches retenus
    retained = audit["selections"]
    print(f"\nSÉLECTIONS D'ÉLITE QUALIFIÉES ({len(retained)}) :")
    print("-" * 80)
    header = f"{'Statut':<10} | {'Match':<38} | {'Pari':<22} | {'Cote':<5} | {'Prob':<6} | {'EV':<7} | {'Marge':<6} | {'Sharp'}"
    print(header)
    print("-" * 80)
    for s in retained:
        status = s.get("status", "N/A")
        match = s.get("match", "N/A")[:38]
        sel = s.get("sel", "N/A")[:22]
        price = f"{s.get('price', 0):.2f}"
        prob = f"{s.get('prob', 0)*100:.1f}%"
        ev = f"{s.get('ev', 0)*100:+.2f}%"
        margin = f"{s.get('sharp_margin', 0)*100:.2f}%"
        sharp = s.get("sharp", "N/A")
        print(f"{status:<10} | {match:<38} | {sel:<22} | {price:<5} | {prob:<6} | {ev:<7} | {margin:<6} | {sharp}")
    print("-" * 80)

    # Focus sur les matches à venir (UPCOMING)
    upcoming_audit = audit_portal_3(selections, status_filter="UPCOMING")
    upcoming_retained = upcoming_audit["selections"]
    print(f"\nFOCUS MATCHES À VENIR (UPCOMING) ({len(upcoming_retained)}) :")
    for i, s in enumerate(upcoming_retained, 1):
        print(f"  {i}. [{s.get('league')}] {s.get('match')}")
        print(f"     -> Sélection : {s.get('sel')} @ {s.get('price')} ({s.get('book')})")
        print(f"     -> Probabilité Sharp : {s.get('prob')*100:.2f}% | EV : {s.get('ev')*100:+.2f}% | Marge Sharp : {s.get('sharp_margin')*100:.2f}% ({s.get('sharp')})")
        print(f"     -> Coup d'envoi : {s.get('kickoff')}")
    print("=" * 80)


if __name__ == "__main__":
    main()
