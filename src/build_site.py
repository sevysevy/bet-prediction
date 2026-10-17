#!/usr/bin/env python3
"""
build_site.py — Générateur de la plateforme moderne d'analyse et prédiction de paris.

Fonctionnalités :
- Collecte multi-sources ou mode démonstration
- Dévigorisation & calcul de l'espérance mathématique (EV)
- Construction de combinés optimisés (garantie d'un seul bookmaker et matches distincts)
- Journalisation SQLite des recommandations et cotes observées
- Rendu d'une application web monopage (SPA) moderne, réactive et interactive :
  * Onglets : Plus probables, Value Bets (EV > 0), Combinés, Simulateur de Coupon / Kelly, Journal
  * Filtrage instantané (recherche, ligue, cote min/max, probabilité min)
  * Coupon interactif (sélection de matches, calcul de cote composée et mise Kelly personnalisée)
  * Zéro dépendance npm requise, 100% autonome
"""
from __future__ import annotations
import argparse
import datetime
import html
import itertools
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feeds                                                    # noqa: E402
from feeds import norm_oddspapi, norm_theodds, norm_pinnapi, modele_commun, pick_sharp, get, KEYS   # noqa: E402
from maths import devig_multiplicative, compute_ev, kelly_fraction, compound_combination           # noqa: E402
import journal                                                  # noqa: E402

MIN_PROB_LEG = 0.70
MAX_LEGS = 4
TOP_BOARD = 50
MAX_MARGIN = 0.08

ODDSPAPI_SLUGS = {
    "premier-league", "championship", "england-league-one", "england-league-two",
    "ligue-1", "ligue-2", "bundesliga", "bundesliga-2", "laliga", "laliga-2",
    "serie-a", "serie-b", "eredivisie", "primeira-liga", "jupiler-pro-league",
    "super-lig", "super-league-greece", "austrian-bundesliga", "super-league",
    "superliga", "eliteserien", "allsvenskan", "veikkausliiga", "ekstraklasa",
    "scottish-premiership", "league-of-ireland",
}

THEODDS_KEYS = [
    "soccer_epl", "soccer_france_ligue_one", "soccer_germany_bundesliga", "soccer_spain_la_liga",
    "soccer_italy_serie_a", "soccer_efl_champ", "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga", "soccer_spain_segunda_division", "soccer_germany_bundesliga2",
    "soccer_france_ligue_two", "soccer_italy_serie_b", "soccer_belgium_first_div",
    "soccer_turkey_super_league", "soccer_greece_super_league", "soccer_austria_bundesliga",
    "soccer_switzerland_superleague", "soccer_denmark_superliga", "soccer_norway_eliteserien",
    "soccer_sweden_allsvenskan", "soccer_sweden_superettan", "soccer_finland_veikkausliiga",
    "soccer_poland_ekstraklasa", "soccer_spl", "soccer_league_of_ireland",
    "soccer_england_league1", "soccer_england_league2"
]

# Stratégie de préservation des quotas / tokens :
ODDSPAPI_CACHE_TTL = 86400  # 1 fois par jour : snapshot Pinnacle et marchés secondaires
THEODDS_CACHE_TTL = 7200    # Toutes les 2 heures : mise à jour des cotes grand public
SCORES_CACHE_TTL = 7200     # Toutes les 2 heures : scores synchronisés au passage sans polling live dédié


# ------------------------------------------------------------------ collecte
def collect_oddspapi(key):
    import time
    key = (key or "").strip().strip('"').strip("'")
    
    # 1. Récupération des tournois (mise en cache 24h pour préserver le quota)
    tournaments, _ = get("https://api.oddspapi.io/v4/tournaments",
                         {"sportId": 10, "apiKey": key}, cache_ttl_s=ODDSPAPI_CACHE_TTL)
    tournaments_map = {str(t["tournamentId"]): t for t in tournaments} if isinstance(tournaments, list) else {}

    # 2. Récupération du dictionnaire des équipes (mise en cache 24h)
    try:
        participants, _ = get("https://api.oddspapi.io/v4/participants",
                              {"sportId": 10, "apiKey": key}, cache_ttl_s=86400)
    except Exception as exc:
        print(f"  [!] oddspapi participants : {exc}", file=sys.stderr)
        participants = {}
    if not isinstance(participants, dict):
        participants = {}

    # 3. Filtrage des tournois cibles (priorité aux championnats majeurs européens)
    major_cats = {
        "england", "spain", "germany", "italy", "france", "europe",
        "international", "netherlands", "portugal", "belgium", "turkey", "scotland"
    }
    top_tier_ids = {"17", "8", "23", "35", "34", "37", "20", "18", "40", "53", "54", "182"}
    target_tournaments = []
    if isinstance(tournaments, list):
        for t in tournaments:
            slug = t.get("tournamentSlug")
            cat = str(t.get("categorySlug") or "").lower()
            if slug in ODDSPAPI_SLUGS and cat in major_cats:
                target_tournaments.append(t)
        # Tri : championnats de première division d'abord, puis par volume de matches
        target_tournaments.sort(key=lambda t: (
            0 if str(t.get("tournamentId")) in top_tier_ids else 1,
            -t.get("futureFixtures", 0)
        ))

    ids = [str(t["tournamentId"]) for t in target_tournaments]
    if not ids and isinstance(tournaments, list):
        ids = [str(t["tournamentId"]) for t in tournaments[:15]]

    if not ids:
        raise RuntimeError("aucun tournoi disponible dans la réponse /tournaments")

    # ATTENTION API ODDSPAPI : Maximum 5 tournamentIds par requête
    # Découpage en lots de 5 avec temporisation respectant le rate limit de 1000ms
    CHUNK_SIZE = 5
    MAX_CHUNKS = 4  # Jusqu'à 20 championnats cibles
    all_odds = []

    for i in range(0, min(len(ids), CHUNK_SIZE * MAX_CHUNKS), CHUNK_SIZE):
        chunk = ids[i:i + CHUNK_SIZE]
        if not chunk:
            continue
        if i > 0:
            time.sleep(1.2)  # Cooldown rate limit obligatoire (1000ms)
        try:
            payload, _ = get("https://api.oddspapi.io/v4/odds-by-tournaments",
                             {"bookmaker": "pinnacle", "tournamentIds": ",".join(chunk), "apiKey": key},
                             cache_ttl_s=ODDSPAPI_CACHE_TTL)
            if isinstance(payload, list):
                all_odds.extend(payload)
        except Exception as exc:
            print(f"  [!] oddspapi lot {chunk} : {exc}", file=sys.stderr)

    events = norm_oddspapi(all_odds, participants=participants, tournaments=tournaments_map)
    return events, f"oddspapi · {len(all_odds)} matches Pinnacle"


def collect_theodds(api_key, max_leagues: int = 10):
    api_key = (api_key or "").strip().strip('"').strip("'")
    events, ok = [], []
    for s in THEODDS_KEYS[:max_leagues]:
        try:
            data, _ = get(f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                          {"apiKey": api_key, "regions": "eu,uk", "markets": "h2h",
                           "oddsFormat": "decimal"},
                          cache_ttl_s=THEODDS_CACHE_TTL)
            if data:
                events += data
                ok.append(s)
        except Exception as exc:
            print(f"  [!] {s} : {exc}", file=sys.stderr)
    return norm_theodds(events), f"The Odds API ({len(ok)} ligues grand public)"


