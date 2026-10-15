#!/usr/bin/env python3
"""
build_site.py — generee la page publique a partir des cotes du marche.

Aucune dependance externe : uniquement la bibliotheque standard.
Sources (par ordre de preference, selon les cles presentes) :
    ODDSPAPI_KEY     -> api.oddspapi.io/v4    1 requete = tout le board
    THEODDSAPI_KEY   -> api.the-odds-api.com  1 appel = 1 ligue

Usage :
    python3 src/build_site.py                      # ecrit dans _site/
    python3 src/build_site.py --out site           # ecrit dans site/
    python3 src/build_site.py --demo               # donnees embarquees
"""
from __future__ import annotations
import argparse, datetime, html, itertools, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feeds                                                    # noqa: E402
from feeds import norm_oddspapi, norm_theodds, modele_commun, pick_sharp, get, KEYS   # noqa: E402

MIN_PROB_LEG = 0.75
MAX_LEGS = 4
TOP_BOARD = 30
MAX_MARGIN = 0.08

# slugs OddsPapi du perimetre cible
ODDSPAPI_SLUGS = {
    "premier-league", "championship", "england-league-one", "england-league-two",
    "ligue-1", "ligue-2", "bundesliga", "bundesliga-2", "laliga", "laliga-2",
    "serie-a", "serie-b", "eredivisie", "primeira-liga", "jupiler-pro-league",
    "super-lig", "super-league-greece", "austrian-bundesliga", "super-league",
    "superliga", "eliteserien", "allsvenskan", "veikkausliiga", "ekstraklasa",
    "scottish-premiership", "league-of-ireland",
}
# cles The Odds API du meme perimetre
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
        raise RuntimeError("aucun tournoi du perimetre dans la reponse /tournaments")
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
    if KEYS["oddspapi"]:
        try:
            return collect_oddspapi(KEYS["oddspapi"])
        except Exception as exc:
            print(f"  [!] oddspapi : {exc}", file=sys.stderr)
    if KEYS["theoddsapi"]:
        try:
            return collect_theodds(KEYS["theoddsapi"])
        except Exception as exc:
            print(f"  [!] theoddsapi : {exc}", file=sys.stderr)
    raise RuntimeError("aucune source disponible")


# ------------------------------------------------------------------ combines
def build_combos(events):
    legs = []
    for ev in events:
        sharp = pick_sharp(ev["books"])
        if not sharp:
            continue
        cand = [s for s, p in sharp["probs"].items() if p >= MIN_PROB_LEG]
        if not cand:
            continue
        sel = max(cand, key=lambda s: sharp["probs"][s])
        prices = {b["name"]: b["prices"][sel] for b in ev["books"]
                  if sel in b["prices"] and b["margin"] < MAX_MARGIN}
        if prices:
            legs.append({"sel": sel, "prob": sharp["probs"][sel], "prices": prices,
                         "match": f'{ev.get("home")} - {ev.get("away")}'})
    legs.sort(key=lambda l: -l["prob"])
    out = []
    for n in range(2, min(MAX_LEGS, len(legs)) + 1):
        best = None
        for combo in itertools.combinations(legs, n):
            prob = 1.0
            for c in combo:
                prob *= c["prob"]
            books = set(combo[0]["prices"])
            for c in combo[1:]:
                books &= set(c["prices"])
            for bk in books:
                odds = 1.0
                for c in combo:
                    odds *= c["prices"][bk]
                if best is None or prob > best["prob"]:
                    best = {"n": n, "prob": prob, "odds": odds, "ev": prob * odds - 1,
                            "book": bk, "legs": [c["sel"] for c in combo]}
        if best:
            out.append(best)
    return out


# ------------------------------------------------------------------ rendu
def age(v):
    if v is None:
        return "—"
    s = int(abs(v))
    return f"{s//60} min" if s < 3600 else f"{s//3600} h"


