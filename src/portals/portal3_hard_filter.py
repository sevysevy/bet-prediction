"""
portal3_hard_filter.py — Portail 3 : Option 3 (Filtre Dur Sécuritaire / Anti-Bruit Strict).

Ce module implémente une stratégie de filtrage sans compromis conçue pour :
1. Éliminer le bruit et la variance excessive des cotes élevées / outsiders.
2. Éviter les micro-cotes stériles (< 1.35) qui détruisent le capital en cas d'accident.
3. Garantir un Strike Rate élevé (p >= 55%) avec une espérance mathématique positive ou neutre (EV >= 0.0%).
4. Exiger une liquidité et une efficience de marché irréprochables (marge sharp benchmark Pinnacle / Exchange <= 5%).
5. Assurer strictement 1 seule sélection par match (sélection d'élite maximale).
6. Permettre une ré-inclusion dynamique : évaluation sans état (stateless) à chaque pull en temps réel.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


# Seuils stricts du Portail 3
DEFAULT_MIN_PROB: float = 0.55        # Probabilité sharp minimum (>= 55%)
DEFAULT_MIN_ODDS: float = 1.35        # Cote minimale (élimine les micro-cotes < 1.35)
DEFAULT_MAX_ODDS: float = 2.30        # Cote maximale (élimine les cotes trop risquées > 2.30)
DEFAULT_MIN_EV: float = 0.0           # Espérance mathématique positive ou nulle (EV >= 0.0%)
DEFAULT_MAX_SHARP_MARGIN: float = 0.05 # Marge benchmark sharp maximum (<= 5.0%)


def evaluate_candidate(
    sel: Dict[str, Any],
    min_prob: float = DEFAULT_MIN_PROB,
    min_odds: float = DEFAULT_MIN_ODDS,
    max_odds: float = DEFAULT_MAX_ODDS,
    min_ev: float = DEFAULT_MIN_EV,
    max_sharp_margin: float = DEFAULT_MAX_SHARP_MARGIN,
    require_sharp_margin: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Évalue si une sélection remplit l'ensemble des règles dures du Portail 3.

    Retourne :
        (True, None) si la sélection est acceptée.
        (False, motif) si elle est rejetée, avec la raison précise du rejet.
    """
    if not isinstance(sel, dict):
        return False, "format_invalide"

    # 1. Règle Probabilité : p >= 55%
    prob = sel.get("prob")
    if prob is None or not isinstance(prob, (int, float)):
        return False, "prob_manquante"
    if prob < min_prob:
        return False, f"prob_insuffisante_{prob:.3f}_inf_{min_prob}"

    # 2. Règle Cote : 1.35 <= price <= 2.30
    price = sel.get("price")
    if price is None or not isinstance(price, (int, float)):
        return False, "cote_manquante"
    if price < min_odds:
        return False, f"cote_trop_faible_{price:.2f}_inf_{min_odds}"
    if price > max_odds:
        return False, f"cote_trop_elevee_{price:.2f}_sup_{max_odds}"

    # 3. Règle EV : EV >= 0.0%
    ev = sel.get("ev")
    if ev is None or not isinstance(ev, (int, float)):
        # Calcul de repli EV = (p * price) - 1.0
        ev = (prob * price) - 1.0
    if ev < min_ev:
        return False, f"ev_negative_{ev:+.4f}_inf_{min_ev}"

    # 4. Règle Marge Sharp : margin <= 0.05
    sharp_margin = sel.get("sharp_margin")
    if sharp_margin is not None and isinstance(sharp_margin, (int, float)):
        if sharp_margin > max_sharp_margin:
            return False, f"marge_sharp_excessive_{sharp_margin:.4f}_sup_{max_sharp_margin}"
    elif require_sharp_margin:
        return False, "marge_sharp_manquante"

    return True, None


def get_match_key(sel: Dict[str, Any]) -> str:
    """
    Extrait une clé d'identification unique pour un match donné.
    Priorité : match_id > event_id sans suffixe de marché > match > home_away.
    """
    if sel.get("match_id"):
        return str(sel["match_id"])
    if sel.get("match"):
        return str(sel["match"]).strip().lower()
    event_id = str(sel.get("event_id") or "")
    if event_id:
        # Retire d'éventuels suffixes de type '_dnb', '_1x2', etc.
        for suf in ("_dnb", "_1x2", "_ou25", "_ou15", "_ou35", "_btts"):
            if event_id.endswith(suf):
                return event_id[:-len(suf)]
        return event_id
    home = str(sel.get("home_team") or sel.get("home") or "").strip().lower()
    away = str(sel.get("away_team") or sel.get("away") or "").strip().lower()
    if home and away:
        return f"{home}_vs_{away}"
    return id(sel)


def _selection_rank_tuple(sel: Dict[str, Any], rank_by: str = "ev") -> Tuple:
    """
    Construit un tuple ordonnable pour désigner la meilleure sélection d'un match.
    Plus le tuple est grand, plus la sélection est prioritaire.
    """
    ev = float(sel.get("ev") or ((sel.get("prob", 0.0) * sel.get("price", 1.0)) - 1.0))
    prob = float(sel.get("prob") or 0.0)
    kelly = float(sel.get("kelly_quarter") or 0.0)
    price = float(sel.get("price") or 1.0)

    if rank_by == "prob":
        # Priorité absolue au taux de réussite, puis EV
        return (prob, ev, kelly, price)
    elif rank_by == "kelly":
        # Priorité au dimensionnement Quarter-Kelly, puis EV, puis prob
        return (kelly, ev, prob, price)
    else:
        # Par défaut "ev" : Maximisation de l'espérance de gain, puis prob, puis kelly
        return (ev, prob, kelly, price)


