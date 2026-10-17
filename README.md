# Les plus probables (Plateforme de Prédiction & Analyse de Marché)

Plateforme moderne et rigoureuse qui affiche, pour les matchs du jour, les sélections et les combinés **classés par probabilité de passer** — accompagnés de l'**espérance de gain (EV)**, du **critère de Kelly fractionnaire** et du **suivi CLV (Closing Line Value)**.

> Les « chances » affichées sont les probabilités du marché, marge du bookmaker retirée (dévigorisation sharp). **Ce ne sont pas des pronostics arbitraires.** Aucune performance n'est garantie.

---

## ⚡ Nouveautés de la version modernisée

- 📱 **Interface Moderne & Réactive (SPA)** : Design dark/glassmorphism épuré, navigation par onglets, responsive mobile.
- 🎯 **Onglet « Plus Probables »** : Tri par probabilité implicite fair dévigorisée.
- 💎 **Onglet « Value Bets (EV > 0) »** : Détection des cotes battant le marché sharp, avec dimensionnement de mise Kelly.
- 🔗 **Onglet « Combinés Optimisés »** : Combinés 2 à 4 jambes construits sur des matches indépendants avec cotes réelles chez un seul bookmaker.
- 🎟️ **Simulateur de Coupon Interactif & Kelly** : Tiroir interactif permettant de sélectionner n'importe quel match, de calculer la probabilité composée, la cote cumulée, l'érosion de marge, et la mise exacte en euros selon le **Quarter-Kelly** ($f^*/4$) adapté à votre bankroll.
- 📊 **Journal SQLite Append-Only & CLV** : Historisation automatique des signaux pour mesurer le **Closing Line Value (CLV)** et la calibration (RPS / Brier).
- 🚀 **API REST intégrée** : Endpoints JSON (`/api/v1/selections`, `/api/v1/combos`, `/api/v1/stats`, `/api/v1/journal`, `/api/v1/refresh`).
- 🛡️ **Cache local intelligent** : TTL de 10 min pour préserver les quotas d'API gratuits.
- 🧪 **Suite de tests automatisée** : Validation unitaire mathématique et logique (`tests/test_all.py`).
- ⚡ **Zéro dépendance npm ou externe** : 100% autonome sur la bibliothèque standard de Python 3.11+.

---

## Pourquoi deux chiffres au lieu d'un

La « chance de passer » et la rentabilité évoluent **en sens inverse** : plus les jambes d'un combiné sont favorites, plus la probabilité de passer est élevée, et plus l'EV s'effondre, parce que la marge du bookmaker se compose avec le nombre de jambes.

| Jambes | Chance de passer | Marge effective | EV (book à 6 %) |
|---|---|---|---|
| 1 | 90,0 % | 6,0 % | −5,7 % |
| 2 | 81,0 % | 11,6 % | −11,0 % |
| 3 | 72,9 % | 16,9 % | −16,0 % |
| 5 | 59,0 % | 26,6 % | −25,3 % |
| 8 | 43,0 % | 39,0 % | −37,3 % |

Une page qui n'afficherait que la chance de passer orienterait mécaniquement vers les paris les plus perdants. La colonne EV est donc le cœur du produit, pas un ornement.

À l'inverse : si chaque jambe avait un **vrai** edge de +4 %, le combiné passerait à +4 % (1 jambe), +12,5 % (3), +21,7 % (5). Les combinés n'amplifient pas *mal* — ils amplifient.

---

## Comment ça marche

Aucune donnée historique requise, aucun modèle complexe en boîte noire : **les cotes sont les probabilités**.

```
① collecte         cotes du jour auprès d'une source (TheOddsAPI, OddsPapi, Pinnapi) avec cache TTL
② dévigorisation   p_fair = probabilité implicite normalisée (ou modèle des puissances)
③ classement       simples triés par p_fair, avec cote, book, fraîcheur, EV et Kelly
④ combinés         produit des p_fair, une seule jambe par match, cote chez UN SEUL book
⑤ journalisation   enregistrement dans data/journal.db (SQLite) pour suivi CLV
⑥ rendu & API      page web moderne SPA et API REST JSON
```

---

## Lancer en local

```bash
# 1. Génération statique (mode démo sans clé)
python src/build_site.py --demo --out site/index.html

# 2. Lancement du serveur complet (avec UI moderne + API REST)
python src/serve.py --demo --port 8080

# Ouvrir dans le navigateur :
# Interface Web : http://localhost:8080/
# API REST      : http://localhost:8080/api/v1/selections
```

### Avec clés API en direct :

```bash
export ODDSPAPI_KEY=...       # ou THEODDSAPI_KEY=...
python src/build_site.py --out site/index.html
python src/serve.py --port 8080 --every 3
```

---

## API REST intégrée

Le serveur autonome `src/serve.py` expose les routes suivantes :

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Interface web monopage (SPA réactive) |
| `GET` | `/api/v1/selections` | Liste des sélections du jour (probabilités, cotes, EV, Kelly) |
| `GET` | `/api/v1/combos` | Liste des combinés optimisés |
| `GET` | `/api/v1/stats` | Métriques globales du journal SQLite (signaux, EV moyen, CLV) |
| `GET` | `/api/v1/journal` | Derniers signaux enregistrés |
| `GET` | `/api/v1/all` | Payload JSON complet |
| `POST`| `/api/v1/refresh` | Déclenche un rafraîchissement immédiat des cotes |

---

## Tests automatisés

Pour exécuter la suite de tests unitaires :

```bash
python -m unittest discover tests
python src/feeds.py selftest
```

---

## Structure du projet

```
src/
├── maths.py         Moteur mathématique (dévigorisation, EV, critère de Kelly fractionnaire, combinés)
├── journal.py       Journal SQLite append-only (enregistrement des signaux et calcul du CLV)
├── feeds.py         Adaptateurs multi-sources (The Odds API, OddsPapi, Pinnapi), cache local et sonde
├── build_site.py    Générateur de la SPA moderne et exportateur JSON
└── serve.py         Serveur autonome HTTP + API REST sans dépendance
tests/
└── test_all.py      Suite complète de tests unitaires
data/                Base SQLite locale (data/journal.db - ignorée par Git)
deploy/              Scripts de déploiement VPS (systemd, start.sh, Caddyfile)
docs/                Architecture scientifique, registre de preuve et décomposition
```

---

## Déploiement VPS

### Avec root & systemd :

```bash
sudo REPO=https://github.com/sevysevy/bet-prediction.git bash deploy/install-vps.sh
```

### Sans root (autonome) :

```bash
./deploy/start.sh 8080
./deploy/stop.sh
```

---

## Ce que ce projet n'est pas

- **Pas un service de pronostics.** Les probabilités viennent des cotes publiées par les opérateurs.
- **Pas une promesse de rendement.** L'EV affichée est le plus souvent négative : c'est la marge du bookmaker, et c'est la vérité du marché.
- **Pas un outil de placement de paris.** Le placement reste manuel.

Les paris d'argent comportent un risque de perte financière et d'addiction. Ne misez jamais d'argent dont vous avez besoin.