def render(rows, combos, source, demo, out_path):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    ev_cls = lambda e: ("neg3" if e < -0.15 else "neg2" if e < -0.08
                        else "neg1" if e < 0 else "pos")
    table = "\n".join(
        f'<tr><td>{html.escape(r["match"])}</td><td class="sel">{html.escape(str(r["sel"]))}</td>'
        f'<td class="n big">{r["prob"]:.1%}</td><td class="n">{r["price"]:.2f}</td>'
        f'<td>{html.escape(str(r["book"]))}<span class="dim"> {r["book_margin"]:.1%}</span></td>'
        f'<td class="n dim">{age(r["age_s"])}</td>'
        f'<td class="n dim">{r["limit"] or "—"}</td>'
        f'<td class="n {ev_cls(r["ev"])}">{r["ev"]:+.1%}</td></tr>'
        for r in rows[:TOP_BOARD])
    ctable = "\n".join(
        f'<tr><td class="n">{c["n"]}</td><td class="n big">{c["prob"]:.1%}</td>'
        f'<td class="n">{c["odds"]:.2f}</td><td>{html.escape(str(c["book"]))}</td>'
        f'<td class="n {ev_cls(c["ev"])}">{c["ev"]:+.1%}</td>'
        f'<td class="dim">{html.escape(", ".join(map(str, c["legs"])))}</td></tr>'
        for c in combos) or '<tr><td colspan="6" class="dim">Aucun combine ne remplit les conditions aujourd\'hui.</td></tr>'
    banner = ('<div class="demo">Mode démonstration — données fabriquées, '
              "aucune cote réelle. Configurez une clé API pour publier de vraies cotes.</div>"
              if demo else "")
    html_doc = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Les plus probables — {now}</title>
