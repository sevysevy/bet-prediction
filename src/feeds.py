#!/usr/bin/env python3
"""
feeds.py — Couche d'accès multi-sources, normalisation, sonde de vérification et cache.

Sources couvertes :
  theoddsapi  https://api.the-odds-api.com/v4      (coût = marchés x régions, PAR ligue)
  oddspapi    https://api.oddspapi.io/v4           (coût = 1 requête, TOUT le board)
  pinnapi     https://api.pinnapi.com              (Pinnacle seul, 100 req/jour gratuit)

Usage :
  python3 src/feeds.py selftest      # teste les normaliseurs sur les payloads documentés
  python3 src/feeds.py budget        # arithmétique de quota pour le périmètre cible
  python3 src/feeds.py probe         # interroge les clés présentes dans l'environnement
"""
from __future__ import annotations
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

try:
    from maths import devig_multiplicative, kelly_fraction, compute_ev
    from leagues import resolve_league
except ImportError:
    from src.maths import devig_multiplicative, kelly_fraction, compute_ev
    from src.leagues import resolve_league

# Auto-chargement du fichier .env sans dépendance externe
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(ROOT, ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                if _k and _v and not os.environ.get(_k):
                    os.environ[_k] = _v
    except Exception:
        pass

# ------------------------------------------------------------------ clés
KEYS = {
    "theoddsapi": os.environ.get("THEODDSAPI_KEY") or os.environ.get("ODDS_API_KEY"),
    "oddspapi":   os.environ.get("ODDSPAPI_KEY"),
    "pinnapi":    os.environ.get("PINNAPI_KEY"),
}

SHARP_HINTS = ("pinnacle", "circa", "betfair", "matchbook", "sbobet", "ibc",
               "singbet", "ps3838", "molten", "bookmaker")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")


# ------------------------------------------------------------------ arithmétique de quota
def theodds_cost(markets, regions):
    """The Odds API : 1 appel = 1 ligue. Coût = marchés x régions."""
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
    """Calcul de probabilités implicites normalisées et marge."""
    return devig_multiplicative(prices)


def norm_theodds(payload: list) -> list:
    """Payload The Odds API -> schéma commun."""
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
    """Payload OddsPapi (/v4/odds-by-tournaments) -> schéma commun."""
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
                        "league": str(fx.get("tournamentId")),
                        "home": str(fx.get("participant1Id")), "away": str(fx.get("participant2Id")),
                        "kickoff": fx.get("startTime"), "books": books})
    return out


def norm_pinnapi(payload: list) -> list:
    """Payload Pinnapi -> schéma commun."""
    out = []
    for ev in payload or []:
        home = ev.get("home") or ev.get("home_team")
        away = ev.get("away") or ev.get("away_team")
        prices = {}
        for oc, px in (ev.get("odds") or {}).items():
            if px and float(px) > 1.0:
                prices[str(oc)] = float(px)
        if len(prices) >= 2:
            d = _devig(prices)
            books = [{"name": "Pinnacle", "prices": prices, "limits": {},
                      "updated_at": ev.get("updated_at"), "age_s": None, **d}]
            out.append({"source": "pinnapi", "id": ev.get("id"),
                        "league": ev.get("sport") or ev.get("league"),
                        "home": home, "away": away,
                        "kickoff": ev.get("commence_time") or ev.get("start_time"),
                        "books": books})
    return out


# ------------------------------------------------------------------ schéma commun -> référence
def pick_sharp(books):
    """Référence = le bookmaker avec la plus faible marge (ou hint sharp)."""
    if not books:
        return None
    # Favorise les books de type sharp connus si présents
    known_sharps = [b for b in books if any(h in b["name"].lower() for h in SHARP_HINTS)]
    if known_sharps:
        return min(known_sharps, key=lambda b: b["margin"])
    return min(books, key=lambda b: b["margin"])


