"""
portal2_sharpe.py — Portail 2 : Option 2 (Ratio de Sharpe Sportif / Score de Croissance Markowitz-Kelly).

Ce module implémente une approche quantitative basée sur la théorie moderne du portefeuille (Markowitz)
et le critère de Kelly pour évaluer et filtrer les paris sportifs :
1. Calcul de la variance du gain :
   sigma = sqrt(p * (1 - p)) * (price - 1)
   Cette métrique capture fidèlement l'explosion du risque sur les cotes élevées.
2. Ratio de Sharpe sportif :
   Sharpe = EV / sigma
   Mesure l'espérance de gain par unité de risque (volatilité).
3. Score de Croissance Markowitz-Kelly :
   g(f*) ~ 0.5 * Sharpe^2 (taux de croissance composé logarithmique du capital).
4. Fonction de pénalisation abrupte pour p < 0.40 :
   Le score s'effondre polynomialement (p / 0.40)^6 pour éradiquer tout bruit de loterie (cotes à 1%).
5. Normalisation en Bet Quality Index (BQI) sur [0, 100] via saturation exponentielle :
   BQI = 100 * (1 - exp(-k * PenalizedSharpe))
6. Attribution de notes qualitatives :
   - A+ : BQI >= 80 (Opportunités d'élite, Sharpe exceptionnel, variance maîtrisée)
   - A  : 65 <= BQI < 80 (Haute qualité, excellent compromis rendement/risque)
   - B+ : 50 <= BQI < 65 (Opportunités solides, valeur confirmée)
   - B  : 35 <= BQI < 50 (Opportunités modérées / secondaires)
   - C  : BQI < 35 (Faible rendement ajusté au risque ou bruit rejeté)
7. Règle intra-match : strictement 1 seule sélection par match (maximisant le BQI).
8. Ré-inclusion dynamique : évaluation purement fonctionnelle et sans état (stateless)
   garantissant une mise à jour instantanée à chaque cycle de données.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


# Paramètres par défaut calibrés pour les marchés sportifs
DEFAULT_P_THRESHOLD: float = 0.40      # Seuil de probabilité en dessous duquel s'applique la pénalité
DEFAULT_PENALTY_POWER: float = 6.0     # Puissance d'effondrement de la pénalité pour p < 0.40
DEFAULT_K_SCALE: float = 25.0          # Constante de saturation exponentielle pour BQI 0-100
DEFAULT_TOP_N: int = 30                # Taille par défaut de la sélection d'élite
DEFAULT_MIN_EV: float = 0.0            # Seuil minimal d'EV (strictement positif)


def compute_bet_sigma(prob: float, price: float) -> float:
    """
    Calcule l'écart-type (volatilité) du gain pour une mise d'1 unité :
    sigma = sqrt(p * (1 - p)) * (price - 1)

    Paramètres :
        prob : Probabilité sharp équitable (0 < p < 1)
        price : Cote décimale proposée (price > 1.0)
    """
    if prob <= 0.0 or prob >= 1.0 or price <= 1.0:
        return 0.0
    return math.sqrt(prob * (1.0 - prob)) * (price - 1.0)


def compute_bet_sharpe(prob: float, price: float, ev: Optional[float] = None) -> float:
    """
    Calcule le Ratio de Sharpe du pari :
    Sharpe = EV / sigma
    """
    if prob <= 0.0 or prob >= 1.0 or price <= 1.0:
        return 0.0

    if ev is None:
        ev = (prob * price) - 1.0

    if ev <= 0.0:
        return 0.0

    sigma = compute_bet_sigma(prob, price)
    if sigma <= 1e-7:
        return 0.0

    return ev / sigma


def compute_bet_quality_index(
    prob: float,
    price: float,
    ev: Optional[float] = None,
    p_threshold: float = DEFAULT_P_THRESHOLD,
    penalty_power: float = DEFAULT_PENALTY_POWER,
    k_scale: float = DEFAULT_K_SCALE,
) -> Dict[str, Any]:
    """
    Calcule l'ensemble des métriques quantitatives Markowitz-Kelly :
    - sigma : Écart-type du gain
    - sharpe : Ratio de Sharpe brut (EV / sigma)
    - penalty : Facteur de pénalisation anti-bruit pour p < 0.40
    - penalized_sharpe : Sharpe pénalisé
    - kelly_growth : Taux de croissance théorique optimal g(f*) ~ 0.5 * Sharpe^2
    - bqi_score : Bet Quality Index normalisé sur [0, 100]
    - grade : Note qualitative (A+, A, B+, B, C)
    """
    if prob <= 0.0 or prob >= 1.0 or price <= 1.0:
        return {
            "sigma": 0.0,
            "sharpe": 0.0,
            "penalty": 0.0,
            "penalized_sharpe": 0.0,
            "kelly_growth": 0.0,
            "bqi_score": 0.0,
            "grade": "C",
        }

    if ev is None:
        ev = (prob * price) - 1.0

    if ev <= 0.0:
        return {
            "sigma": round(compute_bet_sigma(prob, price), 4),
            "sharpe": 0.0,
            "penalty": 0.0,
            "penalized_sharpe": 0.0,
            "kelly_growth": 0.0,
            "bqi_score": 0.0,
            "grade": "C",
        }

    sigma = compute_bet_sigma(prob, price)
    if sigma <= 1e-7:
        return {
            "sigma": 0.0,
            "sharpe": 0.0,
            "penalty": 0.0,
            "penalized_sharpe": 0.0,
            "kelly_growth": 0.0,
            "bqi_score": 0.0,
            "grade": "C",
        }

    sharpe = ev / sigma

    # Pénalité anti-bruit pour p < p_threshold (p < 0.40)
    if prob < p_threshold:
        # Effondrement polynomial abrupte : à p=0.20, pénalité ~ 1.5% ; à p=0.01, pénalité ~ 0
        penalty = (prob / p_threshold) ** penalty_power
    else:
        # Bonus modéré récompensant les forts Strike Rates (maîtrise du drawdown)
        penalty = 1.0 + 0.50 * (prob - p_threshold)

    penalized_sharpe = sharpe * penalty

    # Approximation de croissance log-Kelly : g(f*) ~ 0.5 * Sharpe^2
    kelly_growth = 0.5 * (sharpe ** 2)

    # Bet Quality Index normalisé sur [0, 100] via saturation exponentielle
    # Assure une différenciation fine entre 0.02 et 0.15 de Sharpe
    # tout en plafonnant sans distorsion les valeurs exceptionnelles.
    bqi_score = round(100.0 * (1.0 - math.exp(-k_scale * max(0.0, penalized_sharpe))), 1)
    bqi_score = max(0.0, min(100.0, bqi_score))

    # Attribution de la note qualitative
    if bqi_score >= 80.0:
        grade = "A+"
    elif bqi_score >= 65.0:
        grade = "A"
    elif bqi_score >= 50.0:
        grade = "B+"
    elif bqi_score >= 35.0:
        grade = "B"
    else:
        grade = "C"

    return {
        "sigma": round(sigma, 4),
        "sharpe": round(sharpe, 4),
        "penalty": round(penalty, 4),
        "penalized_sharpe": round(penalized_sharpe, 4),
        "kelly_growth": round(kelly_growth, 5),
        "bqi_score": bqi_score,
        "grade": grade,
    }


def get_match_key(sel: Dict[str, Any]) -> str:
    """
    Extrait une clé d'identification unique pour un match donné afin
    d'assurer la règle '1 seule sélection par match'.
    Priorité : match_id > match > event_id (nettoyé) > home_vs_away.
    """
    if sel.get("match_id"):
        return str(sel["match_id"])
    if sel.get("match"):
        return str(sel["match"]).strip().lower()
    event_id = str(sel.get("event_id") or "")
    if event_id:
        for suf in ("_dnb", "_1x2", "_ou25", "_ou15", "_ou35", "_btts"):
            if event_id.endswith(suf):
                return event_id[:-len(suf)]
        return event_id
    home = str(sel.get("home_team") or sel.get("home") or "").strip().lower()
    away = str(sel.get("away_team") or sel.get("away") or "").strip().lower()
    if home and away:
        return f"{home}_vs_{away}"
    return str(id(sel))


def filter_portal_2(
    selections: List[Dict[str, Any]],
    top_n: Optional[int] = DEFAULT_TOP_N,
    min_score: float = 0.0,
    min_grade: Optional[str] = None,
    one_per_match: bool = True,
    p_threshold: float = DEFAULT_P_THRESHOLD,
    penalty_power: float = DEFAULT_PENALTY_POWER,
    k_scale: float = DEFAULT_K_SCALE,
    min_ev: float = DEFAULT_MIN_EV,
    status_filter: Optional[str | List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filtre et classe les sélections selon le Portail 2 (Ratio de Sharpe & Markowitz-Kelly) :
    1. Calcule pour chaque sélection : sigma, Sharpe, Pénalité p < 0.40, BQI et Grade.
    2. Écarte les sélections d'EV négative ou nulle (EV <= 0.0%).
    3. Si one_per_match=True, sélectionne l'opportunité qui maximise le score BQI pour chaque match.
    4. Classe l'ensemble par score BQI décroissant.
    5. Applique les filtres optionnels de note minimale (min_grade) ou score minimal (min_score).
    6. Retourne le Top N d'élite (ex: 25-30 sélections).

    Arguments :
        selections : Liste des sélections candidates (ex: data.json['selections'])
        top_n : Nombre maximal de sélections d'élite retenues (défaut : 30)
        min_score : Score BQI minimal requis (défaut : 0.0)
        min_grade : Note minimale requise parmi 'A+', 'A', 'B+', 'B', 'C' (défaut : None)
        one_per_match : Si True, conserve strictement 1 seule sélection par match (défaut : True)
        p_threshold : Seuil de probabilité pour la pénalité (défaut : 0.40)
        penalty_power : Puissance d'effondrement anti-bruit pour p < 0.40 (défaut : 6.0)
        k_scale : Constante de saturation exponentielle pour BQI 0-100 (défaut : 25.0)
        min_ev : Espérance mathématique minimale (défaut : 0.0)
        status_filter : Statuts de match autorisés (ex: 'UPCOMING')

    Retourne :
        Liste ordonnée des sélections d'élite enrichies de leurs métriques quantitatives.
    """
    if not selections:
        return []

    # Hiérarchie des notes pour min_grade
    grade_order = {"A+": 5, "A": 4, "B+": 3, "B": 2, "C": 1}
    min_grade_val = grade_order.get(min_grade.upper()) if min_grade else 0

    allowed_statuses = None
    if status_filter:
        if isinstance(status_filter, str):
            allowed_statuses = {status_filter.upper()}
        else:
            allowed_statuses = {s.upper() for s in status_filter}

    evaluated_candidates: List[Dict[str, Any]] = []

    for sel in selections:
        if not isinstance(sel, dict):
            continue

        status = str(sel.get("status") or "").upper()
        if allowed_statuses:
            if status not in allowed_statuses:
                continue
        elif status == "LIVE":
            continue

        prob = sel.get("prob")
        price = sel.get("price")
        if prob is None or price is None:
            continue

        try:
            prob = float(prob)
            price = float(price)
        except (ValueError, TypeError):
            continue

        ev = sel.get("ev")
        if ev is not None:
            try:
                ev = float(ev)
            except (ValueError, TypeError):
                ev = (prob * price) - 1.0
        else:
            ev = (prob * price) - 1.0

        if ev <= min_ev:
            continue

        metrics = compute_bet_quality_index(
            prob=prob,
            price=price,
            ev=ev,
            p_threshold=p_threshold,
            penalty_power=penalty_power,
            k_scale=k_scale,
        )

        bqi_score = metrics["bqi_score"]
        grade = metrics["grade"]

        # Filtre sur note minimale si spécifié
        if min_grade_val and grade_order.get(grade, 0) < min_grade_val:
            continue

        # Filtre sur score minimal si spécifié
        if bqi_score < min_score:
            continue

        enriched = dict(sel)
        enriched["portal"] = 2
        enriched["sigma"] = metrics["sigma"]
        enriched["sharpe"] = metrics["sharpe"]
        enriched["penalized_sharpe"] = metrics["penalized_sharpe"]
        enriched["penalty_factor"] = metrics["penalty"]
        enriched["kelly_growth"] = metrics["kelly_growth"]
        enriched["bqi_score"] = bqi_score
        enriched["grade"] = grade

        evaluated_candidates.append(enriched)

    if not evaluated_candidates:
        return []

    # Règle intra-match : 1 seule sélection par match (maximisant le score BQI)
    if one_per_match:
        by_match = defaultdict(list)
        for s in evaluated_candidates:
            m_key = get_match_key(s)
            by_match[m_key].append(s)

        selected_per_match: List[Dict[str, Any]] = []
        for m_key, match_sels in by_match.items():
            best_sel = max(
                match_sels,
                key=lambda x: (
                    x["bqi_score"],
                    x["sharpe"],
                    float(x.get("ev", 0.0)),
                    float(x.get("prob", 0.0)),
                ),
            )
            selected_per_match.append(best_sel)
        evaluated_candidates = selected_per_match

    # Classement par Quality Score décroissant
    evaluated_candidates.sort(
        key=lambda x: (
            x["bqi_score"],
            x["sharpe"],
            float(x.get("ev", 0.0)),
            float(x.get("prob", 0.0)),
        ),
        reverse=True,
    )

    # Retient le Top N d'élite
    if top_n is not None and top_n > 0:
        return evaluated_candidates[:top_n]

    return evaluated_candidates