<meta name="description" content="Probabilités des matchs du jour, dérivées des cotes du marché. Aucune performance garantie.">
<style>
:root{{--bg:#0e1116;--panel:#161b22;--fg:#e6edf3;--dim:#8b949e;--bd:#22272e;--acc:#4493f8}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 20px 60px}}
header h1{{font-size:24px;margin:0 0 6px;letter-spacing:-.3px}}
header p{{color:var(--dim);font-size:13px;margin:0}}
.demo{{margin:16px 0;padding:11px 14px;border:1px solid #9e6a03;border-radius:8px;
background:#2d2305;color:#e3b341;font-size:13px}}
h2{{font-size:17px;margin:34px 0 4px;color:var(--acc)}}
.sub{{color:var(--dim);font-size:13px;margin:0 0 10px}}
table{{width:100%;border-collapse:collapse;margin-bottom:6px}}
th{{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.6px;
color:var(--dim);border-bottom:1px solid var(--bd);padding:8px 6px;font-weight:600}}
td{{padding:9px 6px;border-bottom:1px solid var(--bd);vertical-align:top}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.big{{font-weight:650;color:var(--acc)}}
td.sel{{font-weight:500}}
.dim{{color:var(--dim);font-size:12.5px}}
.neg1{{color:#e3b341}} .neg2{{color:#f0883e}} .neg3{{color:#f85149;font-weight:650}}
.pos{{color:#3fb950;font-weight:650}}
.note{{margin-top:34px;padding:16px 18px;border:1px solid var(--bd);border-radius:8px;
background:var(--panel);font-size:13px;color:var(--dim)}}
.note b{{color:var(--fg)}}
footer{{margin-top:26px;color:var(--dim);font-size:12px;border-top:1px solid var(--bd);padding-top:14px}}
</style></head><body><div class="wrap">
<header>
<h1>Les événements les plus probables</h1>
<p>Probabilités issues des cotes du marché, dévigorisées · source : {html.escape(source)} ·
généré le {now}</p>
</header>
{banner}
<h2>Simples — classés par chance de passer</h2>
<p class="sub">{len(rows)} sélections · chance = probabilité implicite de la référence sharp,
marge retirée</p>
<table><tr><th>Match</th><th>Sélection</th><th>Chance</th><th>Cote</th><th>Book</th>
<th>Fraîch.</th><th>Mise max</th><th>EV</th></tr>
{table}</table>

<h2>Combinés les plus probables</h2>
<p class="sub">Une seule jambe par match. La cote combinée provient d'un seul book — sinon elle n'est
pas jouable.</p>
<table><tr><th>Jambes</th><th>Chance</th><th>Cote</th><th>Book</th><th>EV</th><th>Sélections</th></tr>
{ctable}</table>

<div class="note">
<b>Comment lire cette page.</b> Les « chances » sont les probabilités du marché, marge du bookmaker
retirée — pas des pronostics. Le marché est bien calibré : un favori annoncé à 90 % gagne réellement
environ 9 fois sur 10.<br><br>
<b>La colonne EV</b> est l'espérance de gain sur la mise. Elle est le plus souvent négative parce
qu'elle contient la marge du bookmaker, et cette marge se compose avec le nombre de jambes : environ
6 % à une jambe, 17 % à trois, 27 % à cinq. C'est pourquoi la « chance de passer » et l'EV évoluent
en sens inverse.<br><br>
<b>Fraîch.</b> = ancienneté de la cote telle que déclarée par le bookmaker. Une cote ancienne n'est
pas un prix disponible. <b>Mise max</b> = montant maximal accepté à cette cote, quand la source
l'expose.<br><br>
<b>Aucune performance n'est garantie. Ceci n'est pas un conseil en investissement.</b> Les paris
comportent un risque de perte et un risque de dépendance. Jouez uniquement de l'argent dont vous
n'avez pas besoin.
</div>
<footer>Page générée automatiquement · les probabilités proviennent des cotes publiées par les
opérateurs · aucun contenu de cette page ne constitue une recommandation de pari.</footer>
</div></body></html>"""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return out_path


FIX_DEMO = [{"id": "e1", "sport_key": "soccer_epl", "commence_time": "2026-10-17T14:00:00Z",
  "home_team": "Manchester City", "away_team": "Brighton",
  "bookmakers": [
    {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-10-17T13:40:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Manchester City", "price": 1.22},
        {"name": "Brighton", "price": 12.0}, {"name": "Draw", "price": 6.4}]}]},
    {"key": "softa", "title": "SoftA", "last_update": "2026-10-17T13:52:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Manchester City", "price": 1.18},
        {"name": "Brighton", "price": 13.0}, {"name": "Draw", "price": 6.6}]}]}]},
 {"id": "e2", "sport_key": "soccer_germany_bundesliga", "commence_time": "2026-10-17T16:30:00Z",
  "home_team": "Bayern Munich", "away_team": "Mainz",
  "bookmakers": [
    {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-10-17T13:41:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Bayern Munich", "price": 1.25},
        {"name": "Mainz", "price": 10.5}, {"name": "Draw", "price": 6.0}]}]},
    {"key": "softa", "title": "SoftA", "last_update": "2026-10-17T13:50:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Bayern Munich", "price": 1.21},
        {"name": "Mainz", "price": 11.5}, {"name": "Draw", "price": 6.2}]}]}]},
 {"id": "e3", "sport_key": "soccer_france_ligue_one", "commence_time": "2026-10-17T19:00:00Z",
  "home_team": "Lille", "away_team": "Nantes",
  "bookmakers": [
    {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-10-17T13:42:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Lille", "price": 1.44},
        {"name": "Nantes", "price": 7.2}, {"name": "Draw", "price": 4.5}]}]},
    {"key": "softa", "title": "SoftA", "last_update": "2026-10-17T13:51:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Lille", "price": 1.41},
        {"name": "Nantes", "price": 7.8}, {"name": "Draw", "price": 4.7}]}]}]},
 {"id": "e4", "sport_key": "soccer_france_ligue_one", "commence_time": "2026-10-18T15:00:00Z",
  "home_team": "Paris SG", "away_team": "Strasbourg",
  "bookmakers": [
    {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-10-17T13:43:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Paris SG", "price": 1.30},
        {"name": "Strasbourg", "price": 9.5}, {"name": "Draw", "price": 5.6}]}]},
    {"key": "softa", "title": "SoftA", "last_update": "2026-10-17T13:53:00Z",
     "markets": [{"key": "h2h", "outcomes": [{"name": "Paris SG", "price": 1.26},
        {"name": "Strasbourg", "price": 10.5}, {"name": "Draw", "price": 5.9}]}]}]}]


DEMO_EVENTS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site/index.html")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    demo = a.demo
    if not demo:
        try:
            events, source = collect()
        except Exception as exc:
            print(f"  [!] collecte impossible ({exc}) — bascule en mode démonstration", file=sys.stderr)
            demo = True
    if demo:
        events, source = norm_theodds(FIX_DEMO), "données de démonstration"

    rows = modele_commun(events)
    if not rows:
        print("  [!] aucune ligne exploitable", file=sys.stderr)
        rows = []
    combos = build_combos(events)
    p = render(rows, combos, source, demo, a.out)
    print(f"{len(rows)} selections · {len(combos)} tailles de combine · {len(events)} evenements -> {p}")


if __name__ == "__main__":
    main()
