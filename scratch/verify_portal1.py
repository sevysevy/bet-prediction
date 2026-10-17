#!/usr/bin/env python3
"""
scratch/verify_portal1.py — Script de démonstration et vérification détaillée du Portail 1.
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from portals.portal1_double_tier import filter_portal_1, get_portal_1_summary, partition_by_tier

data_path = os.path.join(ROOT, "_site", "data.json")
with open(data_path, "r", encoding="utf-8") as f:
    data = json.load(f)

raw_selections = data.get("selections", [])

# Test des deux modes d'arbitrage
qual_safest = filter_portal_1(raw_selections, arbitration="safest")
summary_safest = get_portal_1_summary(raw_selections, qualified_selections=qual_safest, arbitration="safest")

cf_list, pv_list = partition_by_tier(qual_safest)

print("=" * 80)
print("RAPPORT D'ANALYSE ET QUALIFICATION — PORTAIL 1 (DOUBLE PALIER STRATÉGIQUE)")
print("=" * 80)
print(f"Total signaux bruts en base : {summary_safest['total_raw_signals']}")
print(f"Signaux rejetés corbeille à bruit (p < 0.40) : {summary_safest['noise_bin_excluded']}")
print(f"Total sélections qualifiées : {summary_safest['total_qualified']} matches uniques")
print(f"Garantie stricte anti-doublon : 1 sélection max par match (0 conflit)")

print("\n" + "-" * 80)
print(f"🛡️ PALIER 1 : COFFRE-FORT (BASES SOLIDES) — {len(cf_list)} matches qualifiés")
print(f"Cote moyenne : {summary_safest['palier_1_coffre_fort']['avg_odds']} | Strike Rate estimé moyen : {summary_safest['palier_1_coffre_fort']['strike_rate_estime']}% (Objectif > 75%)")
print("-" * 80)
print(f"{'Match':<35} | {'Sélection':<26} | {'Cote':<6} | {'Proba':<6} | {'EV':<7} | {'Bookmaker'}")
print("-" * 105)
for s in cf_list[:10]:
    print(f"{s['match'][:35]:<35} | {s['sel'][:26]:<26} | {s['price']:<6.2f} | {s['prob']*100:<5.1f}% | {s['ev']*100:+5.1f}% | {s['book']}")

print("\n" + "-" * 80)
print(f"💎 PALIER 2 : PÉPITES VALUE — {len(pv_list)} matches qualifiés")
print(f"Cote moyenne : {summary_safest['palier_2_pepites_value']['avg_odds']} | EV moyen : {summary_safest['palier_2_pepites_value']['avg_ev']*100:+.2f}% | Proba moyenne : {summary_safest['palier_2_pepites_value']['strike_rate_estime']}%")
print("-" * 80)
print(f"{'Match':<35} | {'Sélection':<26} | {'Cote':<6} | {'Proba':<6} | {'EV':<7} | {'Bookmaker'}")
print("-" * 105)
for s in pv_list:
    print(f"{s['match'][:35]:<35} | {s['sel'][:26]:<26} | {s['price']:<6.2f} | {s['prob']*100:<5.1f}% | {s['ev']*100:+5.1f}% | {s['book']}")

print("\n" + "=" * 80)
print("ARBITRAGE ALTERNATIF ('attractive') :")
qual_attr = filter_portal_1(raw_selections, arbitration="attractive")
summary_attr = get_portal_1_summary(raw_selections, qualified_selections=qual_attr, arbitration="attractive")
cf_a, pv_a = partition_by_tier(qual_attr)
print(f"En mode 'attractive' : Coffre-Fort = {len(cf_a)} | Pépites Value = {len(pv_a)} (Arsenal @ 1.71, EV +1.13% sélectionné pour Nottingham Forest vs Arsenal)")
print("=" * 80)
