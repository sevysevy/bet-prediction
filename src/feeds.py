#!/usr/bin/env python3
"""
feeds.py — couche d'acces multi-sources + sonde de verification.

Sources couvertes :
  theoddsapi  https://api.the-odds-api.com/v4      (cout = marches x regions, PAR ligue)
  oddspapi    https://api.oddspapi.io/v4           (cout = 1 requete, TOUT le board)
  pinnapi     https://api.pinnapi.com              (Pinnacle seul, 100 req/jour gratuit)

Usage :
  python3 feeds.py selftest      # teste les normaliseurs sur les payloads documentes
  python3 feeds.py budget        # arithmetique de quota pour le perimetre cible
  python3 feeds.py probe         # interroge les cles presentes dans l'environnement
"""
from __future__ import annotations
import json, os, sys, datetime, urllib.request, urllib.parse

# ------------------------------------------------------------------ cles
KEYS = {
    "theoddsapi": os.environ.get("THEODDSAPI_KEY") or os.environ.get("ODDS_API_KEY"),
    "oddspapi":   os.environ.get("ODDSPAPI_KEY"),
    "pinnapi":    os.environ.get("PINNAPI_KEY"),
}

SHARP_HINTS = ("pinnacle", "circa", "betfair", "matchbook", "sbobet", "ibc",
               "singbet", "ps3838", "molten", "bookmaker")


# ------------------------------------------------------------------ arithmetique de quota
def theodds_cost(markets, regions):
    """The Odds API : 1 appel = 1 ligue. Cout = marches x regions."""
    return len(markets) * len(regions)