def norm_team_key(s: str) -> str:
    s = str(s or "").lower().strip()
    s = re.sub(r'\bst\b', 'saint', s)
    s = re.sub(r'\butd\b', 'united', s)
    s = re.sub(r'\bman\b', 'manchester', s)
    s = re.sub(r'\bsg\b', 'saint germain', s)
    s = re.sub(r'\b(fc|cf|osc|rc|as|ac|ss|rb|fsv|sc|us|ogc|vfl|bvb|afc)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s


def merge_feeds(oddspapi_events, theodds_events):
    """
    Fusionne les flux TheOddsAPI (bookmakers grand public) et OddsPapi (Pinnacle sharp + multi-marchés).
    Pour les matches 1X2 couverts par TheOddsAPI, privilégie TheOddsAPI qui contient l'ensemble
    des cotes des bookmakers grand public (Winamax, Betclic, Unibet, 1xBet...) face à Pinnacle.
    Conserve tous les marchés secondaires (Buts, BTTS, DNB) et les matches exclusifs d'OddsPapi.
    """
    to_matches = set()
    for ev in theodds_events:
        h = norm_team_key(ev.get("home"))
        a = norm_team_key(ev.get("away"))
        if h and a:
            to_matches.add((h, a))
            to_matches.add((a, h))

    combined = list(theodds_events)
    for ev in oddspapi_events:
        h = norm_team_key(ev.get("home"))
        a = norm_team_key(ev.get("away"))
        # Si le 1X2 est déjà présent dans TheOddsAPI, on évite le doublon pour garder la version multi-bookmakers
        if ev.get("market_type") == "1X2 (Résultat)" and ((h, a) in to_matches or (a, h) in to_matches):
            continue
        combined.append(ev)

    return combined


def collect():
    oddspapi_key = (os.environ.get("ODDSPAPI_KEY") or "").strip().strip('"').strip("'")
    theodds_key = (os.environ.get("THEODDSAPI_KEY") or os.environ.get("ODDS_API_KEY") or "").strip().strip('"').strip("'")

    oddspapi_events, op_info = [], None
    theodds_events, to_info = [], None

    if theodds_key:
        try:
            theodds_events, to_info = collect_theodds(theodds_key, max_leagues=10)
        except Exception as exc:
            print(f"  [!] theoddsapi : {exc}", file=sys.stderr)

    if oddspapi_key:
        try:
            oddspapi_events, op_info = collect_oddspapi(oddspapi_key)
        except Exception as exc:
            print(f"  [!] oddspapi : {exc}", file=sys.stderr)

    if not theodds_events and not oddspapi_events:
        raise RuntimeError("aucune source disponible (vérifiez que vos clés d'API sont valides)")

    if theodds_events and oddspapi_events:
        combined = merge_feeds(oddspapi_events, theodds_events)
        return combined, f"Couplé · Pinnacle Sharp (OddsPapi) + Grand Public (TheOddsAPI)"
    elif theodds_events:
        return theodds_events, to_info or "the-odds-api"
    else:
        return oddspapi_events, op_info or "oddspapi"


# ------------------------------------------------------------------ Scores & Résultats
def collect_scores(theodds_key):
    """
    Récupère les scores récents (en direct et terminés des dernières 48h)
    pour les 5 grandes ligues européennes via The Odds API.
    """
    scores_map = {}
    if not theodds_key:
        return scores_map
    top_leagues = [
        "soccer_epl", "soccer_france_ligue_one", "soccer_germany_bundesliga",
        "soccer_spain_la_liga", "soccer_italy_serie_a"
    ]
    for lg in top_leagues:
        try:
            data, _ = get(f"https://api.the-odds-api.com/v4/sports/{lg}/scores",
                          {"apiKey": theodds_key, "daysFrom": 2}, cache_ttl_s=SCORES_CACHE_TTL)
            for m in data or []:
                h = norm_team_key(m.get("home_team"))
                a = norm_team_key(m.get("away_team"))
                scores = m.get("scores") or []
                h_score, a_score = None, None
                for s in scores:
                    if norm_team_key(s.get("name")) == h:
                        try:
                            h_score = int(s.get("score"))
                        except (ValueError, TypeError):
                            pass
                    elif norm_team_key(s.get("name")) == a:
                        try:
                            a_score = int(s.get("score"))
                        except (ValueError, TypeError):
                            pass

                scores_map[(h, a)] = {
                    "completed": m.get("completed", False),
                    "home_team": m.get("home_team"),
                    "away_team": m.get("away_team"),
                    "home_score": h_score,
                    "away_score": a_score,
                    "league": lg,
                    "commence_time": m.get("commence_time"),
                    "last_update": m.get("last_update")
                }
        except Exception as exc:
            print(f"  [!] scores {lg} : {exc}", file=sys.stderr)
    return scores_map


def evaluate_outcome(market_type, sel, home, away, home_score, away_score):
    """
    Évalue si un pari est Gagné (WON), Perdu (LOST) ou Remboursé (PUSH)
    en fonction du score final et du marché ciblé.
    """
    if home_score is None or away_score is None:
        return None
    market_type = str(market_type or "1x2").lower()
    sel_lower = str(sel or "").lower()
    norm_h = norm_team_key(home)
    norm_a = norm_team_key(away)

    if "1x2" in market_type:
        if home_score > away_score:
            winner = "home"
        elif away_score > home_score:
            winner = "away"
        else:
            winner = "draw"

        if "draw" in sel_lower or "nul" in sel_lower:
            return "WON" if winner == "draw" else "LOST"
        norm_s = norm_team_key(sel)
        if norm_s == norm_h or norm_h in norm_s or norm_s in norm_h:
            return "WON" if winner == "home" else "LOST"
        if norm_s == norm_a or norm_a in norm_s or norm_s in norm_a:
            return "WON" if winner == "away" else "LOST"
        return None

    if "buts" in market_type or "tot" in market_type:
        total = home_score + away_score
        val = 2.5
        if "1.5" in sel:
            val = 1.5
        elif "3.5" in sel:
            val = 3.5
        elif "2.5" in sel:
            val = 2.5
        if "+" in sel or "over" in sel_lower:
            return "WON" if total > val else "LOST"
        elif "-" in sel or "under" in sel_lower:
            return "WON" if total < val else "LOST"

    if "marquent" in market_type or "btts" in market_type:
        both_scored = (home_score > 0 and away_score > 0)
        if "oui" in sel_lower or "yes" in sel_lower:
            return "WON" if both_scored else "LOST"
        if "non" in sel_lower or "no" in sel_lower:
            return "WON" if not both_scored else "LOST"

    if "rembours" in market_type or "dnb" in market_type:
        if home_score == away_score:
            return "PUSH"
        winner = "home" if home_score > away_score else "away"
        norm_s = norm_team_key(sel)
        if norm_s == norm_h or norm_h in norm_s or norm_s in norm_h:
            return "WON" if winner == "home" else "LOST"
        if norm_s == norm_a or norm_a in norm_s or norm_s in norm_a:
            return "WON" if winner == "away" else "LOST"

    return None


def enrich_rows_with_scores(rows, scores_map, prematch_db=None):
    """
    Enrichit chaque ligne avec le statut temporel (UPCOMING, LIVE, FINISHED),
    le score officiel s'il est connu, et l'évaluation du pronostic (WON, LOST, PUSH).

    Pour les matches en cours (LIVE) ou terminés (FINISHED) :
    - Conserve ou restaure les DERNIÈRES ÉVALUATIONS PRÉ-MATCH authentiques
      (probabilité fair sharp, cote offerte, bookmaker, EV, mise Kelly).
    - Évalue le résultat réel (Gagné / Perdu) sans jamais injecter de fausses cotes 1.00 à 100%.
    - Pour les matches terminés absents du flux live (/odds), charge leur pronostic pré-match
      depuis le journal SQLite pour offrir une véritable vision historique des tendances.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    from leagues import resolve_league

    if prematch_db is None:
        try:
            prematch_db = journal.get_prematch_by_pair()
        except Exception:
            prematch_db = {}

    for r in rows:
        ko = r.get("kickoff")
        dt = None
        if ko:
            try:
                dt = datetime.datetime.fromisoformat(ko.replace("Z", "+00:00"))
            except Exception:
                pass

        match_parts = (r.get("match") or "").split(" - ")
        home_raw = match_parts[0].strip() if len(match_parts) >= 1 else ""
        away_raw = match_parts[1].strip() if len(match_parts) >= 2 else ""

        h = norm_team_key(home_raw)
        a = norm_team_key(away_raw)

        sc = scores_map.get((h, a)) or scores_map.get((a, h))

        status = "UPCOMING"
        score_str = None
        outcome = None
        home_score = sc.get("home_score") if sc else None
        away_score = sc.get("away_score") if sc else None
        diff_min = (now - dt).total_seconds() / 60 if dt else 0
        is_completed = bool(sc and sc.get("completed")) or (dt and diff_min > 135)

        if is_completed:
            status = "FINISHED"
            score_str = f"{home_score} - {away_score}" if (home_score is not None and away_score is not None) else "Terminé"
            outcome = evaluate_outcome(r.get("market_type"), r.get("sel"), home_raw, away_raw, home_score, away_score)
        elif sc and (home_score is not None and away_score is not None):
            status = "LIVE"
            score_str = f"{home_score} - {away_score}"
        elif dt and dt < now:
            status = "LIVE"
            score_str = "En direct"

        # Pour les matches LIVE ou FINISHED, on conserve l'évaluation pré-match d'origine
        if status in ("LIVE", "FINISHED"):
            pm_sels = prematch_db.get((h, a)) or prematch_db.get((a, h))
            if pm_sels:
                pm = pm_sels.get(r.get("sel"))
                if pm:
                    r["prob"] = pm["prob_fair"]
                    r["price"] = pm["odds_offered"]
                    r["book"] = pm["bookmaker"]
                    r["ev"] = pm["ev"]
                    r["kelly_quarter"] = pm.get("kelly_stake_pct", 0.0)
                    if pm.get("sharp_ref"):
                        r["sharp"] = pm["sharp_ref"]
                    if pm.get("sharp_margin"):
                        r["sharp_margin"] = pm["sharp_margin"]

        r["status"] = status
        r["score_str"] = score_str
        r["outcome"] = outcome
        r["home_score"] = home_score
        r["away_score"] = away_score

    # Intègre les matches terminés récents issus des scores officiels
    # UNIQUEMENT s'ils ont fait l'objet d'une évaluation pré-match enregistrée
    existing_pairs = set()
    for r in rows:
        parts = (r.get("match") or "").split(" - ")
        if len(parts) >= 2:
            existing_pairs.add((norm_team_key(parts[0]), norm_team_key(parts[1])))
            existing_pairs.add((norm_team_key(parts[1]), norm_team_key(parts[0])))

    for (h, a), sc in scores_map.items():
        if not sc.get("completed"):
            continue
        if (h, a) in existing_pairs:
            continue
        hs = sc.get("home_score")
        as_ = sc.get("away_score")
        if hs is None or as_ is None:
            continue
        home_t = sc.get("home_team")
        away_t = sc.get("away_team")

        # Recherche des évaluations pré-match authentiques dans le journal
        pm_sels = prematch_db.get((h, a)) or prematch_db.get((a, h))
        if not pm_sels:
            # Si le match n'a jamais été analysé en pré-match, on n'injecte PAS
            # d'évaluation artificielle 100% / 1.00 pour ne pas fausser l'historique
            continue

        lg_info = resolve_league(sc.get("league"))
        for sel, pm in pm_sels.items():
            outcome = evaluate_outcome("1X2", sel, home_t, away_t, hs, as_)
            rows.append({
                "event_id": pm.get("event_id") or f"settled_{h}_{a}",
                "match_id": pm.get("event_id") or f"settled_{h}_{a}",
                "market_type": "1X2 (Résultat)",
                "league": pm.get("league") or lg_info["name"],
                "league_key": sc.get("league") or "general",
                "country": lg_info["country"],
                "flag": lg_info["flag"],
                "badge_url": lg_info["badge_url"],
                "kickoff": pm.get("kickoff") or sc.get("commence_time"),
                "match": f"{home_t} - {away_t}",
                "sel": sel,
                "prob": pm["prob_fair"],
                "price": pm["odds_offered"],
                "book": pm["bookmaker"],
                "limit": None,
                "age_s": None,
                "book_margin": 0.05,
                "sharp": pm.get("sharp_ref") or "Pinnacle",
                "sharp_margin": pm.get("sharp_margin") or 0.02,
                "ev": pm["ev"],
                "kelly_quarter": pm.get("kelly_stake_pct", 0.0),
                "status": "FINISHED",
                "score_str": f"{hs} - {as_}",
                "outcome": outcome,
                "home_score": hs,
                "away_score": as_
            })
        existing_pairs.add((h, a))
        existing_pairs.add((a, h))


# ------------------------------------------------------------------ combinés
def build_combos(events):
    legs = []
    for ev in events:
        # Seuls les résultats 1X2 sont combinés automatiquement pour éviter toute corrélation cachée
        if ev.get("market_type") and "1X2" not in ev.get("market_type"):
            continue
        books = ev.get("books", [])
        sharp = pick_sharp(books)
        if not sharp:
            continue
        cand = [s for s, p in sharp["probs"].items() if p >= MIN_PROB_LEG]
        if not cand:
            continue
        sel = max(cand, key=lambda s: sharp["probs"][s])
        prices = {b["name"]: b["prices"][sel] for b in books
                  if sel in b.get("prices", {}) and b.get("margin", 1.0) < MAX_MARGIN}
        if not prices:
            prices = {b["name"]: b["prices"][sel] for b in books if sel in b.get("prices", {})}
        if prices:
            legs.append({
                "sel": sel,
                "prob": sharp["probs"][sel],
                "prices": prices,
                "match": f'{ev.get("home")} - {ev.get("away")}',
                "league": ev.get("league") or "Général"
            })
    legs.sort(key=lambda l: -l["prob"])

    out = []
    for n in range(2, min(MAX_LEGS, len(legs)) + 1):
        best = None
        for combo in itertools.combinations(legs, n):
            if len({c["match"] for c in combo}) != n:
                continue
            c_res = compound_combination(list(combo))
            if not c_res:
                continue
            if best is None or c_res["prob"] > best["prob"]:
                best = {
                    "n": n,
                    "prob": c_res["prob"],
                    "odds": c_res["odds"],
                    "ev": c_res["ev"],
                    "book": c_res["book"],
                    "kelly": c_res["kelly_quarter"],
                    "legs": [f"{c['match']} ({c['sel']})" for c in combo],
                    "raw_legs": combo
                }
        if best:
            out.append(best)
    return out


# ------------------------------------------------------------------ Démo enrichie
FIX_DEMO = [
  {"id": "e1", "sport_key": "Premier League", "commence_time": "2026-10-17T14:00:00Z",
   "home_team": "Manchester City", "away_team": "Brighton",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:40:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Manchester City", "price": 1.22},
         {"name": "Brighton", "price": 12.0}, {"name": "Draw", "price": 6.4}]}]},
     {"key": "betclic", "title": "Betclic", "last_update": "2026-10-17T13:52:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Manchester City", "price": 1.24},
         {"name": "Brighton", "price": 11.5}, {"name": "Draw", "price": 6.1}]}]},
     {"key": "winamax", "title": "Winamax", "last_update": "2026-10-17T13:52:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Manchester City", "price": 1.25},
         {"name": "Brighton", "price": 10.5}, {"name": "Draw", "price": 6.0}]}]}]},

  {"id": "e2", "sport_key": "Bundesliga", "commence_time": "2026-10-17T14:30:00Z",
   "home_team": "Bayern Munich", "away_team": "Mainz",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:41:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Bayern Munich", "price": 1.20},
         {"name": "Mainz", "price": 12.5}, {"name": "Draw", "price": 7.0}]}]},
     {"key": "unibet", "title": "Unibet", "last_update": "2026-10-17T13:50:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Bayern Munich", "price": 1.18},
         {"name": "Mainz", "price": 13.5}, {"name": "Draw", "price": 6.8}]}]}]},

  {"id": "e3", "sport_key": "Ligue 1", "commence_time": "2026-10-17T16:00:00Z",
   "home_team": "Paris SG", "away_team": "Strasbourg",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:43:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Paris SG", "price": 1.28},
         {"name": "Strasbourg", "price": 10.0}, {"name": "Draw", "price": 5.8}]}]},
     {"key": "winamax", "title": "Winamax", "last_update": "2026-10-17T13:53:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Paris SG", "price": 1.32},
         {"name": "Strasbourg", "price": 9.2}, {"name": "Draw", "price": 5.5}]}]}]},

  {"id": "e4", "sport_key": "La Liga", "commence_time": "2026-10-17T17:30:00Z",
   "home_team": "Real Madrid", "away_team": "Getafe",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:42:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Real Madrid", "price": 1.25},
         {"name": "Getafe", "price": 11.0}, {"name": "Draw", "price": 6.2}]}]},
     {"key": "betclic", "title": "Betclic", "last_update": "2026-10-17T13:51:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Real Madrid", "price": 1.27},
         {"name": "Getafe", "price": 10.5}, {"name": "Draw", "price": 6.0}]}]}]},

  {"id": "e5", "sport_key": "Ligue 1", "commence_time": "2026-10-17T19:00:00Z",
   "home_team": "Lille", "away_team": "Nantes",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:42:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Lille", "price": 1.48},
         {"name": "Nantes", "price": 7.5}, {"name": "Draw", "price": 4.4}]}]},
     {"key": "winamax", "title": "Winamax", "last_update": "2026-10-17T13:51:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Lille", "price": 1.54},
         {"name": "Nantes", "price": 7.0}, {"name": "Draw", "price": 4.3}]}]}]},

  {"id": "e6", "sport_key": "Serie A", "commence_time": "2026-10-17T19:45:00Z",
   "home_team": "Inter Milan", "away_team": "Monza",
   "bookmakers": [
     {"key": "pinnacle", "title": "Pinnacle (Sharp)", "last_update": "2026-10-17T13:44:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Inter Milan", "price": 1.21},
         {"name": "Monza", "price": 13.0}, {"name": "Draw", "price": 6.8}]}]},
     {"key": "betclic", "title": "Betclic", "last_update": "2026-10-17T13:54:00Z",
      "markets": [{"key": "h2h", "outcomes": [{"name": "Inter Milan", "price": 1.23},
         {"name": "Monza", "price": 12.0}, {"name": "Draw", "price": 6.5}]}]}]}
]


# ------------------------------------------------------------------ Génération du site moderne
def generate_html(rows, combos, stats, source, demo, now_str):
    """
    Produit une Single Page Application moderne, responsive et réactive.
    Styles CSS modernes intégrés, interactions JavaScript vanille sans dépendance.
    """
    leagues_seen = {}
    for r in rows:
        lg_name = r.get("league")
        if lg_name and lg_name not in leagues_seen:
            leagues_seen[lg_name] = {
                "name": lg_name,
                "country": r.get("country", ""),
                "flag": r.get("flag", "⚽"),
                "badge_url": r.get("badge_url", "")
            }

    app_data = {
        "generated_at": now_str,
        "source": source,
        "demo": demo,
        "stats": stats,
        "selections": rows,
        "combos": [{k: v for k, v in c.items() if k != "raw_legs"} for c in combos],
        "leagues": list(leagues_seen.values())
    }
    json_embedded = json.dumps(app_data, ensure_ascii=False)

    best_prob_str = f"{rows[0]['prob']:.1%}" if rows else "—"
    best_match_str = rows[0]['match'] if rows else ""
    stat_signals = stats.get('total_signals', len(rows))
    stat_pos = stats.get('positive_ev_count', len([r for r in rows if r['ev'] > 0]))
    avg_ev_str = f"{stats.get('avg_ev', 0):+.2%}" if stats.get('avg_ev') is not None else "+0.00%"

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Les Plus Probables — Prédiction & Espérance de Gain (EV)</title>
  <meta name="description" content="Probabilités issues des cotes du marché dévigorisées, combinés optimisés et calcul d'espérance de gain (EV).">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #090d16;
      --card-bg: #111827;
      --card-border: #1f293d;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent: #6366f1;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --badge-bg: #1e293b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      line-height: 1.5;
    }}
    .mono {{ font-family: 'JetBrains Mono', monospace; }}
    
    /* Layout */
    .container {{ max-width: 1240px; margin: 0 auto; padding: 24px 20px 100px; }}
    header {{
      display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px;
      padding-bottom: 20px; border-bottom: 1px solid var(--card-border);
    }}
    .header-top {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }}
    h1 {{ font-size: 26px; font-weight: 800; letter-spacing: -0.5px; color: #fff; }}
    .subtitle {{ color: var(--text-muted); font-size: 14px; max-width: 760px; }}
    
    /* Stats Bar */
    .stats-bar {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--card-bg); border: 1px solid var(--card-border);
      padding: 14px 18px; border-radius: 12px; display: flex; flex-direction: column;
    }}
    .stat-label {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-muted); font-weight: 600; }}
    .stat-val {{ font-size: 22px; font-weight: 700; margin-top: 4px; color: #fff; }}
    .stat-sub {{ font-size: 12px; color: var(--text-muted); }}

    /* Banner Demo */
    .demo-banner {{
      background: linear-gradient(90deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.05) 100%);
      border: 1px solid rgba(245, 158, 11, 0.4);
      padding: 12px 18px; border-radius: 10px; margin-bottom: 20px;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      color: #fbbf24; font-size: 13.5px;
    }}

    /* Navigation Tabs */
    .tabs {{
      display: flex; gap: 8px; border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px; overflow-x: auto; padding-bottom: 2px;
    }}
    .tab-btn {{
      background: none; border: none; padding: 10px 18px; border-radius: 8px;
      color: var(--text-muted); font-size: 14px; font-weight: 600; cursor: pointer;
      display: flex; align-items: center; gap: 8px; transition: all 0.2s ease;
      white-space: nowrap;
    }}
    .tab-btn:hover {{ color: #fff; background: var(--badge-bg); }}
    .tab-btn.active {{
      color: #fff; background: var(--primary);
    }}
    .tab-count {{
      background: rgba(255, 255, 255, 0.2); padding: 1px 7px;
      border-radius: 12px; font-size: 11px;
    }}

    /* Date Timeline Bar */
    .date-bar {{
      display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
      background: var(--card-bg); border: 1px solid var(--card-border);
      padding: 12px 16px; border-radius: 12px; margin-bottom: 14px;
    }}
    .date-presets {{
      display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    }}
    .date-pill {{
      background: var(--badge-bg); color: var(--text-muted); border: 1px solid var(--card-border);
      padding: 6px 13px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
      display: inline-flex; align-items: center; gap: 6px; transition: all 0.15s ease;
    }}
    .date-pill:hover {{ color: #fff; border-color: var(--primary); }}
    .date-pill.active {{
      background: var(--primary); color: #fff; border-color: var(--primary);
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }}
    .pill-count {{
      background: rgba(255, 255, 255, 0.2); padding: 1px 6px; border-radius: 10px; font-size: 11px;
    }}
    .date-picker-wrap {{
      display: flex; align-items: center; gap: 8px;
    }}
    .date-input {{
      background: #0b101b; border: 1px solid var(--card-border); color: #fff;
      padding: 6px 10px; border-radius: 8px; font-size: 13px; outline: none; cursor: pointer;
    }}
    .date-input:focus {{ border-color: var(--primary); }}
    .btn-clear-date {{
      background: none; border: none; color: #ef4444; font-size: 18px; cursor: pointer;
      line-height: 1; padding: 0 4px;
    }}

    /* Filter Controls */
    .filter-panel {{
      background: var(--card-bg); border: 1px solid var(--card-border);
      padding: 16px; border-radius: 12px; margin-bottom: 20px;
      display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
    }}
    .search-input {{
      background: #0b101b; border: 1px solid var(--card-border);
      color: #fff; padding: 8px 14px; border-radius: 8px; font-size: 13.5px;
      flex: 1; min-width: 220px; outline: none;
    }}
    .search-input:focus {{ border-color: var(--primary); }}
    .select-dropdown {{
      background: #0b101b; border: 1px solid var(--card-border);
      color: #fff; padding: 8px 12px; border-radius: 8px; font-size: 13px;
      outline: none; cursor: pointer;
    }}
    .badge {{
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;
    }}
    .badge-pos {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .badge-neg {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
    .badge-warn {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-gray {{ background: var(--badge-bg); color: var(--text-muted); }}
    .badge-market {{
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.35);
      font-size: 11px;
      font-weight: 700;
      padding: 1px 7px;
      border-radius: 4px;
      display: inline-block;
      letter-spacing: 0.3px;
    }}
    .badge-live {{
      background: rgba(239, 68, 68, 0.2);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.45);
      font-size: 11px;
      animation: pulse-live 2s infinite;
    }}
    .badge-finished {{
      background: rgba(100, 116, 139, 0.2);
      color: #cbd5e1;
      border: 1px solid rgba(100, 116, 139, 0.35);
      font-size: 11px;
    }}
    .badge-upcoming {{
      background: rgba(59, 130, 246, 0.15);
      color: #93c5fd;
      border: 1px solid rgba(59, 130, 246, 0.35);
      font-size: 11px;
    }}
    .badge-won {{
      background: rgba(16, 185, 129, 0.25);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.5);
      font-weight: 700;
      font-size: 11px;
    }}
    .badge-lost {{
      background: rgba(244, 63, 94, 0.2);
      color: #fb7185;
      border: 1px solid rgba(244, 63, 94, 0.4);
      font-weight: 700;
      font-size: 11px;
    }}
    .badge-push {{
      background: rgba(234, 179, 8, 0.2);
      color: #facc15;
      border: 1px solid rgba(234, 179, 8, 0.4);
      font-size: 11px;
    }}
    @keyframes pulse-live {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.75; transform: scale(0.98); }}
    }}

    /* Tables */
    .table-container {{
      background: var(--card-bg); border: 1px solid var(--card-border);
      border-radius: 12px; overflow-x: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; }}
    th {{
      background: #0d131f; color: var(--text-muted); padding: 12px 14px;
      font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px;
      font-weight: 700; border-bottom: 1px solid var(--card-border);
    }}
    td {{
      padding: 12px 14px; border-bottom: 1px solid var(--card-border);
      vertical-align: middle;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: rgba(255, 255, 255, 0.02); }}
    td.right, th.right {{ text-align: right; }}
    
    .prob-bar-container {{
      display: flex; align-items: center; gap: 8px;
    }}
    .prob-bar {{
      width: 60px; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden;
    }}
    .prob-fill {{ height: 100%; background: var(--primary); border-radius: 3px; }}
    
    /* Interactive Slip Button */
    .btn-add {{
      background: var(--badge-bg); color: #fff; border: 1px solid var(--card-border);
      padding: 5px 10px; border-radius: 6px; font-size: 12px; cursor: pointer;
      display: inline-flex; align-items: center; gap: 4px; transition: all 0.15s ease;
    }}
    .btn-add:hover {{ background: var(--primary); border-color: var(--primary); }}
    .btn-add.in-slip {{ background: var(--success); border-color: var(--success); }}

    /* Cards / Accordion */
    .combo-card {{
      background: var(--card-bg); border: 1px solid var(--card-border);
      border-radius: 12px; padding: 18px; margin-bottom: 16px;
    }}
    .combo-header {{
      display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
      margin-bottom: 12px;
    }}
    .legs-list {{
      display: flex; flex-direction: column; gap: 6px; margin-top: 10px;
      padding-top: 10px; border-top: 1px solid var(--card-border);
    }}
    .leg-item {{
      display: flex; justify-content: space-between; font-size: 13px; color: var(--text-muted);
    }}
    .btn-refresh {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #e2e8f0;
      font-size: 12px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
    }}
    .btn-refresh:hover {{
      background: rgba(59, 130, 246, 0.25);
      border-color: var(--primary);
      color: #fff;
    }}
    .btn-refresh:active {{
      transform: scale(0.96);
    }}

    /* Bet Slip Floating Drawer */
    .slip-drawer {{
      position: fixed; bottom: 20px; right: 20px; width: 360px;
      background: #0f172a; border: 1px solid #334155; border-radius: 16px;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6); z-index: 100;
      display: flex; flex-direction: column; overflow: hidden; transition: transform 0.3s ease;
    }}
    .slip-header {{
      background: #1e293b; padding: 14px 18px; display: flex; justify-content: space-between;
      align-items: center; font-weight: 700; font-size: 14px; cursor: pointer;
    }}
    .slip-body {{ padding: 16px; max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }}
    .slip-item {{
      background: #111827; border: 1px solid var(--card-border); border-radius: 8px;
      padding: 10px 12px; display: flex; justify-content: space-between; align-items: center;
    }}
    .slip-calc {{
      background: #111827; border: 1px dashed #334155; border-radius: 8px;
      padding: 12px; font-size: 13px; display: flex; flex-direction: column; gap: 8px;
    }}
    .calc-row {{ display: flex; justify-content: space-between; }}
    .stake-input {{
      width: 70px; background: #090d16; border: 1px solid #334155; color: #fff;
      padding: 4px 6px; border-radius: 4px; text-align: right; font-family: 'JetBrains Mono', monospace;
    }}
    .slip-collapsed .slip-body {{ display: none; }}

    /* Educational Box */
    .edu-card {{
      background: rgba(30, 41, 59, 0.6); border: 1px solid var(--card-border);
      border-radius: 12px; padding: 20px; margin-top: 30px;
    }}
    .edu-card h3 {{ font-size: 16px; margin-bottom: 8px; color: var(--primary); }}
    .edu-card p {{ font-size: 13px; color: var(--text-muted); line-height: 1.6; margin-bottom: 8px; }}

    @media (max-width: 768px) {{
      .slip-drawer {{ width: calc(100vw - 32px); right: 16px; bottom: 16px; }}
      .stats-bar {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>
<div class="container">
  <header>
    <div class="header-top">
      <div>
        <h1>Les Plus Probables</h1>
        <p class="subtitle">
          Probabilités de marché dévigorisées (référence sharp sans marge) · Comparaison des cotes & Espérance de Gain (EV).
        </p>
      </div>
      <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <button id="btn-force-refresh" onclick="triggerManualRefresh()" class="btn-refresh" title="Forcer une actualisation manuelle immédiate sans cache">🔄 Actualiser</button>
          <span class="badge badge-gray mono">Source: {html.escape(source)}</span>
        </div>
        <div style="font-size: 12px; color: var(--text-muted);">Généré à {now_str}</div>
      </div>
    </div>
  </header>

  {"<div class='demo-banner'><span>⚡ <b>Mode Démonstration Actif</b> — Données simulées multi-ligues. Renseignez ODDSPAPI_KEY ou THEODDSAPI_KEY pour le flux live.</span><span class='badge badge-warn'>DÉMO</span></div>" if demo else ""}

  <!-- Stats Grid -->
  <div class="stats-bar">
    <div class="stat-card">
      <span class="stat-label">Sélections Analysées</span>
      <span class="stat-val" id="stat-total-selections">{len(rows)}</span>
      <span class="stat-sub">Issues 1X2 & Over/Under</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Value Bets Détectés</span>
      <span class="stat-val" style="color: var(--success);" id="stat-value-bets">{stats.get('positive_ev_count', 0)}</span>
      <span class="stat-sub">Espérance positive (EV &gt; 0)</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Meilleure Probabilité</span>
      <span class="stat-val mono" style="color: var(--primary);">{best_prob_str}</span>
      <span class="stat-sub">{best_match_str}</span>
    </div>
    <div class="stat-card">
      <span class="stat-label">Combinés Disponibles</span>
      <span class="stat-val" id="stat-combos-count">{len(combos)}</span>
      <span class="stat-sub">2 à 4 jambes · 1 seul book</span>
    </div>
  </div>

  <!-- Tabs Navigation -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('probables')">
      🎯 Plus Probables <span class="tab-count" id="count-probables">{len(rows)}</span>
    </button>
    <button class="tab-btn" onclick="switchTab('value')">
      💎 Value Bets (EV &gt; 0) <span class="tab-count" id="count-value">{len([r for r in rows if r['ev'] > 0])}</span>
    </button>
    <button class="tab-btn" onclick="switchTab('combos')">
      🔗 Combinés Filtrés <span class="tab-count">{len(combos)}</span>
    </button>
    <button class="tab-btn" onclick="switchTab('journal')">
      📊 Suivi & Journal CLV <span class="tab-count">{stats.get('total_signals', 0)}</span>
    </button>
    <button class="tab-btn" onclick="switchTab('methodo')">
      ℹ️ Méthodologie & Risque
    </button>
  </div>

  <!-- Date Timeline Bar -->
  <div class="date-bar" id="date-bar">
    <div class="date-presets">
      <button class="date-pill active" id="date-pill-all" onclick="setDateFilter('all')">
        🌐 Tous les jours <span class="pill-count" id="count-date-all">0</span>
      </button>
      <button class="date-pill" id="date-pill-yesterday" onclick="setDateFilter('yesterday')">
        ⏪ Hier <span class="pill-count" id="count-date-yesterday">0</span>
      </button>
      <button class="date-pill" id="date-pill-today" onclick="setDateFilter('today')">
        ⚡ Aujourd'hui <span class="pill-count" id="count-date-today">0</span>
      </button>
      <button class="date-pill" id="date-pill-tomorrow" onclick="setDateFilter('tomorrow')">
        ⏩ Demain <span class="pill-count" id="count-date-tomorrow">0</span>
      </button>
    </div>
    <div class="date-picker-wrap">
      <span style="font-size: 13px; color: var(--text-muted);">📅 Calendrier :</span>
      <input type="date" class="date-input" id="custom-date-picker" onchange="onCustomDateChange(this.value)">
      <button class="btn-clear-date" id="btn-clear-date" onclick="clearDateFilter()" title="Réinitialiser la date" style="display: none;">&times;</button>
    </div>
  </div>

  <!-- Filter & Search Bar -->
  <div class="filter-panel" id="filter-bar">
    <input type="text" class="search-input" id="search-box" placeholder="🔍 Rechercher une équipe, un match..." oninput="applyFilters()">
    <select class="select-dropdown" id="market-filter" onchange="applyFilters()">
      <option value="">Tous les types de paris</option>
      <option value="1X2">🏆 Résultat du match (1X2)</option>
      <option value="Buts">⚽ Nombre de Buts (Over/Under)</option>
      <option value="marquent">🤝 Les 2 équipes marquent</option>
      <option value="Remboursé">🛡️ Remboursé si Nul (DNB)</option>
    </select>
    <select class="select-dropdown" id="league-filter" onchange="applyFilters()">
      <option value="">Toutes les compétitions</option>
    </select>
    <select class="select-dropdown" id="odds-filter" onchange="applyFilters()">
      <option value="all">Toutes les cotes</option>
      <option value="low">Favoris lourds (Cote &lt; 1.30)</option>
      <option value="mid">Favoris moyens (1.30 - 1.80)</option>
      <option value="high">Outsiders (&gt; 1.80)</option>
    </select>
    <select class="select-dropdown" id="status-filter" onchange="applyFilters()">
      <option value="">Tous les statuts</option>
      <option value="UPCOMING">⏳ À venir</option>
      <option value="LIVE">🔴 En direct (Live)</option>
      <option value="FINISHED">🏁 Terminés (Scores)</option>
      <option value="WON">✅ Pronostics Gagnés</option>
      <option value="LOST">❌ Pronostics Perdus</option>
    </select>
    <div style="margin-left: auto; display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 13px; color: var(--text-muted);">Trier par:</span>
      <select class="select-dropdown" id="sort-selector" onchange="applyFilters()">
        <option value="prob-desc">Probabilité (Max → Min)</option>
        <option value="ev-desc">EV (Meilleure → Moins bonne)</option>
        <option value="odds-asc">Cote (Plus basse → Plus haute)</option>
      </select>
    </div>
  </div>

  <!-- Tab 1: Plus Probables -->
  <div id="tab-probables" class="tab-content">
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Compétition</th>
            <th>Match</th>
            <th>Type & Pronostic</th>
            <th class="right">Chance (Marché)</th>
            <th class="right">Meilleure Cote</th>
            <th>Bookmaker</th>
            <th class="right">EV</th>
            <th class="right">Kelly (1/4)</th>
            <th class="right">Action</th>
          </tr>
        </thead>
        <tbody id="table-probables-body">
          <!-- Rempli par JavaScript -->
        </tbody>
      </table>
    </div>
  </div>

  <!-- Tab 2: Value Bets -->
  <div id="tab-value" class="tab-content" style="display: none;">
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Compétition</th>
            <th>Match</th>
            <th>Type & Pronostic</th>
            <th class="right">Chance (Marché)</th>
            <th class="right">Cote Offerte</th>
            <th>Bookmaker</th>
            <th class="right">Edge / EV</th>
            <th class="right">Mise Kelly Conseillée</th>
            <th class="right">Action</th>
          </tr>
        </thead>
        <tbody id="table-value-body">
          <!-- Rempli par JavaScript -->
        </tbody>
      </table>
    </div>
    <div id="value-empty-msg" style="display: none; padding: 40px; text-align: center; color: var(--text-muted);">
      <p style="font-size: 16px; margin-bottom: 6px;">Aucun Value Bet détecté sur ce marché actuellement.</p>
      <p style="font-size: 13px;">C'est le résultat normal et honnête : les marchés majeurs sont très efficients. Les cotes offertes couvrent rarement la marge du bookmaker.</p>
    </div>
  </div>

  <!-- Tab 3: Combinés -->
  <div id="tab-combos" class="tab-content" style="display: none;">
    <div id="combos-container">
      <!-- Rempli par JavaScript -->
    </div>
  </div>

  <!-- Tab 4: Journal & CLV -->
  <div id="tab-journal" class="tab-content" style="display: none;">
    <div class="stats-bar">
      <div class="stat-card">
        <span class="stat-label">Signaux Journalisés</span>
        <span class="stat-val">{stats.get('total_signals', 0)}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Signaux EV Positive</span>
        <span class="stat-val" style="color: var(--success);">{stats.get('positive_ev_count', 0)}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">EV Moyen Observé</span>
        <span class="stat-val mono">{avg_ev_str}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Base SQLite</span>
        <span class="stat-val" style="font-size: 16px;">data/journal.db</span>
        <span class="stat-sub">Append-only · Traçabilité CLV</span>
      </div>
    </div>
    <div class="edu-card">
      <h3>Suivi du Closing Line Value (CLV)</h3>
      <p>
        Selon la contrainte scientifique C7, la rentabilité à court terme (P&L) est trop bruitée pour attester d'un avantage réel.
        Le <b>Closing Line Value (CLV)</b> mesure l'écart entre la cote prise et la cote de clôture de référence (Pinnacle/sharp).
        Si la cote de clôture est systématiquement inférieure à la cote prise, l'edge mathématique est démontré.
      </p>
    </div>
  </div>

  <!-- Tab 5: Méthodologie -->
  <div id="tab-methodo" class="tab-content" style="display: none;">
    <div class="edu-card">
      <h3>1. Pourquoi deux chiffres au lieu d'un (Probabilité vs EV)</h3>
      <p>
        Plus une sélection est favorite, plus sa <b>probabilité de passer est élevée</b>, mais plus l'<b>espérance de gain (EV) s'effondre</b>.
        Pourquoi ? Parce que la marge du bookmaker (overround) pénalise mécaniquement le parieur.
        Une plateforme qui n'afficherait que la probabilité inciterait mécaniquement aux paris les plus perdants sur le long terme.
      </p>
      <h3 style="margin-top: 18px;">2. L'amplification destructrice des combinés</h3>
      <p>
        Sur un simple, la marge du bookmaker est typiquement de ~5 à 7%.
        Sur un combiné de 3 matches, la marge composée monte à ~17%. Sur 5 matches, elle dépasse 27%.
        C'est pourquoi combiner des cotes à 1.15 ou 1.25 mène quasi-invariablement à la ruine, même si 80% des combinés semblent « faciles ».
      </p>
      <h3 style="margin-top: 18px;">3. Critère de Kelly Fractionnaire</h3>
      <p>
        En cas d'opportunité à espérance positive (EV &gt; 0), la mise recommandée est calculée selon le <b>Quarter-Kelly (f*/4)</b>, plafonné à 5% du capital disponible. Cela protège mathématiquement la bankroll contre les séquences de pertes inévitables.
      </p>
    </div>
  </div>

  <!-- Bet Slip Floating Drawer -->
  <div class="slip-drawer" id="bet-slip">
    <div class="slip-header" onclick="toggleSlip()">
      <span>🎟️ Mon Coupon & Simulateur (<span id="slip-count">0</span>)</span>
      <span id="slip-toggle-icon">▼</span>
    </div>
    <div class="slip-body">
      <div id="slip-items">
        <div style="text-align: center; color: var(--text-muted); padding: 14px 0; font-size: 13px;">
          Cliquez sur <b>+ Coupon</b> sur n'importe quelle ligne pour tester un combiné personnalisé.
        </div>
      </div>
      <div class="slip-calc" id="slip-calc-panel" style="display: none;">
        <div class="calc-row">
          <span style="color: var(--text-muted);">Probabilité cumulée :</span>
          <b class="mono" id="slip-cumul-prob">0.0%</b>
        </div>
        <div class="calc-row">
          <span style="color: var(--text-muted);">Cote combinée :</span>
          <b class="mono" id="slip-cumul-odds">1.00</b>
        </div>
        <div class="calc-row">
          <span style="color: var(--text-muted);">Espérance de gain (EV) :</span>
          <b class="mono" id="slip-cumul-ev">0.0%</b>
        </div>
        <div class="calc-row" style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed #334155;">
          <span>Votre Bankroll (€) :</span>
          <input type="number" class="stake-input" id="user-bankroll" value="500" oninput="updateSlipCalcs()">
        </div>
        <div class="calc-row">
          <span>Mise conseillée (Kelly) :</span>
          <b class="mono" style="color: var(--success);" id="slip-kelly-stake">0.00 €</b>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
  window.APP_DATA = {json_embedded};

  let slipSelections = [];
  let currentDateFilter = 'all';
  let customDateValue = '';

  function initApp() {{
    populateLeagues();
    updateDateCounts();
    applyFilters();
  }}

  function populateLeagues() {{
    const sel = document.getElementById('league-filter');
    (window.APP_DATA.leagues || []).forEach(lg => {{
      const opt = document.createElement('option');
      opt.value = lg.name;
      opt.textContent = `${{lg.flag || '⚽'}} ${{lg.name}} (${{lg.country}})`;
      sel.appendChild(opt);
    }});
  }}

  function switchTab(tabId) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    
    event.currentTarget.classList.add('active');
    document.getElementById('tab-' + tabId).style.display = 'block';

    const filterBar = document.getElementById('filter-bar');
    const dateBar = document.getElementById('date-bar');
    if (tabId === 'probables' || tabId === 'value') {{
      filterBar.style.display = 'flex';
      if (dateBar) dateBar.style.display = 'flex';
    }} else {{
      filterBar.style.display = 'none';
      if (dateBar) dateBar.style.display = 'none';
    }}
  }}

  function formatDateLocal(d) {{
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${{y}}-${{m}}-${{day}}`;
  }}

  function getEventDateStr(isoStr) {{
    if (!isoStr) return '';
    try {{
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return '';
      return formatDateLocal(d);
    }} catch (e) {{
      return '';
    }}
  }}

  function setDateFilter(mode) {{
    currentDateFilter = mode;
    customDateValue = '';
    const dateInput = document.getElementById('custom-date-picker');
    if (dateInput) dateInput.value = '';
    const clearBtn = document.getElementById('btn-clear-date');
    if (clearBtn) clearBtn.style.display = 'none';

    document.querySelectorAll('.date-pill').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('date-pill-' + mode);
    if (activeBtn) activeBtn.classList.add('active');

    applyFilters();
  }}

  function onCustomDateChange(val) {{
    if (!val) {{
      setDateFilter('all');
      return;
    }}
    currentDateFilter = 'custom';
    customDateValue = val;
    document.querySelectorAll('.date-pill').forEach(btn => btn.classList.remove('active'));
    const clearBtn = document.getElementById('btn-clear-date');
    if (clearBtn) clearBtn.style.display = 'inline-block';

    applyFilters();
  }}

  function clearDateFilter() {{
    setDateFilter('all');
  }}

  function updateDateCounts() {{
    const items = window.APP_DATA.selections || [];
    const now = new Date();
    const todayStr = formatDateLocal(now);
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = formatDateLocal(yesterday);
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = formatDateLocal(tomorrow);

    let cntAll = items.length;
    let cntYest = 0;
    let cntToday = 0;
    let cntTom = 0;

    items.forEach(r => {{
      const d = getEventDateStr(r.kickoff);
      if (d === yesterdayStr) cntYest++;
      else if (d === todayStr) cntToday++;
      else if (d === tomorrowStr) cntTom++;
    }});

    const elAll = document.getElementById('count-date-all');
    if (elAll) elAll.textContent = cntAll;
    const elYest = document.getElementById('count-date-yesterday');
    if (elYest) elYest.textContent = cntYest;
    const elToday = document.getElementById('count-date-today');
    if (elToday) elToday.textContent = cntToday;
    const elTom = document.getElementById('count-date-tomorrow');
    if (elTom) elTom.textContent = cntTom;
  }}

  function formatKickoff(isoStr) {{
    if (!isoStr) return '';
    try {{
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return '';
      const now = new Date();
      const isToday = d.toDateString() === now.toDateString();
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      const isTomorrow = d.toDateString() === tomorrow.toDateString();

      const timeStr = d.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
      if (isToday) return `Aujourd'hui ${{timeStr}}`;
      if (isTomorrow) return `Demain ${{timeStr}}`;

      const days = ['Dim.', 'Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.'];
      const dayName = days[d.getDay()];
      const dateStr = `${{d.getDate().toString().padStart(2, '0')}}/${{(d.getMonth() + 1).toString().padStart(2, '0')}}`;
      return `${{dayName}} ${{dateStr}} ${{timeStr}}`;
    }} catch (e) {{
      return '';
    }}
  }}

  function renderStatusBadge(r) {{
    if (r.status === 'LIVE') {{
      return `<span class="badge badge-live">🔴 En direct ${{r.score_str ? escapeHtml(r.score_str) : ''}}</span>`;
    }} else if (r.status === 'FINISHED') {{
      return `<span class="badge badge-finished">🏁 Terminé ${{r.score_str ? `(${{escapeHtml(r.score_str)}})` : ''}}</span>`;
    }} else {{
      return `<span class="badge badge-upcoming">⏳ À venir</span>`;
    }}
  }}

  function renderOutcomeBadge(r) {{
    if (r.outcome === 'WON') {{
      return `<span class="badge badge-won">✅ Gagné</span>`;
    }} else if (r.outcome === 'LOST') {{
      return `<span class="badge badge-lost">❌ Perdu</span>`;
    }} else if (r.outcome === 'PUSH') {{
      return `<span class="badge badge-push">🛡️ Remboursé</span>`;
    }}
    return '';
  }}

  function applyFilters() {{
    const query = document.getElementById('search-box').value.toLowerCase();
    const market = document.getElementById('market-filter')?.value;
    const league = document.getElementById('league-filter').value;
    const oddsGroup = document.getElementById('odds-filter').value;
    const statusFilter = document.getElementById('status-filter')?.value;
    const sortBy = document.getElementById('sort-selector').value;

    let items = [...(window.APP_DATA.selections || [])];

    const now = new Date();
    const todayStr = formatDateLocal(now);
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = formatDateLocal(yesterday);
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = formatDateLocal(tomorrow);

    if (currentDateFilter === 'today') {{
      items = items.filter(r => getEventDateStr(r.kickoff) === todayStr);
    }} else if (currentDateFilter === 'yesterday') {{
      items = items.filter(r => getEventDateStr(r.kickoff) === yesterdayStr);
    }} else if (currentDateFilter === 'tomorrow') {{
      items = items.filter(r => getEventDateStr(r.kickoff) === tomorrowStr);
    }} else if (currentDateFilter === 'custom' && customDateValue) {{
      items = items.filter(r => getEventDateStr(r.kickoff) === customDateValue);
    }}

    if (query) {{
      items = items.filter(r => (r.match + ' ' + r.sel + ' ' + (r.market_type || '')).toLowerCase().includes(query));
    }}
    if (market) {{
      items = items.filter(r => (r.market_type || '').includes(market));
    }}
    if (league) {{
      items = items.filter(r => r.league === league);
    }}
    if (statusFilter) {{
      if (statusFilter === 'WON' || statusFilter === 'LOST') {{
        items = items.filter(r => r.outcome === statusFilter);
      }} else {{
        items = items.filter(r => r.status === statusFilter);
      }}
    }}
    if (oddsGroup === 'low') {{
      items = items.filter(r => r.price < 1.30);
    }} else if (oddsGroup === 'mid') {{
      items = items.filter(r => r.price >= 1.30 && r.price <= 1.80);
    }} else if (oddsGroup === 'high') {{
      items = items.filter(r => r.price > 1.80);
    }}

    if (sortBy === 'prob-desc') {{
      items.sort((a, b) => b.prob - a.prob);
    }} else if (sortBy === 'ev-desc') {{
      items.sort((a, b) => b.ev - a.ev);
    }} else if (sortBy === 'odds-asc') {{
      items.sort((a, b) => a.price - b.price);
    }}

    renderProbablesTable(items);
    renderValueTable(items.filter(r => r.ev > 0));
    renderCombos();
  }}

  function renderProbablesTable(rows) {{
    const tbody = document.getElementById('table-probables-body');
    tbody.innerHTML = '';
    rows.forEach(r => {{
      const tr = document.createElement('tr');
      const evClass = r.ev >= 0 ? 'badge-pos' : r.ev > -0.06 ? 'badge-warn' : 'badge-neg';
      const inSlip = slipSelections.some(s => s.match === r.match && s.sel === r.sel);
      
      tr.innerHTML = `
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${{r.badge_url ? `<img src="${{r.badge_url}}" width="20" height="15" style="border-radius: 3px; object-fit: cover; box-shadow: 0 1px 3px rgba(0,0,0,0.5);" onerror="this.style.display='none'">` : ''}}
            <div>
              <div style="font-weight: 600; color: #fff;">${{escapeHtml(r.league)}}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${{r.flag || '⚽'}} ${{escapeHtml(r.country || '')}}</div>
            </div>
          </div>
        </td>
        <td style="font-weight: 600;">
          <div>${{escapeHtml(r.match)}}</div>
          <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap;">
            <span style="font-size: 11px; color: var(--text-muted);">${{formatKickoff(r.kickoff)}}</span>
            ${{renderStatusBadge(r)}}
          </div>
        </td>
        <td>
          ${{r.market_type ? `<div style="margin-bottom: 4px;"><span class="badge badge-market">${{escapeHtml(r.market_type)}}</span></div>` : ''}}
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span style="color: var(--primary); font-weight: 600;">${{escapeHtml(r.sel)}}</span>
            ${{renderOutcomeBadge(r)}}
          </div>
        </td>
        <td class="right">
          <div class="prob-bar-container" style="justify-content: flex-end;">
            <div class="prob-bar"><div class="prob-fill" style="width: ${{Math.round(r.prob * 100)}}%;"></div></div>
            <span class="mono" style="font-weight: 700;">${{(r.prob * 100).toFixed(1)}}%</span>
          </div>
        </td>
        <td class="right mono" style="font-weight: 700; color: #fff;">${{r.price.toFixed(2)}}</td>
        <td>
          <span>${{escapeHtml(r.book)}}</span>
          <span style="font-size: 11px; color: var(--text-muted); margin-left: 4px;">(${{(r.book_margin * 100).toFixed(1)}}%)</span>
        </td>
        <td class="right"><span class="badge ${{evClass}} mono">${{r.ev >= 0 ? '+' : ''}}${{(r.ev * 100).toFixed(1)}}%</span></td>
        <td class="right mono" style="color: var(--text-muted);">${{r.kelly_quarter > 0 ? (r.kelly_quarter * 100).toFixed(1) + '%' : '—'}}</td>
        <td class="right">
          <button class="btn-add ${{inSlip ? 'in-slip' : ''}}" onclick='toggleSlipItem(${{JSON.stringify(r)}})'>
            ${{inSlip ? '✓ Ajouté' : '+ Coupon'}}
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    }});
  }}

  function renderValueTable(rows) {{
    const tbody = document.getElementById('table-value-body');
    const emptyMsg = document.getElementById('value-empty-msg');
    tbody.innerHTML = '';
    if (rows.length === 0) {{
      emptyMsg.style.display = 'block';
      return;
    }}
    emptyMsg.style.display = 'none';
    rows.forEach(r => {{
      const tr = document.createElement('tr');
      const inSlip = slipSelections.some(s => s.match === r.match && s.sel === r.sel);
      tr.innerHTML = `
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${{r.badge_url ? `<img src="${{r.badge_url}}" width="20" height="15" style="border-radius: 3px; object-fit: cover; box-shadow: 0 1px 3px rgba(0,0,0,0.5);" onerror="this.style.display='none'">` : ''}}
            <div>
              <div style="font-weight: 600; color: #fff;">${{escapeHtml(r.league)}}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${{r.flag || '⚽'}} ${{escapeHtml(r.country || '')}}</div>
            </div>
          </div>
        </td>
        <td style="font-weight: 600;">
          <div>${{escapeHtml(r.match)}}</div>
          <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap;">
            <span style="font-size: 11px; color: var(--text-muted);">${{formatKickoff(r.kickoff)}}</span>
            ${{renderStatusBadge(r)}}
          </div>
        </td>
        <td>
          ${{r.market_type ? `<div style="margin-bottom: 4px;"><span class="badge badge-market">${{escapeHtml(r.market_type)}}</span></div>` : ''}}
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span style="color: var(--success); font-weight: 600;">${{escapeHtml(r.sel)}}</span>
            ${{renderOutcomeBadge(r)}}
          </div>
        </td>
        <td class="right mono" style="font-weight: 700;">${{(r.prob * 100).toFixed(1)}}%</td>
        <td class="right mono" style="font-weight: 700; color: #fff;">${{r.price.toFixed(2)}}</td>
        <td>${{escapeHtml(r.book)}}</td>
        <td class="right"><span class="badge badge-pos mono">+${{(r.ev * 100).toFixed(1)}}%</span></td>
        <td class="right mono" style="font-weight: 700; color: var(--success);">${{(r.kelly_quarter * 100).toFixed(1)}}% du capital</td>
        <td class="right">
          <button class="btn-add ${{inSlip ? 'in-slip' : ''}}" onclick='toggleSlipItem(${{JSON.stringify(r)}})'>
            ${{inSlip ? '✓ Ajouté' : '+ Coupon'}}
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    }});
  }}

  function renderCombos() {{
    const container = document.getElementById('combos-container');
    container.innerHTML = '';
    const combos = window.APP_DATA.combos || [];
    if (combos.length === 0) {{
      container.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--text-muted);">Aucun combiné ne satisfait les contraintes de filtrage (prob &ge; 70%, 1 book commun).</div>';
      return;
    }}
    combos.forEach(c => {{
      const card = document.createElement('div');
      card.className = 'combo-card';
      const evBadge = c.ev >= 0 ? 'badge-pos' : c.ev > -0.12 ? 'badge-warn' : 'badge-neg';
      card.innerHTML = `
        <div class="combo-header">
          <div>
            <span class="badge badge-gray" style="font-size: 13px;">Combiné ${{c.n}} Jambes</span>
            <span style="margin-left: 8px; color: var(--text-muted); font-size: 13px;">Bookmaker : <b>${{escapeHtml(c.book)}}</b></span>
          </div>
          <div style="display: flex; gap: 12px; align-items: center;">
            <div style="text-align: right;">
              <span style="font-size: 11px; color: var(--text-muted); display: block;">PROBABILITÉ</span>
              <b class="mono" style="color: var(--primary); font-size: 16px;">${{(c.prob * 100).toFixed(1)}}%</b>
            </div>
            <div style="text-align: right;">
              <span style="font-size: 11px; color: var(--text-muted); display: block;">COTE TOTALE</span>
              <b class="mono" style="color: #fff; font-size: 16px;">${{c.odds.toFixed(2)}}</b>
            </div>
            <span class="badge ${{evBadge}} mono" style="font-size: 14px;">${{c.ev >= 0 ? '+' : ''}}${{(c.ev * 100).toFixed(1)}}% EV</span>
          </div>
        </div>
        <div class="legs-list">
          ${{c.legs.map(l => `<div class="leg-item"><span>⚽ ${{escapeHtml(l)}}</span></div>`).join('')}}
        </div>
      `;
      container.appendChild(card);
    }});
  }}

  function toggleSlipItem(item) {{
    const idx = slipSelections.findIndex(s => s.match === item.match && s.sel === item.sel);
    if (idx >= 0) {{
      slipSelections.splice(idx, 1);
    }} else {{
      slipSelections.push(item);
    }}
    updateSlipUI();
    applyFilters();
  }}

  function updateSlipUI() {{
    const countEl = document.getElementById('slip-count');
    const itemsEl = document.getElementById('slip-items');
    const calcPanel = document.getElementById('slip-calc-panel');
    countEl.textContent = slipSelections.length;

    if (slipSelections.length === 0) {{
      itemsEl.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 14px 0; font-size: 13px;">Cliquez sur <b>+ Coupon</b> pour ajouter des sélections.</div>';
      calcPanel.style.display = 'none';
      return;
    }}

    calcPanel.style.display = 'flex';
    itemsEl.innerHTML = '';
    slipSelections.forEach((s, idx) => {{
      const div = document.createElement('div');
      div.className = 'slip-item';
      div.innerHTML = `
        <div>
          <div style="font-size: 12px; font-weight: 600;">${{escapeHtml(s.match)}}</div>
          <div style="font-size: 12px; color: var(--primary);">${{escapeHtml(s.sel)}} @ ${{s.price.toFixed(2)}} (${{(s.prob*100).toFixed(0)}}%)</div>
        </div>
        <button onclick="removeSlipAt(${{idx}})" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 16px;">&times;</button>
      `;
      itemsEl.appendChild(div);
    }});

    updateSlipCalcs();
  }}

  function removeSlipAt(idx) {{
    slipSelections.splice(idx, 1);
    updateSlipUI();
    applyFilters();
  }}

  function updateSlipCalcs() {{
    if (slipSelections.length === 0) return;
    let prob = 1.0;
    let odds = 1.0;
    slipSelections.forEach(s => {{
      prob *= s.prob;
      odds *= s.price;
    }});
    const ev = (prob * odds) - 1.0;

    document.getElementById('slip-cumul-prob').textContent = (prob * 100).toFixed(1) + '%';
    document.getElementById('slip-cumul-odds').textContent = odds.toFixed(2);
    
    const evEl = document.getElementById('slip-cumul-ev');
    evEl.textContent = (ev >= 0 ? '+' : '') + (ev * 100).toFixed(1) + '%';
    evEl.style.color = ev >= 0 ? 'var(--success)' : (ev > -0.1 ? 'var(--warning)' : 'var(--danger)');

    // Kelly
    const bankroll = parseFloat(document.getElementById('user-bankroll').value) || 0;
    let stake = 0;
    if (ev > 0 && odds > 1.0) {{
      const b = odds - 1.0;
      const q = 1.0 - prob;
      const fStar = (prob * b - q) / b;
      stake = Math.max(0, Math.min(bankroll * fStar * 0.25, bankroll * 0.05));
    }}
    document.getElementById('slip-kelly-stake').textContent = stake > 0 ? stake.toFixed(2) + ' €' : '0.00 € (EV négative)';
  }}

  function toggleSlip() {{
    document.getElementById('bet-slip').classList.toggle('slip-collapsed');
  }}

  async function triggerManualRefresh() {{
    let key = localStorage.getItem('refresh_key');
    if (!key) {{
      key = prompt("Clé REFRESH_KEY configurée dans votre environnement (.env) :");
      if (!key) return;
      localStorage.setItem('refresh_key', key);
    }}
    const btn = document.getElementById('btn-force-refresh');
    if (btn) {{
      btn.innerText = "⏳ En cours...";
      btn.disabled = true;
    }}
    try {{
      const resp = await fetch(`/api/v1/refresh?key=${{encodeURIComponent(key)}}`, {{ method: 'POST' }});
      const data = await resp.json();
      if (resp.ok && data.success) {{
        alert("✅ Actualisation forcée réussie ! Rechargement des données fraîches...");
        window.location.reload();
      }} else if (resp.status === 401) {{
        localStorage.removeItem('refresh_key');
        alert("❌ Clé REFRESH_KEY non valide.");
      }} else {{
        alert(`❌ Erreur : ${{data.message || data.error || 'Échec de rafraîchissement'}}`);
      }}
    }} catch (e) {{
      alert(`❌ Erreur réseau : ${{e.message}}`);
    }} finally {{
      if (btn) {{
        btn.innerText = "🔄 Actualiser";
        btn.disabled = false;
      }}
    }}
  }}

  window.addEventListener('DOMContentLoaded', initApp);
</script>
</body>
</html>"""


# ------------------------------------------------------------------ Point d'entrée
def main():
    ap = argparse.ArgumentParser(description="Générateur de site bet-prediction")
    ap.add_argument("--out", default="_site/index.html", help="Chemin du fichier HTML de sortie")
    ap.add_argument("--demo", action="store_true", help="Utiliser le flux de démonstration")
    ap.add_argument("--no-journal", action="store_true", help="Ne pas consigner dans la base SQLite")
    ap.add_argument("--force", action="store_true", help="Forcer une actualisation immédiate sans utiliser le cache")
    a = ap.parse_args()

    if a.force:
        os.environ["FORCE_REFRESH"] = "1"

    demo = a.demo
    if not demo:
        try:
            events, source = collect()
        except Exception as exc:
            print(f"  [!] collecte impossible ({exc}) — bascule en mode démonstration", file=sys.stderr)
            demo = True

    if demo:
        events, source = norm_theodds(FIX_DEMO), "données de démonstration (multi-ligues)"

    rows = modele_commun(events)
    if not rows:
        print("  [!] aucune ligne exploitable", file=sys.stderr)
        rows = []

    # Enrichissement avec les scores récents (en direct et terminés) et évaluation des pronostics
    theodds_key = (os.environ.get("THEODDSAPI_KEY") or os.environ.get("ODDS_API_KEY") or "").strip().strip('"').strip("'")
    if theodds_key and not demo:
        try:
            scores_map = collect_scores(theodds_key)
            enrich_rows_with_scores(rows, scores_map)
        except Exception as exc:
            print(f"  [!] scores non disponibles : {exc}", file=sys.stderr)
            enrich_rows_with_scores(rows, {})
    else:
        enrich_rows_with_scores(rows, {})

    combos = build_combos(events)

    # Journalisation dans la base SQLite append-only
    if not a.no_journal and rows:
        try:
            inserted = journal.log_recommendations(rows)
            stats = journal.get_stats()
        except Exception as exc:
            print(f"  [!] journal SQLite indisponible : {exc}", file=sys.stderr)
            stats = {"total_signals": len(rows), "positive_ev_count": len([r for r in rows if r["ev"] > 0])}
    else:
        stats = {"total_signals": len(rows), "positive_ev_count": len([r for r in rows if r["ev"] > 0])}

    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    html_content = generate_html(rows, combos, stats, source, demo, now_str)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Également exporter data.json à côté de index.html pour les clients API ou headless
    json_path = os.path.join(os.path.dirname(os.path.abspath(a.out)), "data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": now_str,
            "source": source,
            "demo": demo,
            "stats": stats,
            "selections": rows,
            "combos": [{k: v for k, v in c.items() if k != "raw_legs"} for c in combos]
        }, f, indent=2, ensure_ascii=False)

    print(f"[OK] {len(rows)} selections | {len(combos)} combines optimises | {len(events)} evenements -> {a.out}")


if __name__ == "__main__":
    main()
