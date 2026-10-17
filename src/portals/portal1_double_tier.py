#!/usr/bin/env python3
"""
portal1_double_tier.py — Moteur de filtrage pour le Portail 1 : Double Palier Stratégique.

Architecture du Portail 1 :
1. Palier 1 'Coffre-Fort' (Bases Solides) :
   - Probabilité sharp p >= 0.65 (65%)
   - Cote >= 1.25
   - Taux de victoire cible > 75%
   - Sélection axée sur la résilience maximale et la sécurité de bankroll.

2. Palier 2 'Pépites Value' :
   - Probabilité sharp 0.45 <= p < 0.65 (45% à 65%)
   - Espérance mathématique positive EV > +0.01 (+1%)
   - Cote comprise entre 1.50 et 2.30
   - Sélection axée sur l'injustice de cote et l'edge mathématique net.

3. Corbeille à bruit :
   - Exclusion stricte de toute sélection avec p < 0.40 (40%).

4. Règle de sélection anti-doublon par match :
   - 1 seule sélection maximale par match (la plus sûre ou la plus attractive selon l'arbitrage).
   - Exclusion stricte de tout conflit ou doublon 1/N/2 ou marchés multiples sur le même événement.

5. Ré-inclusion dynamique :
   - Algorithme fonctionnel et pur, ré-évaluant l'intégralité du board à chaque cycle de rafraîchissement.
   - Dès qu'un match lointain voit ses cotes/probabilités mûrir (hausse de liquidité, affinement Pinnacle),
     il est ré-inclus automatiquement sans intervention manuelle.
"""
from __future__ import annotations

import copy
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# Constantes des seuils stratégiques du Portail 1
COFFRE_FORT_MIN_PROB: float = 0.65
COFFRE_FORT_MIN_ODDS: float = 1.25
COFFRE_FORT_TARGET_WINRATE: float = 0.75

PEPITE_MIN_PROB: float = 0.45
PEPITE_MAX_PROB: float = 0.65
PEPITE_MIN_EV: float = 0.01
PEPITE_MIN_ODDS: float = 1.50
PEPITE_MAX_ODDS: float = 2.30

NOISE_PROB_THRESHOLD: float = 0.40

# Badges et labels visuels
BADGE_COFFRE_FORT: str = "🛡️ Coffre-Fort"
LABEL_COFFRE_FORT: str = "Bases Solides"

BADGE_PEPITE_VALUE: str = "💎 Pépites Value"
LABEL_PEPITE_VALUE: str = "Pépites Value"


