# Les plus probables

Page publique qui affiche, pour les matchs du jour, les sélections et les combinés **classés par
probabilité de passer** — et, à côté de chaque ligne, l'**espérance de gain (EV)**.

> Les « chances » affichées sont les probabilités du marché, marge du bookmaker retirée. **Ce ne sont
> pas des pronostics.** Aucune performance n'est garantie.

---

## Pourquoi deux chiffres au lieu d'un

La « chance de passer » et la rentabilité évoluent **en sens inverse** : plus les jambes d'un combiné
sont favorites, plus la probabilité de passer est élevée, et plus l'EV s'effondre, parce que la marge
du bookmaker se compose avec le nombre de jambes.

| Jambes | Chance de passer | Marge effective | EV (book à 6 %) |
|---|---|---|---|
| 1 | 90,0 % | 6,0 % | −5,7 % |
| 2 | 81,0 % | 11,6 % | −11,0 % |
| 3 | 72,9 % | 16,9 % | −16,0 % |
| 5 | 59,0 % | 26,6 % | −25,3 % |
| 8 | 43,0 % | 39,0 % | −37,3 % |

Une page qui n'afficherait que la chance de passer orienterait mécaniquement vers les paris les plus
perdants. La colonne EV est donc le cœur du produit, pas un ornement.

À l'inverse : si chaque jambe avait un **vrai** edge de +4 %, le combiné passerait à +4 % (1 jambe),
+12,5 % (3), +21,7 % (5). Les combinés n'amplifient pas *mal* — ils amplifient.

---

## Comment ça marche

Aucune donnée historique, aucun modèle entraîné. Les cotes **sont** les probabilités.

```
① collecte   cotes du jour auprès d'une source (plusieurs books)
② dévigorisation   p_fair = probabilité implicite normalisée   (jamais 1/cote brut : biaisé)
③ classement   simples triés par p_fair, avec cote, book, fraîcheur, mise max, EV
④ combinés   produit des p_fair, une seule jambe par match, cote prise chez UN SEUL book
⑤ rendu   page HTML statique
```

**Zéro dépendance externe** : uniquement la bibliothèque standard de Python 3.11+. Le build tourne en
quelques secondes et ne consomme quasiment rien — il tient sur un VPS à 4 Go sans difficulté.

### La référence « sharp »

Pour chaque événement, la référence est **le book à la marge la plus faible**, détecté
automatiquement — plutôt qu'une liste de noms codée en dur (l'API publique de Pinnacle a fermé en
juillet 2025). La marge de chaque book est affichée pour que le choix soit vérifiable.

---

## Sources de cotes

Les adaptateurs vivent dans `src/feeds.py`. La source est choisie selon les clés présentes.

| Source | Variable | Tier gratuit | Coût d'une passe |
|---|---|---|---|
| [OddsPapi](https://oddspapi.io) | `ODDSPAPI_KEY` | 250 requêtes/mois | **1** — tout le board en un appel |
| [The Odds API](https://the-odds-api.com) | `THEODDSAPI_KEY` | 500 crédits/mois | 8–24 — le coût est `marchés × régions` **par ligue** |
| [pinnapi](https://pinnapi.com) | `PINNAPI_KEY` | 100 requêtes/jour | Pinnacle seul |

**OddsPapi est la source recommandée** : une requête couvre tous les championnats, Pinnacle est inclus,
et elle expose en plus la **limite de mise** par issue, l'**ancienneté** de chaque cote, la **ligne de
clôture** (`/fixtures/odds/clv`) et les **résultats** (`/settlements`) — de quoi mesurer un edge réel
plus tard sans construire de machinerie de collecte.

Vérifier ce que tes clés donnent réellement :

```bash
export ODDSPAPI_KEY=...
python3 src/feeds.py probe      # championnats, books sharp détectés, quota restant
python3 src/feeds.py budget     # arithmétique de quota
python3 src/feeds.py selftest   # teste les normaliseurs hors ligne
```

---

## Lancer en local

```bash
python3 src/build_site.py --demo --out site/index.html   # sans clé API
export ODDSPAPI_KEY=...                                  # ou THEODDSAPI_KEY
python3 src/build_site.py --out site/index.html
python3 -m http.server -d site 8000                      # http://localhost:8000
```

---

## Déploiement

Dépôt **privé** — et GitHub Pages exige un compte **GitHub Pro** sur un dépôt privé. Le déploiement
de référence est donc le **VPS**.

### VPS (recommandé)

```bash
sudo REPO=https://github.com/sevysevy/bet-prediction.git bash deploy/install-vps.sh
```

Le script clone le dépôt dans `/srv/bet-prediction`, installe la paire `systemd`
(`bet-prediction-refresh.service` + `.timer`, régénération toutes les 3 h), pose le `Caddyfile` et
démarre le service statique sur le port 8080.

Au premier lancement il crée `/srv/bet-prediction/.env` en `chmod 600` puis s'arrête : **renseigne les
clés, relance**. Les clés ne quittent jamais le VPS.

Prérequis : `git`, `python3 >= 3.11`, `caddy`. Aucun paquet Python à installer.

Le dépôt étant privé, le VPS a besoin d'un moyen d'authentification pour `git pull` : clé de
déploiement en lecture (Settings → Deploy keys) ou jeton dans `~/.git-credentials`.

### GitHub Pages (si tu passes en GitHub Pro)

Le workflow Pages a été retiré pour ne pas laisser un job en échec. Si tu passes en Pro, il suffit de
rajouter un job `deploy` qui publie `_site/` avec `actions/upload-pages-artifact` +
`actions/deploy-pages`, et de mettre Pages en source « GitHub Actions ». `.github/workflows/ci.yml`
continue de valider le code à chaque push.

## Structure

```
src/feeds.py         adaptateurs multi-sources, dévigorisation, sonde, budget de quota
src/build_site.py    générateur de la page
site/index.html      sortie générée (ignorée par git, servie localement)
docs/                décomposition, architecture, spécification du MVP, registre de preuve
deploy/              Caddyfile + systemd (option VPS)
```

`.github/workflows/ci.yml` valide le code à chaque push (compilation, tests hors ligne, build de
démonstration).

`docs/` contient le travail de conception : `docs/01-architecture.md` (architecture cible complète),
`docs/02-mvp.md` (spécification de cette page), et `docs/research/evidence-register.md` (les sources
scientifiques et techniques qui fondent les choix).

---

## Ce que ce projet n'est pas

- **Pas un service de pronostics.** Les probabilités viennent des cotes publiées par les opérateurs.
- **Pas une promesse de rendement.** L'EV affichée est le plus souvent négative : c'est la marge du
  bookmaker, et c'est la vérité du marché.
- **Pas un outil de placement de paris.** Aucune API publique ne permet de placer un pari ; le
  placement reste manuel.

Le pari comporte un risque de perte et un risque de dépendance. Jouez uniquement de l'argent dont vous
n'avez pas besoin.

## Licence

Dépôt privé — **tous droits réservés**, voir `LICENSE`. À passer en MIT si le projet est un jour
ouvert.