def budget(leagues=8, free_credits=500, oddspapi_free=250):
    rows = []
    for nom, mk, rg in (("1 marche, 1 region", 1, 1), ("1 marche, 2 regions", 1, 2),
                        ("1 marche, 3 regions", 1, 3), ("2 marches, 2 regions", 2, 2)):
        c = theodds_cost([0]*mk, [0]*rg)
        par_passe = c * leagues
        rows.append((nom, c, par_passe, free_credits // par_passe if par_passe else 0,
                     (free_credits // par_passe) / 30 if par_passe else 0))
    return rows


# ------------------------------------------------------------------ normalisation
def _devig(prices: dict) -> dict:
    inv = {k: 1.0 / v for k, v in prices.items()}
    over = sum(inv.values())
    return {"margin": over - 1.0, "probs": {k: v / over for k, v in inv.items()}}


def norm_theodds(payload: list) -> list:
    """Payload The Odds API -> schema commun."""
    out = []
    for ev in payload or []:
        books = []
        for b in ev.get("bookmakers", []) or []:
            for mk in b.get("markets", []) or []:
                if mk.get("key") != "h2h":
                    continue
                prices = {}
                for o in mk.get("outcomes", []) or []:
                    try:
                        p = float(o["price"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if p > 1.0:
                        prices[o.get("name")] = p
                if len(prices) < 2:
                    continue
                d = _devig(prices)
                books.append({"name": b.get("title") or b.get("key"),
                              "prices": prices, "limit": None,
                              "updated_at": b.get("last_update"),
                              "age_s": None, **d})
        if books:
            out.append({"source": "theoddsapi", "id": ev.get("id"),
                        "league": ev.get("sport_key"),
                        "home": ev.get("home_team"), "away": ev.get("away_team"),
                        "kickoff": ev.get("commence_time"), "books": books})
    return out


def norm_oddspapi(payload: list, participants=None, markets=None) -> list:
    """Payload OddsPapi (/v4/odds-by-tournaments) -> schema commun."""
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for fx in payload or []:
        books = []
        for bk, bd in (fx.get("bookmakerOdds") or {}).items():
            prices, limits, ages = {}, {}, []
            for _mid, mk in (bd.get("markets") or {}).items():
                for _oid, oc in (mk.get("outcomes") or {}).items():
                    for _pid, pl in (oc.get("players") or {}).items():
                        price = pl.get("price")
                        if not price:
                            continue
                        key = (pl.get("bookmakerOutcomeId") or _oid)
                        key = str(key).lower()
                        if key in ("home", "1"):
                            key = str(fx.get("participant1Id"))
                        elif key in ("away", "2"):
                            key = str(fx.get("participant2Id"))
                        elif key in ("draw", "x"):
                            key = "Draw"
                        if price > 1.0 and (key not in prices or price > prices[key]):
                            prices[key] = float(price)
                            lim = pl.get("limit")
                            if lim:
                                limits[key] = lim
                        if pl.get("changedAt"):
                            try:
                                t = datetime.datetime.fromisoformat(pl["changedAt"].replace("Z", "+00:00"))
                                ages.append((now - t).total_seconds())
                            except ValueError:
                                pass
            if len(prices) < 2:
                continue
            d = _devig(prices)
            books.append({"name": bk, "prices": prices, "limits": limits,
                          "updated_at": bd.get("changedAt") or fx.get("updatedAt"),
                          "age_s": min(ages) if ages else None,
                          "active": bd.get("bookmakerIsActive"), **d})
        if books:
            out.append({"source": "oddspapi", "id": fx.get("fixtureId"),
                        "league": fx.get("tournamentId"),
                        "home": str(fx.get("participant1Id")), "away": str(fx.get("participant2Id")),
                        "kickoff": fx.get("startTime"), "books": books})
    return out


# ------------------------------------------------------------------ schema commun -> reference
def pick_sharp(books):
    """Reference = le book a la marge la plus faible (auto-detection)."""
    return min(books, key=lambda b: b["margin"]) if books else None


def modele_commun(events):
    """[events] -> lignes de tableau (selection, chance, cote, book, EV, limite, age)."""
    rows = []
    for ev in events:
        sharp = pick_sharp(ev["books"])
        if not sharp:
            continue
        for sel, p in sharp["probs"].items():
            best, bb = None, None
            for b in ev["books"]:
                if b is sharp or b["margin"] >= 0.08:
                    continue
                px = b["prices"].get(sel)
                if px and (best is None or px > best):
                    best, bb = px, b
            if bb is None:
                continue
            rows.append({"match": f'{ev.get("home")} - {ev.get("away")}',
                         "sel": sel, "prob": p, "price": best, "book": bb["name"],
                         "limit": (bb.get("limits") or {}).get(sel),
                         "age_s": bb.get("age_s"), "book_margin": bb["margin"],
                         "sharp": sharp["name"],
                         "sharp_margin": sharp["margin"], "ev": p * best - 1.0})
    rows.sort(key=lambda r: -r["prob"])
    return rows


# ------------------------------------------------------------------ transport
def get(url, params, timeout=20):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": "feeds/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()), dict(r.headers)


# ------------------------------------------------------------------ selftest
FIX_ODDSPAPI = [{
  "fixtureId": "id1000001764618978", "participant1Id": 3, "participant2Id": 35,
  "tournamentId": 17, "hasOdds": True,
  "startTime": "2025-12-08T20:00:00.000Z", "updatedAt": "2025-12-02T08:01:48.812Z",
  "bookmakerOdds": {
    "pinnacle": {
      "bookmakerIsActive": True,
      "changedAt": "2025-12-07T22:50:48Z",
      "markets": {
        "101": {
          "outcomes": {
            "101": {"players": {"0": {"active": True, "bookmakerOutcomeId": "home",
                                      "changedAt": "2025-12-07T22:50:48Z",
                                      "limit": 5000, "price": 5.01}}},
            "102": {"players": {"0": {"active": True, "bookmakerOutcomeId": "away",
                                      "changedAt": "2025-12-07T22:50:48Z",
                                      "limit": 3000, "price": 1.25}}},
            "103": {"players": {"0": {"active": True, "bookmakerOutcomeId": "draw",
                                      "changedAt": "2025-12-07T21:10:00Z",
                                      "limit": 2000, "price": 6.40}}},
          }
        }
      }
    },
    "bookm": {
      "bookmakerIsActive": True,
      "changedAt": "2025-12-07T23:40:00Z",
      "markets": {
        "101": {
          "outcomes": {
            "201": {"players": {"0": {"active": True, "bookmakerOutcomeId": "home",
                                      "changedAt": "2025-12-07T23:40:00Z",
                                      "limit": 4000, "price": 4.80}}},
            "202": {"players": {"0": {"active": True, "bookmakerOutcomeId": "away",
                                      "changedAt": "2025-12-07T23:40:00Z",
                                      "limit": 2500, "price": 1.29}}},
            "203": {"players": {"0": {"active": True, "bookmakerOutcomeId": "draw",
                                      "changedAt": "2025-12-07T23:40:00Z",
                                      "limit": 1500, "price": 6.90}}},
          }
        }
      }
    }
  }
}]


FIX_THEODDS = [{"id": "fb3772", "sport_key": "soccer_epl",
  "commence_time": "2026-10-17T14:00:00Z", "home_team": "Manchester City", "away_team": "Brighton",
  "bookmakers": [
    {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-10-17T13:40:00Z",
     "markets": [{"key": "h2h", "outcomes": [
        {"name": "Manchester City", "price": 1.22},
        {"name": "Brighton", "price": 12.0}, {"name": "Draw", "price": 6.4}]}]},
    {"key": "bookm", "title": "BookM", "last_update": "2026-10-17T11:10:00Z",
     "markets": [{"key": "h2h", "outcomes": [
        {"name": "Manchester City", "price": 1.18},
        {"name": "Brighton", "price": 13.0}, {"name": "Draw", "price": 6.6}]}]}]}]


def selftest():
    for nom, fn, fix in (("theoddsapi", norm_theodds, FIX_THEODDS),
                         ("oddspapi", norm_oddspapi, FIX_ODDSPAPI)):
        ev = fn(fix)
        rows = modele_commun(ev)
        print(f"\n--- {nom} : {len(ev)} evenement(s) -> {len(rows)} ligne(s)")
        for e in ev:
            for b in e["books"]:
                lim = f" limite={b.get('limits')}" if b.get("limits") else ""
                print(f"    {b['name']:<12} marge {b['margin']:>6.2%} "
                      f"probs " + " ".join(f"{k}={v:.3f}" for k, v in b["probs"].items()) + lim)
        if not rows:
            marges = [b["margin"] for e in ev for b in e["books"]]
            print(f"    -> 0 ligne : tous les books ont une marge >= 8 % "
                  f"(max {max(marges):.1%}) — le filtre d'exploitabilite les ecarte. "
                  f"Normal sur ce payload documente, atypique en production.")
        for r in rows:
            lim = f" limite={r['limit']}" if r["limit"] else ""
            print(f"    -> {r['sel']:<16} chance {r['prob']:>6.1%} cote {r['price']:.2f} "
                  f"chez {r['book']} EV {r['ev']:+.2%}{lim}")
        assert all(abs(sum(b["probs"].values()) - 1.0) < 1e-9 for e in ev for b in e["books"]), \
            "devigorisation invalide"
    print("\n[a verifier] somme des probas devigorisees = 1 pour chaque book : OK")


def show_budget():
    print(f"{'Configuration':<26} {'cout/appel':>10} {'par passe':>10} {'passes/mois':>12} {'/jour':>7}")
    print("-" * 70)
    for nom, c, passe, passes, par_jour in budget():
        print(f"{nom:<26} {c:>10} {passe:>10} {passes:>12} {par_jour:>6.1f}")
    print("\nThe Odds API : 1 appel = 1 ligue (endpoint /v4/sports/{sport}/odds).")
    print("OddsPapi     : 1 requete = TOUT le board (tournamentIds=17,8,... en une seule fois).")
    print("-> a perimetre egal, OddsPapi offre ~8x plus de passes sur le tier gratuit.")


def probe():
    print("SONDE DES SOURCES — les cles absentes sont ignorees\n")
    any_key = False
    if KEYS["theoddsapi"]:
        any_key = True
        try:
            data, hdr = get("https://api.the-odds-api.com/v4/sports/",
                            {"apiKey": KEYS["theoddsapi"]})
            foot = [s["key"] for s in data if "soccer" in s["key"]]
            print(f"[theoddsapi] /sports (gratuit) : {len(data)} sports, {len(foot)} championnats")
            for s in foot:
                print(f"    {s}")
            print(f"    quota restant : {hdr.get('x-requests-remaining')} / "
                  f"utilise : {hdr.get('x-requests-used')}")
        except Exception as e:
            print(f"[theoddsapi] ECHEC : {e}")
    else:
        print("[theoddsapi] THEODDSAPI_KEY absente")
    if KEYS["oddspapi"]:
        any_key = True
        for path, params in (("/v4/sports", {}), ("/v4/bookmakers", {})):
            try:
                data, _ = get(f"https://api.oddspapi.io{path}", {**params, "apiKey": KEYS["oddspapi"]})
                n = len(data) if isinstance(data, list) else "?"
                print(f"[oddspapi] {path} : {n} entrees")
                if "bookmakers" in path and isinstance(data, list):
                    noms = [b.get("bookmakerName") or b.get("slug") or str(b) for b in data]
                    sharp = [b for b in noms if any(h in str(b).lower() for h in SHARP_HINTS)]
                    print(f"    books sharp detectes : {sharp[:15]}")
            except Exception as e:
                print(f"[oddspapi] {path} ECHEC : {e}")
    else:
        print("[oddspapi] ODDSPAPI_KEY absente")
    if KEYS["pinnapi"]:
        any_key = True
        try:
            data, _ = get("https://api.pinnapi.com/v1/sports", {"apiKey": KEYS["pinnapi"]})
            print(f"[pinnapi] /v1/sports : {len(data) if isinstance(data, list) else data}")
        except Exception as e:
            print(f"[pinnapi] ECHEC (endpoint a confirmer avec la doc de ton compte) : {e}")
    else:
        print("[pinnapi] PINNAPI_KEY absente")
    if not any_key:
        print("\nAucune cle dans l'environnement.")
        print("export THEODDSAPI_KEY=... ; export ODDSPAPI_KEY=... ; export PINNAPI_KEY=...")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    {"selftest": selftest, "budget": show_budget, "probe": probe}.get(cmd, selftest)()
