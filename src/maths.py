"""
maths.py — Fonctions mathématiques, dévigorisation, espérance de gain (EV) et critère de Kelly.

Garantit le respect des contraintes scientifiques (C2, C4, C8) :
- Dévigorisation par probabilités normalisées (et méthodes alternatives)
- Calcul de marge réelle et d'EV
- Critère de Kelly fractionnaire (Quarter Kelly, Half Kelly) avec plafonnement du risque
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple


def devig_multiplicative(prices: Dict[str, float]) -> Dict[str, any]:
    """
    Dévigorisation standard (probabilités normalisées) :
    p_i = (1 / o_i) / sum(1 / o_k)
    Marge (overround - 1) : sum(1 / o_k) - 1.0
    """
    inv = {}
    for k, v in prices.items():
        if v and v > 1.0:
            inv[k] = 1.0 / float(v)
    if not inv:
        return {"margin": 0.0, "probs": {}}
    over = sum(inv.values())
    probs = {k: v / over for k, v in inv.items()}
    return {
        "margin": over - 1.0,
        "overround": over,
        "probs": probs
    }


def devig_power(prices: Dict[str, float], tol: float = 1e-6, max_iter: int = 100) -> Dict[str, any]:
    """
    Dévigorisation par méthode des puissances (Power model) :
    Résout k tel que sum((1 / o_i)^k) = 1.0.
    Atténue le biais favori-outsider (Favorite-Longshot Bias - FLB).
    Si convergence impossible, repli sur devig_multiplicative.
    """
    inv = {k: 1.0 / float(v) for k, v in prices.items() if v and v > 1.0}
    if len(inv) < 2:
        return devig_multiplicative(prices)

    over = sum(inv.values())
    if abs(over - 1.0) < tol:
        return {"margin": 0.0, "overround": 1.0, "probs": inv}

    # Recherche dichotomique de k
    k_min, k_max = 0.5, 4.0
    k_curr = 1.0
    for _ in range(max_iter):
        k_curr = 0.5 * (k_min + k_max)
        s = sum(p ** k_curr for p in inv.values())
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            k_min = k_curr
        else:
            k_max = k_curr

    raw_probs = {k: p ** k_curr for k, p in inv.items()}
    s_norm = sum(raw_probs.values())
    probs = {k: v / s_norm for k, v in raw_probs.items()}
    return {
        "margin": over - 1.0,
        "overround": over,
        "k_power": k_curr,
        "probs": probs
    }


def compute_ev(prob: float, odds: float) -> float:
    """
    Espérance de gain (EV) par euro misé :
    EV = (prob * odds) - 1.0
    Exemple : prob = 0.80, odds = 1.30 -> EV = 0.80 * 1.30 - 1 = +0.04 (+4.0%)
    """
    if prob <= 0 or odds <= 1.0:
        return -1.0
    return (prob * odds) - 1.0


def kelly_fraction(prob: float, odds: float, fraction: float = 0.25, max_stake_pct: float = 0.05) -> float:
    """
    Critère de Kelly fractionnaire (C8) :
    f* = (p * (b) - (1 - p)) / b = (p * b - q) / b  où b = odds - 1.
    fraction = 0.25 pour Quarter-Kelly (recommandé en raison du bruit de calibration ECE).
    Plafonné à max_stake_pct (5% par défaut).
    Renvoie le pourcentage de la bankroll recommandé (ex: 0.021 = 2.1%).
    """
    if prob <= 0 or odds <= 1.0 or prob >= 1.0:
        return 0.0
    b = odds - 1.0
    q = 1.0 - prob
    f_star = (prob * b - q) / b
    if f_star <= 0:
        return 0.0
    stake = f_star * fraction
    return min(stake, max_stake_pct)


def compound_combination(legs: List[Dict[str, any]], book_name: Optional[str] = None) -> Optional[Dict[str, any]]:
    """
    Calcule le combiné pour un ensemble de sélections :
    - probabilité composée = produit des probabilités équitables (hypothèse d'indépendance)
    - cote composée = produit des cotes chez un même bookmaker
    - EV composée = prob * odds - 1
    """
    if not legs or len(legs) < 2:
        return None

    # Vérification d'indépendance élémentaire : pas deux sélections du même match
    matches = [l.get("match") for l in legs if l.get("match")]
    if len(matches) != len(set(matches)):
        return None

    prob = 1.0
    for l in legs:
        prob *= float(l["prob"])

    # Recherche des bookmakers communs
    books_available = set(legs[0].get("prices", {}).keys())
    for l in legs[1:]:
        books_available &= set(l.get("prices", {}).keys())

    if not books_available:
        return None

    target_book = book_name if (book_name and book_name in books_available) else None
    if not target_book:
        # Sélection du bookmaker offrant la meilleure cote combinée
        best_bk = None
        best_odds = 0.0
        for bk in books_available:
            o = 1.0
            for l in legs:
                o *= l["prices"][bk]
            if o > best_odds:
                best_odds = o
                best_bk = bk
        target_book = best_bk

    total_odds = 1.0
    for l in legs:
        total_odds *= legs[0]["prices"][target_book] if l is legs[0] else l["prices"][target_book]

    ev = (prob * total_odds) - 1.0
    kelly_quarter = kelly_fraction(prob, total_odds, fraction=0.25)

    return {
        "n": len(legs),
        "prob": prob,
        "odds": total_odds,
        "book": target_book,
        "ev": ev,
        "kelly_quarter": kelly_quarter,
        "legs": legs,
        "leg_labels": [f"{l.get('match', '')}: {l.get('sel', '')}" for l in legs]
    }
