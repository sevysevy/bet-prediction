#!/usr/bin/env python3
"""
serve.py — service autonome : regenere la page et la sert, sans root et sans dependance.

Aucun systemd, aucun caddy, aucun paquet a installer. Utile quand on n'a pas les droits
root sur le VPS, ou quand systemd n'est pas disponible (conteneur).

    python3 src/serve.py --port 8080 --every 3            # service permanent
    python3 src/serve.py --port 8080 --once               # genere puis sort
    python3 src/serve.py --port 8080 --every 3 --demo     # sans cle API

Les cles sont lues dans l'environnement ou dans .env a la racine du projet.
"""
from __future__ import annotations
import argparse, functools, http.server, os, socketserver, sys, threading, time, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import build_site                                              # noqa: E402


def charger_env(chemin=None):
    """Charge .env sans dependance externe (n'ecrase pas l'environnement)."""
    chemin = chemin or os.path.join(ROOT, ".env")
    if not os.path.exists(chemin):
        return 0
    n = 0
    for ligne in open(chemin, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, val = ligne.split("=", 1)
        cle, val = cle.strip(), val.strip().strip('"').strip("'")
        if cle and val and not os.environ.get(cle):
            os.environ[cle] = val
            n += 1
    return n


def generer(out, demo=False):
    """Reutilise le generateur du projet. Ne leve jamais : renvoie (ok, message)."""
    argv = sys.argv[:]
    try:
        sys.argv = ["build_site.py", "--out", out] + (["--demo"] if demo else [])
        build_site.main()
        return True, f"page regeneree a {datetime.datetime.now():%H:%M:%S}"
    except SystemExit:
        return True, "page regeneree"
    except Exception as exc:                                   # une panne ne doit pas tuer le service
        return False, f"echec de generation : {exc}"
    finally:
        sys.argv = argv


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write(f"{self.address_string()} - {fmt % a}\n")

    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


def boucle(out, minutes, demo):
    while True:
        time.sleep(minutes * 60)
        ok, msg = generer(out, demo)
        print(f"[refresh] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--every", type=float, default=3, help="heures entre deux regenerations")
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"))
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--once", action="store_true", help="generer puis quitter (pas de serveur)")
    a = ap.parse_args()

    n = charger_env()
    out_file = os.path.join(a.out, "index.html")
    os.makedirs(a.out, exist_ok=True)
    ok, msg = generer(out_file, a.demo)
    print(f"[init] {msg} ({n} cle(s) lue(s) depuis .env)", flush=True)
    if a.once:
        return
    if a.every > 0:
        threading.Thread(target=boucle, args=(out_file, a.every * 60, a.demo), daemon=True).start()
    handler = functools.partial(Handler, directory=a.out)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((a.host, a.port), handler) as srv:
        print(f"[serve] http://{a.host}:{a.port}/  (regeneration toutes les {a.every} h)", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
