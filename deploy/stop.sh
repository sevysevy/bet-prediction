#!/usr/bin/env bash
set -euo pipefail
RACINE=$(cd "$(dirname "$0")/.." && pwd)
PIDFILE="$RACINE/_site/serve.pid"
[ -f "$PIDFILE" ] || { echo ">> pas de pidfile"; exit 0; }
if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" && echo ">> service arrete"
else
  echo ">> processus deja absent"
fi
rm -f "$PIDFILE"
