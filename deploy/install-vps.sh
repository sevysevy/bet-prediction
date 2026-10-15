#!/usr/bin/env bash
# Installation sur le VPS : clone, cles, regeneration periodique, service statique.
# Prerequis : git, python3 >= 3.11, caddy. Lance en root ou avec sudo.
set -euo pipefail

DEST=/srv/bet-prediction
REPO=${REPO:-https://github.com/sevysevy/bet-prediction.git}

for c in git python3 caddy; do
  command -v "$c" >/dev/null || { echo "manquant : $c"; exit 1; }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' \
  || { echo "python3 >= 3.11 requis"; exit 1; }

if [ -d "$DEST/.git" ]; then
  git -C "$DEST" pull --ff-only
else
  git clone "$REPO" "$DEST"
fi

if [ ! -f "$DEST/.env" ]; then
  cp "$DEST/.env.example" "$DEST/.env"
  chmod 600 "$DEST/.env"
  echo ">> Renseigner les cles dans $DEST/.env puis relancer."
  exit 0
fi

mkdir -p "$DEST/_site"
install -m 644 "$DEST/deploy/refresh.service" /etc/systemd/system/bet-prediction-refresh.service
install -m 644 "$DEST/deploy/refresh.timer"   /etc/systemd/system/bet-prediction-refresh.timer
install -m 644 "$DEST/deploy/Caddyfile"       /etc/caddy/Caddyfile

systemctl daemon-reload
systemctl enable --now bet-prediction-refresh.timer
systemctl restart caddy
systemctl start bet-prediction-refresh.service

echo ">> Page servie sur http://\$(hostname -I | awk '{print \$1}'):8080"