def normalize_team_key(name: str) -> str:
    """
    Normalise le nom d'une équipe pour aligner les différentes sources de cotes
    (OddsPapi, TheOddsAPI, Pinnacle, etc.) et garantir l'unicité de chaque match.
    """
    s = str(name or "").lower().strip()
    s = re.sub(r"\bst\b", "saint", s)
    s = re.sub(r"\butd\b", "united", s)
    s = re.sub(r"\bman\b", "manchester", s)
    s = re.sub(r"\bsg\b", "saint germain", s)
    s = re.sub(r"\b(fc|cf|osc|rc|as|ac|ss|rb|fsv|sc|us|ogc|vfl|bvb|afc)\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def get_match_dedup_key(sel: Dict[str, Any]) -> str:
    """
    Génère une clé d'identification canonique pour un match.
    Empêche les doublons issus de marchés différents ou de flux multi-sources
    sur la même rencontre sportive.
    """
    match_str = str(sel.get("match") or "").strip()
    ko_date = str(sel.get("kickoff") or "")[:10]

    if " - " in match_str:
        parts = match_str.split(" - ", 1)
        h_clean = normalize_team_key(parts[0])
        a_clean = normalize_team_key(parts[1])
        if h_clean and a_clean:
            return f"{h_clean}_vs_{a_clean}_{ko_date}"

    # Repli sur match_id si disponible
    mid = sel.get("match_id")
    if mid:
        return f"id_{mid}_{ko_date}"

    return f"raw_{match_str}_{ko_date}"


def classify_selection(
    sel: Dict[str, Any],
    min_prob_cf: float = COFFRE_FORT_MIN_PROB,
    min_odds_cf: float = COFFRE_FORT_MIN_ODDS,
    min_prob_pv: float = PEPITE_MIN_PROB,
    max_prob_pv: float = PEPITE_MAX_PROB,
    min_ev_pv: float = PEPITE_MIN_EV,
    min_odds_pv: float = PEPITE_MIN_ODDS,
    max_odds_pv: float = PEPITE_MAX_ODDS,
    noise_threshold: float = NOISE_PROB_THRESHOLD,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Évalue une sélection individuelle et détermine si elle appartient à :
    - 'coffre_fort' : Palier 1
    - 'pepite_value' : Palier 2
    - None : Non retenu (bruit, hors critères ou données invalides).
    """
    prob = sel.get("prob")
    price = sel.get("price")
    ev = sel.get("ev")

    # Rejet des sélections aux données manquantes ou cotes aberrantes
    if prob is None or price is None or price <= 1.0:
        return None, None

    # Corbeille à bruit : exclusion stricte de toute sélection avec p < 0.40
    if prob < noise_threshold:
        return None, None

    # 1. Palier 1 'Coffre-Fort' (Bases Solides) : p >= 0.65, cote >= 1.25
    if prob >= min_prob_cf and price >= min_odds_cf:
        meta = {
            "tier": "coffre_fort",
            "tier_rank": 1,
            "badge": BADGE_COFFRE_FORT,
            "label": LABEL_COFFRE_FORT,
            "strike_rate_estime": round(float(prob) * 100, 1),
            "strike_rate_target": "> 75%",
        }
        return "coffre_fort", meta

    # 2. Palier 2 'Pépites Value' : 0.45 <= p < 0.65, EV > +0.01, 1.50 <= cote <= 2.30
    # Tolérance epsilon 1e-9 pour la comparaison flottante de l'EV
    ev_val = float(ev if ev is not None else -1.0)
    if (min_prob_pv <= prob < max_prob_pv) and (ev_val > min_ev_pv - 1e-9) and (min_odds_pv <= price <= max_odds_pv):
        meta = {
            "tier": "pepite_value",
            "tier_rank": 2,
            "badge": BADGE_PEPITE_VALUE,
            "label": LABEL_PEPITE_VALUE,
            "strike_rate_estime": round(float(prob) * 100, 1),
            "strike_rate_target": "> 50%",
        }
        return "pepite_value", meta

    return None, None


def filter_portal_1(
    selections: List[Dict[str, Any]],
    arbitration: str = "safest",
    min_prob_cf: float = COFFRE_FORT_MIN_PROB,
    min_odds_cf: float = COFFRE_FORT_MIN_ODDS,
    min_prob_pv: float = PEPITE_MIN_PROB,
    max_prob_pv: float = PEPITE_MAX_PROB,
    min_ev_pv: float = PEPITE_MIN_EV,
    min_odds_pv: float = PEPITE_MIN_ODDS,
    max_odds_pv: float = PEPITE_MAX_ODDS,
    noise_threshold: float = NOISE_PROB_THRESHOLD,
    sort_by: str = "tier",
) -> List[Dict[str, Any]]:
    """
    Filtre et sélectionne les meilleures opportunités pour le Portail 1 :
    Double Palier Stratégique (Coffre-Fort + Pépites Value).

    Paramètres :
        selections: Liste des sélections brutes (dictionnaires de paris).
        arbitration: Règle d'arbitrage en cas de sélections multiples pour un même match :
            - 'safest' (défaut) : Privilégie la plus sûre (plus forte probabilité sharp, Palier 1 prioritaire).
            - 'attractive' : Privilégie la plus attractive (plus forte EV positive, Palier 2 prioritaire).
            - 'by_tier' : Retient jusqu'à 1 sélection par match et par palier.
        sort_by: Tri du résultat ('tier', 'prob', 'ev', 'kickoff').

    Retourne :
        Liste des sélections qualifiées enrichies de leurs métadonnées de palier :
        'tier', 'badge', 'label', 'strike_rate_estime', 'strike_rate_target'.
    """
    if not selections:
        return []

    # 1. Évaluation et regroupement par match
    # Structure : match_key -> liste de (selection_copy, tier, metadata)
    candidates_by_match: Dict[str, List[Tuple[Dict[str, Any], str, Dict[str, Any]]]] = defaultdict(list)

    for sel in selections:
        tier, meta = classify_selection(
            sel,
            min_prob_cf=min_prob_cf,
            min_odds_cf=min_odds_cf,
            min_prob_pv=min_prob_pv,
            max_prob_pv=max_prob_pv,
            min_ev_pv=min_ev_pv,
            min_odds_pv=min_odds_pv,
            max_odds_pv=max_odds_pv,
            noise_threshold=noise_threshold,
        )
        if tier and meta:
            mk = get_match_dedup_key(sel)
            candidates_by_match[mk].append((copy.deepcopy(sel), tier, meta))

    qualified: List[Dict[str, Any]] = []

    # 2. Application de la règle de sélection unique par match
    for mk, candidates in candidates_by_match.items():
        if arbitration == "by_tier":
            # 1 sélection max par palier pour ce match
            cands_cf = [c for c in candidates if c[1] == "coffre_fort"]
            cands_pv = [c for c in candidates if c[1] == "pepite_value"]
            if cands_cf:
                best_cf = sorted(
                    cands_cf,
                    key=lambda x: (x[0].get("prob") or 0.0, x[0].get("ev") or 0.0, x[0].get("price") or 0.0),
                    reverse=True,
                )[0]
                item, t, m = best_cf
                item.update(m)
                qualified.append(item)
            if cands_pv:
                best_pv = sorted(
                    cands_pv,
                    key=lambda x: (x[0].get("ev") or 0.0, x[0].get("prob") or 0.0, x[0].get("price") or 0.0),
                    reverse=True,
                )[0]
                item, t, m = best_pv
                item.update(m)
                qualified.append(item)

        elif arbitration == "attractive":
            # Priorité à l'attractivité (Pépites Value d'abord, puis max EV, max prob)
            best = sorted(
                candidates,
                key=lambda x: (
                    1 if x[1] == "pepite_value" else 0,
                    x[0].get("ev") or 0.0,
                    x[0].get("prob") or 0.0,
                    x[0].get("price") or 0.0,
                ),
                reverse=True,
            )[0]
            item, t, m = best
            item.update(m)
            item["arbitration_applied"] = "most_attractive"
            qualified.append(item)

        else:
            # Mode 'safest' (défaut) : priorité à la sécurité (Coffre-Fort d'abord, puis max prob, max EV)
            best = sorted(
                candidates,
                key=lambda x: (
                    1 if x[1] == "coffre_fort" else 0,
                    x[0].get("prob") or 0.0,
                    x[0].get("ev") or 0.0,
                    x[0].get("price") or 0.0,
                ),
                reverse=True,
            )[0]
            item, t, m = best
            item.update(m)
            item["arbitration_applied"] = "safest"
            qualified.append(item)

    # 3. Tri final des sélections
    if sort_by == "prob":
        qualified.sort(key=lambda x: (x.get("prob") or 0.0), reverse=True)
    elif sort_by == "ev":
        qualified.sort(key=lambda x: (x.get("ev") or 0.0), reverse=True)
    elif sort_by == "kickoff":
        qualified.sort(key=lambda x: (str(x.get("kickoff") or "")))
    else:
        # Tri par défaut par Palier (Coffre-Fort puis Pépites Value), puis par pertinence interne
        cf_list = [q for q in qualified if q["tier"] == "coffre_fort"]
        pv_list = [q for q in qualified if q["tier"] == "pepite_value"]

        cf_list.sort(key=lambda x: (x.get("prob") or 0.0, x.get("price") or 0.0), reverse=True)
        pv_list.sort(key=lambda x: (x.get("ev") or 0.0, x.get("prob") or 0.0), reverse=True)
        qualified = cf_list + pv_list

    return qualified


def partition_by_tier(qualified_selections: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Sépare les sélections qualifiées du Portail 1 en deux sous-listes :
    (coffre_fort, pepites_value).
    """
    coffre_fort = [s for s in qualified_selections if s.get("tier") == "coffre_fort"]
    pepites_value = [s for s in qualified_selections if s.get("tier") == "pepite_value"]
    return coffre_fort, pepites_value


def get_portal_1_summary(
    selections: List[Dict[str, Any]],
    qualified_selections: Optional[List[Dict[str, Any]]] = None,
    arbitration: str = "safest",
) -> Dict[str, Any]:
    """
    Calcule la synthèse statistique complète pour le Portail 1 :
    comptages, moyennes de cotes, probabilités, EV et indicateurs de performance.
    """
    total_raw = len(selections)
    noise_count = sum(1 for s in selections if (s.get("prob") or 0.0) < NOISE_PROB_THRESHOLD)

    if qualified_selections is None:
        qualified = filter_portal_1(selections, arbitration=arbitration)
    else:
        qualified = qualified_selections

    cf_list, pv_list = partition_by_tier(qualified)

    def _calc_stats(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not subset:
            return {
                "count": 0,
                "avg_odds": 0.0,
                "avg_prob": 0.0,
                "avg_ev": 0.0,
                "strike_rate_estime": 0.0,
            }
        n = len(subset)
        avg_odds = sum(s.get("price") or 0.0 for s in subset) / n
        avg_prob = sum(s.get("prob") or 0.0 for s in subset) / n
        avg_ev = sum(s.get("ev") or 0.0 for s in subset) / n
        return {
            "count": n,
            "avg_odds": round(avg_odds, 3),
            "avg_prob": round(avg_prob, 4),
            "avg_ev": round(avg_ev, 4),
            "strike_rate_estime": round(avg_prob * 100, 1),
        }

    cf_stats = _calc_stats(cf_list)
    cf_stats["target_winrate"] = "> 75%"
    cf_stats["target_met"] = cf_stats["avg_prob"] >= 0.70  # Conforme à la fourchette haute

    pv_stats = _calc_stats(pv_list)
    pv_stats["target_min_ev"] = "+1.0%"
    pv_stats["all_positive_ev"] = all((s.get("ev") or 0.0) > 0.01 for s in pv_list) if pv_list else True

    return {
        "portal": "Portail 1 - Double Palier Stratégique",
        "arbitration_mode": arbitration,
        "total_raw_signals": total_raw,
        "noise_bin_excluded": noise_count,
        "total_qualified": len(qualified),
        "unique_matches_count": len(set(get_match_dedup_key(s) for s in qualified)),
        "palier_1_coffre_fort": cf_stats,
        "palier_2_pepites_value": pv_stats,
    }


if __name__ == "__main__":
    import json
    import os

    # Démonstration et vérification locale si exécuté directement
    sys.stdout.reconfigure(encoding="utf-8")
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_site", "data.json")

    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_sels = data.get("selections", [])
        summary = get_portal_1_summary(raw_sels)
        print("=== SYNTHÈSE PORTAIL 1 (_site/data.json) ===")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"Fichier non trouvé : {data_path}")
