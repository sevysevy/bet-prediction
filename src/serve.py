#!/usr/bin/env python3
"""
serve.py — Service autonome et API REST : sert l'application et expose les données.

Zéro dépendance externe : uniquement la bibliothèque standard Python.
Fonctionnalités :
- Serveur HTTP asynchrone (ThreadingTCPServer)
- Endpoints REST API :
    GET  /api/v1/selections     -> Liste des sélections avec probabilités fair, cotes, EV et Kelly
    GET  /api/v1/combos         -> Combinés multi-jambes optimisés
    GET  /api/v1/stats          -> Statistiques du journal (nombre de signaux, EV moyen, CLV)
    GET  /api/v1/journal        -> Derniers signaux enregistrés
    POST /api/v1/refresh        -> Déclenche un rafraîchissement immédiat
- Service des fichiers statiques (index.html, data.json)
- Rafraîchissement automatique en arrière-plan à intervalle configurable
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import socketserver
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import build_site                                              # noqa: E402
import journal                                                 # noqa: E402


def charger_env(chemin: Optional[str] = None) -> int:
    """Charge les variables .env sans écraser l'environnement existant."""
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


def generer(out_path: str, demo: bool = False, force: bool = False) -> tuple[bool, str]:
    """Exécute la régénération du site et des données."""
    argv = sys.argv[:]
    old_force = os.environ.get("FORCE_REFRESH")
    try:
        if force:
            os.environ["FORCE_REFRESH"] = "1"
        sys.argv = ["build_site.py", "--out", out_path] + (["--demo"] if demo else []) + (["--force"] if force else [])
        build_site.main()
        return True, f"Régénération réussie à {datetime.datetime.now():%H:%M:%S}"
    except SystemExit:
        return True, "Régénération réussie"
    except Exception as exc:
        return False, f"Échec de régénération : {exc}"
    finally:
        sys.argv = argv
        if old_force is not None:
            os.environ["FORCE_REFRESH"] = old_force
        elif "FORCE_REFRESH" in os.environ:
            del os.environ["FORCE_REFRESH"]


def _check_refresh_auth(headers, query_params) -> bool:
    """
    Vérifie l'autorisation d'actualisation manuelle via REFRESH_KEY (ou ADMIN_KEY).
    Si aucune clé n'est définie dans l'environnement, l'actualisation est libre.
    """
    expected_key = (os.environ.get("REFRESH_KEY") or os.environ.get("ADMIN_KEY") or os.environ.get("SECRET_KEY") or "").strip()
    if not expected_key:
        return True
    
    # Vérification URL (?key=... ou ?token=...)
    provided = query_params.get("key") or query_params.get("token") or ""
    if provided == expected_key:
        return True
        
    # Vérification Headers (X-Refresh-Key ou X-API-Key)
    for h_name in ("x-refresh-key", "x-api-key"):
        if headers.get(h_name, "").strip() == expected_key:
            return True
            
    # Vérification Authorization: Bearer <key>
    auth = headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[7:].strip() == expected_key:
        return True

    return False


class ModernAppHandler(SimpleHTTPRequestHandler):
    """Handler HTTP servant l'API REST et les fichiers statiques."""

    def __init__(self, *args, directory=None, out_dir=None, is_demo=False, **kwargs):
        self.out_dir = out_dir or os.path.join(ROOT, "_site")
        self.is_demo = is_demo
        super().__init__(*args, directory=self.out_dir, **kwargs)

    def _send_json(self, data: any, status_code: int = 200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Refresh-Key, Authorization")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Refresh-Key, Authorization")
        self.end_headers()

    def _handle_refresh(self, force: bool = True):
        parsed = urllib.parse.urlparse(self.path)
        q_params = dict(urllib.parse.parse_qsl(parsed.query))
        
        if not _check_refresh_auth(self.headers, q_params):
            self._send_json({
                "success": False,
                "error": "Accès refusé : clé de rafraîchissement non valide ou manquante (?key=... ou header X-Refresh-Key)"
            }, status_code=401)
            return

        out_file = os.path.join(self.out_dir, "index.html")
        ok, msg = generer(out_file, self.is_demo, force=force)
        self._send_json({
            "success": ok,
            "message": msg,
            "forced": force,
            "timestamp": datetime.datetime.now().isoformat()
        }, status_code=200 if ok else 500)

    def do_POST(self):
        if self.path.startswith("/api/v1/refresh"):
            self._handle_refresh(force=True)
        else:
            self._send_json({"error": "Endpoint non trouvé"}, status_code=404)

    def do_GET(self):
        # Endpoints API
        if self.path.startswith("/api/v1/"):
            if self.path.startswith("/api/v1/refresh"):
                self._handle_refresh(force=True)
                return

            data_file = os.path.join(self.out_dir, "data.json")
            cache = {}
            if os.path.exists(data_file):
                try:
                    with open(data_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    pass

            if self.path == "/api/v1/selections":
                self._send_json(cache.get("selections", []))
                return
            elif self.path == "/api/v1/combos":
                self._send_json(cache.get("combos", []))
                return
            elif self.path == "/api/v1/stats":
                st = journal.get_stats()
                self._send_json(st)
                return
            elif self.path == "/api/v1/journal":
                recent = journal.get_recent_recommendations(limit=50)
                self._send_json(recent)
                return
            elif self.path == "/api/v1/all":
                self._send_json(cache)
                return
            else:
                self._send_json({"error": "Route API inconnue"}, status_code=404)
                return

        # Fichiers statiques
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=120")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        # N'afficher que les requêtes importantes ou erreurs
        if not self.path.startswith("/api/v1/stats"):
            sys.stderr.write(f"[{datetime.datetime.now():%H:%M:%S}] {self.address_string()} - {fmt % args}\n")


def background_loop(out_file: str, minutes: float, demo: bool):
    """Boucle de rafraîchissement périodique."""
    while True:
        time.sleep(minutes * 60)
        ok, msg = generer(out_file, demo)
        print(f"[auto-refresh] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Serveur web et API REST bet-prediction")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)), help="Port d'écoute")
    ap.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute")
    ap.add_argument("--every", type=float, default=2, help="Intervalle de rafraîchissement en heures (défaut : 2h)")
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"), help="Répertoire du site")
    ap.add_argument("--demo", action="store_true", help="Mode données simulées")
    ap.add_argument("--once", action="store_true", help="Générer les fichiers et quitter")
    a = ap.parse_args()

    n = charger_env()
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "index.html")

    ok, msg = generer(out_file, a.demo)
    print(f"[init] {msg} ({n} clé(s) lue(s) dans .env)", flush=True)

    if a.once:
        return

    if a.every > 0:
        threading.Thread(target=background_loop, args=(out_file, a.every * 60, a.demo), daemon=True).start()

    def handler_factory(*args, **kwargs):
        return ModernAppHandler(*args, out_dir=out_dir, is_demo=a.demo, **kwargs)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((a.host, a.port), handler_factory) as srv:
        print(f"[serve] Serveur prêt : http://localhost:{a.port}/", flush=True)
        print(f"[serve] API REST : http://localhost:{a.port}/api/v1/selections", flush=True)
        print(f"[serve] Rafraîchissement automatique toutes les {a.every} heures", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nArrêt du serveur.")


if __name__ == "__main__":
    main()