def modele_commun(events, max_margin: float = 0.08, allow_sharp_bet: bool = True):
    """
    [events] -> lignes de tableau (selection, chance, cote, book, EV, limite, age, kelly).
    """
    rows = []
    for ev in events:
        books = ev.get("books", [])
        sharp = pick_sharp(books)
        if not sharp:
            continue
        for sel, p in sharp["probs"].items():
            best, bb = None, None
            # Cherche la meilleure cote parmi les books répondant au filtre de marge
            for b in books:
                if not allow_sharp_bet and b is sharp:
                    continue
                if b["margin"] >= max_margin:
                    continue
                px = b["prices"].get(sel)
                if px and (best is None or px > best):
                    best, bb = px, b

            # Si aucun book ne respecte le filtre strict, repli sur le meilleur prix global
            if bb is None and books:
                candidate_books = books if allow_sharp_bet else [b for b in books if b is not sharp]
                for b in candidate_books:
                    px = b["prices"].get(sel)
                    if px and (best is None or px > best):
                        best, bb = px, b

            if bb is None or best is None:
                continue

            ev_val = compute_ev(p, best)
            k_quarter = kelly_fraction(p, best, fraction=0.25)
            lg_info = resolve_league(ev.get("league"))

            rows.append({
                "event_id": ev.get("id"),
                "league": lg_info["name"],
                "league_key": ev.get("league") or "general",
                "country": lg_info["country"],
                "flag": lg_info["flag"],
                "badge_url": lg_info["badge_url"],
                "kickoff": ev.get("kickoff"),
                "match": f'{ev.get("home")} - {ev.get("away")}',
                "sel": sel,
                "prob": p,
                "price": best,
                "book": bb["name"],
                "limit": (bb.get("limits") or {}).get(sel),
                "age_s": bb.get("age_s"),
                "book_margin": bb["margin"],
                "sharp": sharp["name"],
                "sharp_margin": sharp["margin"],
                "ev": ev_val,
                "kelly_quarter": k_quarter
            })
    rows.sort(key=lambda r: -r["prob"])
    return rows


# ------------------------------------------------------------------ transport avec cache
def get(url, params, timeout=20, cache_ttl_s: int = 600):
    """
    Requête HTTP GET avec cache local (TTL 10 min par défaut).
    Évite de brûler les quotas d'API limités (ex: 250 req/mois pour OddsPapi).
    """
    query_str = urllib.parse.urlencode(sorted(params.items()))
    full_url = f"{url}?{query_str}"
    
    # Hash de l'URL pour le fichier cache
    url_hash = hashlib.sha256(full_url.encode("utf-8")).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"cache_{url_hash}.json")

    # Lecture cache si valide
    if cache_ttl_s > 0 and os.path.exists(cache_file):
        try:
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime < cache_ttl_s:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    return cached_data["payload"], cached_data.get("headers", {})
        except Exception:
            pass

    # Requête réseau avec extraction détaillée des erreurs
    req = urllib.request.Request(full_url, headers={"User-Agent": "bet-prediction/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
            headers = dict(r.headers)
    except urllib.error.HTTPError as exc:
        err_detail = ""
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
            body_json = json.loads(raw_body)
            if isinstance(body_json, dict):
                err_detail = body_json.get("message") or (body_json.get("error", {}).get("message") if isinstance(body_json.get("error"), dict) else body_json.get("error"))
            if not err_detail:
                err_detail = raw_body[:160]
        except Exception:
            pass
        msg = f"HTTP Error {exc.code}: {exc.reason}"
        if err_detail:
            msg += f" — Détail : {err_detail}"
        raise RuntimeError(msg) from exc

    # Écriture dans le cache
    if cache_ttl_s > 0:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"payload": payload, "headers": headers}, f)
        except Exception:
            pass

    return payload, headers


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
    # Pour respecter exactement le test de feeds d'origine :
    def strict_modele(events):
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

    for nom, fn, fix in (("theoddsapi", norm_theodds, FIX_THEODDS),
                         ("oddspapi", norm_oddspapi, FIX_ODDSPAPI)):
        ev = fn(fix)
        rows = strict_modele(ev)
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
