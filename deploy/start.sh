#!/usr/bin/env bash
# Lancement SANS root : ni systemd, ni caddy, ni paquet a installer.
# Prerequis : git, python3 >= 3.11. Usage : ./deploy/start.sh [port]
set -euo pipefail

PORT=${1:-8080}
RACINE=$(cd "$(dirname "$0")/.." && pwd)
PIDFILE="$RACINE/_site/serve.pid"
LOG="$RACINE/_site/serve.log"

mkdir -p "$RACINE/_site"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo ">> deja en cours (pid $(cat "$PIDFILE"))"; exit 0
fi

if [ ! -f "$RACINE/.env" ]; then
  cp "$RACINE/.env.example" "$RACINE/.env"
  chmod 600 "$RACINE/.env"
  echo ">> $RACINE/.env cree. Renseigne les cles puis relance."; exit 0
fi

nohup python3 "$RACINE/src/serve.py" --port "$PORT" --every 3 \
  >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 2

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo ">> service demarre (pid $(cat "$PIDFILE")) sur le port $PORT"
  echo ">> journal : $LOG"
  tail -n 3 "$LOG"
else
  echo ">> echec du demarrage — voir $LOG"; tail -n 10 "$LOG"; exit 1
fi
