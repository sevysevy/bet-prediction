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
    "soccer_epl", "soccer_efl_champ", "soccer_england_league1", "soccer_england_league2",
    "soccer_france_ligue_one", "soccer_france_ligue_two", "soccer_germany_bundesliga",
    "soccer_germany_bundesliga2", "soccer_spain_la_liga", "soccer_spain_segunda_division",
    "soccer_italy_serie_a", "soccer_italy_serie_b", "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga", "soccer_belgium_first_div", "soccer_turkey_super_league",
    "soccer_greece_super_league", "soccer_austria_bundesliga", "soccer_switzerland_superleague",
    "soccer_denmark_superliga", "soccer_norway_eliteserien", "soccer_sweden_allsvenskan",
    "soccer_sweden_superettan", "soccer_finland_veikkausliiga", "soccer_poland_ekstraklasa",
    "soccer_spl", "soccer_league_of_ireland",
]


# ------------------------------------------------------------------ collecte
def collect_oddspapi(key):
    data, _ = get("https://api.oddspapi.io/v4/tournaments", {"sportId": 10, "apiKey": key})
    ids = [str(t["tournamentId"]) for t in data if t.get("tournamentSlug") in ODDSPAPI_SLUGS]
    if not ids:
        raise RuntimeError("aucun tournoi du périmètre dans la réponse /tournaments")
    payload, _ = get("https://api.oddspapi.io/v4/odds-by-tournaments",
                     {"tournamentIds": ",".join(ids), "oddsFormat": "decimal", "apiKey": key})
    return norm_oddspapi(payload), f"oddspapi · {len(ids)} tournois"


def collect_theodds(api_key):
    events, ok = [], []
    for s in THEODDS_KEYS:
        try:
            data, _ = get(f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                          {"apiKey": api_key, "regions": "eu,uk", "markets": "h2h",
                           "oddsFormat": "decimal"})
            events += data
            ok.append(s)
        except Exception as exc:
            print(f"  [!] {s} : {exc}", file=sys.stderr)
    return norm_theodds(events), f"the-odds-api · {len(ok)} ligues"


def collect():
    oddspapi_key = os.environ.get("ODDSPAPI_KEY")
    theodds_key = os.environ.get("THEODDSAPI_KEY") or os.environ.get("ODDS_API_KEY")

    if oddspapi_key:
        try:
            return collect_oddspapi(oddspapi_key)
        except Exception as exc:
            print(f"  [!] oddspapi : {exc}", file=sys.stderr)
    if theodds_key:
        try:
            return collect_theodds(theodds_key)
        except Exception as exc:
            print(f"  [!] theoddsapi : {exc}", file=sys.stderr)
    raise RuntimeError("aucune source disponible (renseignez ODDSPAPI_KEY ou THEODDSAPI_KEY)")


# ------------------------------------------------------------------ combinés
def build_combos(events):
    legs = []
    for ev in events:
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
    app_data = {
        "generated_at": now_str,
        "source": source,
        "demo": demo,
        "stats": stats,
        "selections": rows,
        "combos": [{k: v for k, v in c.items() if k != "raw_legs"} for c in combos],
        "leagues": sorted(list({r.get("league") for r in rows if r.get("league")}))
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
      <div style="text-align: right;">
        <span class="badge badge-gray mono">Source: {html.escape(source)}</span>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Généré à {now_str}</div>
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

  <!-- Filter & Search Bar -->
  <div class="filter-panel" id="filter-bar">
    <input type="text" class="search-input" id="search-box" placeholder="🔍 Rechercher une équipe, un match..." oninput="applyFilters()">
    <select class="select-dropdown" id="league-filter" onchange="applyFilters()">
      <option value="">Toutes les compétitions</option>
    </select>
    <select class="select-dropdown" id="odds-filter" onchange="applyFilters()">
      <option value="all">Toutes les cotes</option>
      <option value="low">Favoris lourds (Cote &lt; 1.30)</option>
      <option value="mid">Favoris moyens (1.30 - 1.80)</option>
      <option value="high">Outsiders (&gt; 1.80)</option>
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
            <th>Sélection</th>
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
            <th>Sélection</th>
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

  function initApp() {{
    populateLeagues();
    applyFilters();
  }}

  function populateLeagues() {{
    const sel = document.getElementById('league-filter');
    (window.APP_DATA.leagues || []).forEach(lg => {{
      const opt = document.createElement('option');
      opt.value = lg;
      opt.textContent = lg;
      sel.appendChild(opt);
    }});
  }}

  function switchTab(tabId) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    
    event.currentTarget.classList.add('active');
    document.getElementById('tab-' + tabId).style.display = 'block';

    const filterBar = document.getElementById('filter-bar');
    if (tabId === 'probables' || tabId === 'value') {{
      filterBar.style.display = 'flex';
    }} else {{
      filterBar.style.display = 'none';
    }}
  }}

  function applyFilters() {{
    const query = document.getElementById('search-box').value.toLowerCase();
    const league = document.getElementById('league-filter').value;
    const oddsGroup = document.getElementById('odds-filter').value;
    const sortBy = document.getElementById('sort-selector').value;

    let items = [...(window.APP_DATA.selections || [])];

    if (query) {{
      items = items.filter(r => (r.match + ' ' + r.sel).toLowerCase().includes(query));
    }}
    if (league) {{
      items = items.filter(r => r.league === league);
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
        <td><span class="badge badge-gray">${{escapeHtml(r.league)}}</span></td>
        <td style="font-weight: 600;">${{escapeHtml(r.match)}}</td>
        <td><span style="color: var(--primary); font-weight: 600;">${{escapeHtml(r.sel)}}</span></td>
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
        <td><span class="badge badge-gray">${{escapeHtml(r.league)}}</span></td>
        <td style="font-weight: 600;">${{escapeHtml(r.match)}}</td>
        <td><span style="color: var(--success); font-weight: 600;">${{escapeHtml(r.sel)}}</span></td>
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

  function escapeHtml(str) {{
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
    a = ap.parse_args()

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