def audit_portal_2(
    selections: List[Dict[str, Any]],
    top_n: Optional[int] = DEFAULT_TOP_N,
    min_score: float = 0.0,
    min_grade: Optional[str] = None,
    one_per_match: bool = True,
    p_threshold: float = DEFAULT_P_THRESHOLD,
    penalty_power: float = DEFAULT_PENALTY_POWER,
    k_scale: float = DEFAULT_K_SCALE,
    min_ev: float = DEFAULT_MIN_EV,
    status_filter: Optional[str | List[str]] = None,
) -> Dict[str, Any]:
    """
    Fournit un audit complet et transparent des décisions du Portail 2 :
    - Statistiques globales (total entrées, EV positive, candidats qualifiés).
    - Distribution des notes (A+, A, B+, B, C).
    - Démonstration de l'élimination des cotes monstres / outsiders à faible probabilité.
    - Liste ordonnée finale du Top N d'élite.
    """
    total = len(selections)
    rejection_reasons = defaultdict(int)
    eliminated_longshots: List[Dict[str, Any]] = []
    positive_ev_count = 0

    for sel in selections:
        prob = sel.get("prob", 0.0)
        price = sel.get("price", 1.0)
        ev = sel.get("ev", (prob * price) - 1.0)

        if ev <= min_ev:
            rejection_reasons["ev_negative_ou_nulle"] += 1
            continue

        positive_ev_count += 1

        # Suivi des outsiders à forte cote
        if prob < p_threshold:
            metrics = compute_bet_quality_index(
                prob=prob,
                price=price,
                ev=ev,
                p_threshold=p_threshold,
                penalty_power=penalty_power,
                k_scale=k_scale,
            )
            if price >= 5.0 or prob < 0.20:
                eliminated_longshots.append({
                    "match": sel.get("match", "Inconnu"),
                    "sel": sel.get("sel", "Inconnu"),
                    "prob": prob,
                    "price": price,
                    "ev": ev,
                    "sigma": metrics["sigma"],
                    "sharpe": metrics["sharpe"],
                    "bqi_score": metrics["bqi_score"],
                    "grade": metrics["grade"],
                })

    final_selections = filter_portal_2(
        selections,
        top_n=top_n,
        min_score=min_score,
        min_grade=min_grade,
        one_per_match=one_per_match,
        p_threshold=p_threshold,
        penalty_power=penalty_power,
        k_scale=k_scale,
        min_ev=min_ev,
        status_filter=status_filter,
    )

    grade_counts = defaultdict(int)
    for s in final_selections:
        grade_counts[s["grade"]] += 1

    avg_sharpe = (
        round(sum(s["sharpe"] for s in final_selections) / len(final_selections), 3)
        if final_selections
        else 0.0
    )
    avg_bqi = (
        round(sum(s["bqi_score"] for s in final_selections) / len(final_selections), 1)
        if final_selections
        else 0.0
    )
    avg_prob = (
        round(sum(s["prob"] for s in final_selections) / len(final_selections), 3)
        if final_selections
        else 0.0
    )
    avg_price = (
        round(sum(s["price"] for s in final_selections) / len(final_selections), 2)
        if final_selections
        else 0.0
    )

    # Trie les longshots éliminés par EV décroissant pour montrer l'impact anti-ruine
    eliminated_longshots.sort(key=lambda x: x["ev"], reverse=True)

    return {
        "total_inputs": total,
        "positive_ev_count": positive_ev_count,
        "final_retained_count": len(final_selections),
        "grade_distribution": dict(grade_counts),
        "averages": {
            "avg_sharpe": avg_sharpe,
            "avg_bqi": avg_bqi,
            "avg_prob": avg_prob,
            "avg_price": avg_price,
        },
        "rejection_summary": dict(rejection_reasons),
        "eliminated_longshots_sample": eliminated_longshots[:10],
        "selections": final_selections,
    }