def filter_portal_3(
    selections: List[Dict[str, Any]],
    min_prob: float = DEFAULT_MIN_PROB,
    min_odds: float = DEFAULT_MIN_ODDS,
    max_odds: float = DEFAULT_MAX_ODDS,
    min_ev: float = DEFAULT_MIN_EV,
    max_sharp_margin: float = DEFAULT_MAX_SHARP_MARGIN,
    one_per_match: bool = True,
    rank_by: str = "ev",
    status_filter: Optional[str | List[str]] = None,
    require_sharp_margin: bool = False,
) -> List[Dict[str, Any]]:
    """
    Filtre les sélections selon les critères durs du Portail 3 :
    - Probabilité sharp p >= 0.55
    - Cote offerte comprise entre 1.35 et 2.30
    - EV >= 0.0%
    - Marge sharp benchmark <= 0.05 (Pinnacle / Exchange liquide)
    - 1 seule sélection par match (meilleure sélection selon rank_by)
    - Ré-inclusion dynamique : évaluation sans état à chaque appel

    Arguments :
        selections: Liste des sélections candidates (depuis data.json ou le flux en direct)
        min_prob: Seuil de probabilité minimal (défaut 0.55)
        min_odds: Cote minimale admissible (défaut 1.35)
        max_odds: Cote maximale admissible (défaut 2.30)
        min_ev: Espérance minimale admissible (défaut 0.0%)
        max_sharp_margin: Marge bookmaker de référence maximale (défaut 0.05)
        one_per_match: Si True, conserve uniquement la meilleure sélection par match
        rank_by: Critère de sélection intra-match ("ev", "prob", "kelly")
        status_filter: Optionnel, filtre de statut (ex: 'UPCOMING' ou ['UPCOMING', 'LIVE'])
        require_sharp_margin: Si True, rejette toute sélection sans marge sharp explicite

    Retourne :
        Liste ordonnée des sélections d'élite qualifiées pour le Portail 3.
    """
    if not selections:
        return []

    # Normalisation du filtre de statut si spécifié
    allowed_statuses = None
    if status_filter:
        if isinstance(status_filter, str):
            allowed_statuses = {status_filter.upper()}
        else:
            allowed_statuses = {s.upper() for s in status_filter}

    # 1. Première passe : validation unitaire des critères durs
    qualified: List[Dict[str, Any]] = []
    for s in selections:
        if allowed_statuses:
            s_status = str(s.get("status") or "").upper()
            if s_status not in allowed_statuses:
                continue

        ok, _ = evaluate_candidate(
            s,
            min_prob=min_prob,
            min_odds=min_odds,
            max_odds=max_odds,
            min_ev=min_ev,
            max_sharp_margin=max_sharp_margin,
            require_sharp_margin=require_sharp_margin,
        )
        if ok:
            qualified.append(s)

    # 2. Règle intra-match : 1 seule sélection par match
    if one_per_match and qualified:
        by_match = defaultdict(list)
        for s in qualified:
            m_key = get_match_key(s)
            by_match[m_key].append(s)

        selected_per_match: List[Dict[str, Any]] = []
        for m_key, match_sels in by_match.items():
            best_sel = max(match_sels, key=lambda x: _selection_rank_tuple(x, rank_by=rank_by))
            selected_per_match.append(best_sel)
        qualified = selected_per_match

    # 3. Tri final décroissant par qualité d'espérance / probabilité
    qualified.sort(
        key=lambda x: _selection_rank_tuple(x, rank_by=rank_by),
        reverse=True,
    )

    return qualified


def audit_portal_3(
    selections: List[Dict[str, Any]],
    min_prob: float = DEFAULT_MIN_PROB,
    min_odds: float = DEFAULT_MIN_ODDS,
    max_odds: float = DEFAULT_MAX_ODDS,
    min_ev: float = DEFAULT_MIN_EV,
    max_sharp_margin: float = DEFAULT_MAX_SHARP_MARGIN,
    one_per_match: bool = True,
    rank_by: str = "ev",
    status_filter: Optional[str | List[str]] = None,
) -> Dict[str, Any]:
    """
    Fournit un audit complet et transparent de l'effet de chaque filtre dur du Portail 3.
    """
    total = len(selections)
    rejection_counts = defaultdict(int)
    qualified_candidates = []

    allowed_statuses = None
    if status_filter:
        if isinstance(status_filter, str):
            allowed_statuses = {status_filter.upper()}
        else:
            allowed_statuses = {s.upper() for s in status_filter}

    for s in selections:
        if allowed_statuses:
            s_status = str(s.get("status") or "").upper()
            if s_status not in allowed_statuses:
                rejection_counts["statut_ignore"] += 1
                continue

        ok, reason = evaluate_candidate(
            s,
            min_prob=min_prob,
            min_odds=min_odds,
            max_odds=max_odds,
            min_ev=min_ev,
            max_sharp_margin=max_sharp_margin,
        )
        if ok:
            qualified_candidates.append(s)
        else:
            category = reason.split("_")[0] if reason else "autre"
            rejection_counts[category] += 1

    final_selections = filter_portal_3(
        selections,
        min_prob=min_prob,
        min_odds=min_odds,
        max_odds=max_odds,
        min_ev=min_ev,
        max_sharp_margin=max_sharp_margin,
        one_per_match=one_per_match,
        rank_by=rank_by,
        status_filter=status_filter,
    )

    deduplicated_count = len(qualified_candidates) - len(final_selections) if one_per_match else 0

    return {
        "total_inputs": total,
        "qualified_raw": len(qualified_candidates),
        "final_retained": len(final_selections),
        "deduplicated_by_match": deduplicated_count,
        "rejections_by_category": dict(rejection_counts),
        "selections": final_selections,
    }
