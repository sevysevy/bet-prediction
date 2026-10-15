# Architecture — Plateforme de détection de valeur (architecture A « marché »)

Version 1 · 2026-10-15 · Contraintes d'exécution : **VPS 4 Go RAM, aucun GPU, ~100 Go de disque**

---

## 0. Les cinq principes qui dictent tout le reste

| # | Principe | Conséquence architecturale |
|---|---|---|
| P1 | **Le marché est la source, pas l'adversaire** — la cote sharp dévigorisée *est* la probabilité de référence | Aucun modèle en production. F3 devient optionnel, hors chemin critique |
| P2 | **La fraîcheur est une donnée de premier ordre** | Chaque cote porte son horodatage ; une cote périmée est rejetée, pas corrigée |
| P3 | **La collecte est plus critique que le calcul** | Le collecteur est le seul composant qui doit tourner 24/7 sans interruption |
| P4 | **Rien n'est recommandé sans cote, book, mise et heure limite** | Le moteur ne produit jamais un « pronostic », seulement une action exécutable |
| P5 | **La preuve vient du CLV mesuré sur les prix OBSERVÉS — et l'étiquetage dit exactement ce que ça vaut** | Aucune cote déclarée par un utilisateur n'entre dans la mesure. Le journal est append-only |

---

## 1. Vue d'ensemble

```
   ┌──────────────────────── SERVICES EXTERNES ─────────────────────────┐
   │  Agrégateur de cotes  ·  Feed compositions/blessures  ·  Push      │
   └───────┬──────────────────────────┬───────────────────────┬─────────┘
           │ region=eu (règle)        │ region=fr + books     │
           │ region=us (Circa)        │ de placement          │
           ▼                          ▼                       │
   ┌───────────────────────────────────────────┐              │
   │ ① COLLECTEUR (démon permanent, 150 Mo)    │              │
   │   poll 140 s · stockage des DELTAS seuls  │              │
   │   horodatage systématique                 │              │
   └───────────────┬───────────────────────────┘              │
                   ▼                                          │
   ┌───────────────────────────────────────────┐              │
   │ ② NORMALISEUR                              │              │
   │   cotes US/décimal → proba implicite       │              │
   │   mapping équipes + mapping marchés        │              │
   │   dévigorisation (probas normalisées)      │              │
   └───────────────┬───────────────────────────┘              │
                   ▼                                          │
   ┌───────────────────────────────────────────┐              │
   │ ③ MOTEUR DE VALEUR                         │              │
   │   p_fair ← référence sharp dévigorisée     │              │
   │   EV = p_fair × cote_offerte − 1           │              │
   │   filtres d'exécution + seuil              │              │
   │   mise = Kelly quart, plafonnée            │              │
   └───────────────┬───────────────────────────┘              │
                   ▼                                          │
   ┌───────────────────────────────────────────┐              │
   │ ④ DIFFUSEUR  →  carte de pari (push)  ─────┼──────────────┘
   │   fenêtre de validité · bouton « je l'ai pris »
   └───────────────┬───────────────────────────┘
                   ▼
   ┌───────────────────────────────────────────┐
   │ ⑤ JOURNAL DES PARIS  (SQLite, append-only) │
   └───────────────┬───────────────────────────┘
                   ▼
   ┌───────────────────────────────────────────┐
   │ ⑥ MESURE : CLV · calibration · rapport     │
   │   critère d'arrêt                          │
   └───────────────┬───────────────────────────┘
                   ▼
   ┌───────────────────────────────────────────┐
   │ ⑦ REGISTRE PUBLIC (preuve vérifiée seule)  │
   └───────────────────────────────────────────┘

   ⟂ composant transverse :
   ┌───────────────────────────────────────────┐
   │ ⑧ CAPTURE DE CLÔTURE — poll renforcé de la │
   │   référence sharp jusqu'au coup d'envoi,   │
   │   puis FIGE la dernière cote vue           │
   └───────────────────────────────────────────┘
```

---

## 2. Les huit composants

| # | Composant | Rôle | Cadence | Mémoire | Techno |
|---|---|---|---|---|---|
| ① | **Collecteur** | Interroge l'agrégateur (regions `eu`, `fr`, `us`), écrit un delta à chaque changement de cote, horodate tout | boucle continue, poll 140 s | 150 Mo | Python + `requests`/`httpx`, retry + backoff |
| ② | **Normaliseur** | Convertit US↔décimal, résout les noms d'équipes et de marchés, dévigorise par probabilités normalisées | à chaque lot | 80 Mo | Python, `rapidfuzz` pour le mapping |
| ③ | **Moteur de valeur** | Calcule `p_fair`, l'EV, applique les filtres et le seuil, calcule la mise | à chaque lot | 60 Mo | Python, DuckDB pour les lectures |
| ④ | **Diffuseur** | Envoie la carte de pari, gère la fenêtre de validité. **Aucune saisie utilisateur n'entre dans la mesure** | immédiat | 40 Mo | Bot push (Telegram) |
| ⑤ | **Journal des recommandations** | Table append-only ; une ligne par recommandation, portant le **prix observé** et son horodatage source | à la décision | 20 Mo | SQLite |
| ⑥ | **Mesure** | Calcule le CLV par pari, la moyenne glissante, la calibration, le rapport hebdomadaire | quotidien | 300 Mo | Python + DuckDB |
| ⑦ | **Registre public** | Expose le track record, alimenté **uniquement** par le compte propriétaire | quotidien | 200 Mo | générateur statique |
| ⑧ | **Capture de clôture** | Poll resserré de la référence sharp dans les 30 dernières minutes, puis fige | continu, ciblé | 40 Mo | même boucle que ①, priorité haute |
| | **Total permanent** | | | **~890 Mo** | sur 4 Go → **~2,7 Go de marge** |

---

## 3. Chronologie d'un signal (contre la fenêtre mesurée de 30 s à 5 min)

| t | Événement | Composant |
|---|---|---|
| t−140 s | Poll : la référence sharp bouge sur la sélection A | ① |
| t−140 s + 5 s | Détection du mouvement, écriture du delta | ① |
| | `p_fair` recalculée (dévigorisation) | ② |
| | `EV = p_fair × cote_BookM − 1` → **+3,1 %** ≥ seuil | ③ |
| | Filtres : fraîcheur sharp 4 min ✅ · fraîcheur offre 9 min ✅ · marge BookM 4,7 % ✅ · cote 2,05 ∈ [1,4 ; 6,0] ✅ · 4 h avant le KO ✅ | ③ |
| | Mise = Kelly quart → **0,6 % du capital** | ③ |
| t−130 s | Carte poussée : cote, book, mise, heure limite | ④ |
| t−60 s | L'utilisateur lit et ouvre le book | humain |
| **t = 0** | Recommandation figée avec le **prix observé** et l'horodatage du feed. Aucune saisie utilisateur | ⑤ |
| **t + 140 s** | Poll suivant : la cote est-elle toujours là ? → alimente le **taux de signal perdu** | ① → ⑥ |
| +30 min | Capture de clôture : la référence sharp est figée | ⑧ |
| J+1 | CLV calculé : `p_clôture_fair − p_prise` | ⑥ |

---

## 3 bis. Hiérarchie des preuves — et ce qu'on décide

**Décision : aucune cote n'est déclarée par un utilisateur.** Un prix déclaré est invérifiable par
construction : rien n'empêche de déclarer une cote qu'on n'a jamais obtenue, et rien ne permet de le
détecter. Cette voie est écartée.

Trois niveaux restent possibles, par ordre de force probante :

| Niveau | Source du prix | Ce que ça prouve | Coût |
|---|---|---|---|
| **1 — Exécuté** | Compte propriétaire, argent réel, relevés de retrait | Que la stratégie est rentable **en pratique**, limitations de comptes incluses | Élevé. Limitation/fermeture de compte[20][21] |
| **2 — Observé** | **Prix du feed, horodaté par le feed** au moment de la recommandation | La qualité **éditoriale** des recommandations, dans des conditions de marché observées | Faible. **Retenu pour la v1** |
| **3 — Déclaré** | Saisie utilisateur | Rien | Nul. **Écarté** |

### Ce que le niveau 2 ne prouve PAS — et qui doit être écrit sur le produit

1. **Prix observé ≠ prix exécutable.** Le feed peut afficher une cote non disponible pour un utilisateur
   donné : limite de mise, restriction de compte, blocage géographique, ou simple retard d'affichage du
   book par rapport à l'agrégateur.
2. **La cote peut disparaître** entre la recommandation et la prise. C'est le *taux de signal perdu*,
   mesuré automatiquement par le poll suivant (+140 s), et publié.
3. **Il n'y a pas de preuve de retrait.** Aucun argent n'a été engagé, donc aucun relevé ne corrobore.

**Conséquence d'étiquetage, obligatoire :** le registre public affiche
« *performance théorique, sur prix observés, non exécutée* ». Jamais « nos parieurs gagnent X ».
Présenter une performance non exécutée comme un résultat est précisément le reproche que la littérature
adresse aux opérateurs qui « ne fournissent pas ce qu'ils annoncent »[4] — le retour de bâton serait
d'autant plus violent que le produit est vendu sur cette promesse.

**Contrôle croisé, quasi gratuit :** le collecteur relit déjà la cote toutes les 140 s. Le poll suivant la
recommandation sert donc **de vérification automatique** de disponibilité. S'y ajoute un échantillon
humain de 10 recommandations par semaine (ouvrir réellement le book), seul contrôle du point 1.

---

## 4. Modèle de données (SQLite)

```sql
-- Cotes : on n'écrit QUE sur changement (deltas)
CREATE TABLE odds_delta (
  ts            TEXT NOT NULL,      -- ISO 8601 UTC, horodatage de l'observation
  event_id      TEXT NOT NULL,
  book          TEXT NOT NULL,
  region        TEXT NOT NULL,      -- eu | fr | us
  market        TEXT NOT NULL,
  selection     TEXT NOT NULL,
  price_decimal REAL NOT NULL,
  fetched_at    TEXT NOT NULL,      -- horodatage du fetch
  updated_at    TEXT NOT NULL,      -- horodatage déclaré par le book  <-- LE CHAMP CRITIQUE
  PRIMARY KEY (ts, event_id, book, market, selection)
);

CREATE TABLE event (            -- mapping inter-books
  event_id TEXT PRIMARY KEY, kickoff_utc TEXT, league TEXT,
  home_canonical TEXT, away_canonical TEXT
);

CREATE TABLE closing_line (     -- figé par ⑧, jamais réécrit
  event_id TEXT, book TEXT, market TEXT, selection TEXT,
  price_decimal REAL, captured_at TEXT, minutes_before_ko REAL,
  PRIMARY KEY (event_id, book, market, selection)
);

CREATE TABLE recommendation (   -- append-only, AUCUNE saisie utilisateur
  rec_id TEXT PRIMARY KEY, decided_at TEXT,
  event_id TEXT, book TEXT, market TEXT, selection TEXT,
  -- le prix tel qu'OBSERVÉ par le feed, avec son propre horodatage :
  observed_price REAL, observed_updated_at TEXT, feed_region TEXT,
  p_fair_at_decision REAL, ev_detected REAL, ev_realisable_est REAL,
  stake_frac REAL, ruleset_version TEXT,
  -- remplis par ⑥ :
  close_price REAL, close_fair_prob REAL, clv REAL,
  signal_lost INTEGER, minutes_available REAL,
  settled INTEGER DEFAULT 0, won INTEGER, payout REAL
);

CREATE TABLE filtered_out (     -- ce qu'on a REJETÉ et pourquoi : traçabilité
  ts TEXT, event_id TEXT, book TEXT, selection TEXT,
  ev_detected REAL, reason TEXT  -- stale_offer | stale_sharp | margin | odds_range | no_sharp_ref | time_to_ko
);
```

**Pourquoi `filtered_out` existe** : sans journal des rejets, tu ne peux pas savoir si ton seuil est trop strict ou si la source est vide. C'est aussi ce qui protège du p-hacking — tu ne peux pas réajuster le seuil sans voir combien de signaux tu as jetés.

---

## 5. Ordonnancement

| Job | Fréquence | Durée | Priorité |
|---|---|---|---|
| Collecte des cotes | continue, 140 s | < 10 s | haute |
| Capture de clôture | continue, ciblée sur les KO < 30 min | < 5 s | **maximale** |
| Moteur + diffuseur | après chaque lot | < 10 s | haute |
| Remplissage du CLV | quotidien, 03:00 | < 2 min | basse |
| Rapport de mesure | hebdomadaire | ~10 min | basse |
| Backtest walk-forward | **manuel**, hors production | heures | jamais en parallèle |

**Règle absolue** : aucun job lourd pendant la collecte. Le backtest se lance à la demande, jamais sur le chemin critique.

---

## 6. Règles de décision (à geler)

| Règle | Valeur | Justification |
|---|---|---|
| Référence sharp | région `eu` (Pinnacle) ou `us` (Circa) | Circa : marge 1,98 % observée, la plus basse du panel |
| Dévigorisation | probabilités normalisées | l'inverse des cotes est biaisé[3] |
| Seuil de détection | **EV ≥ 3,0 %** | l'edge réalisable ≈ 0,345 × l'edge détecté[32] |
| Fraîcheur de la référence | < 5 min | sinon le référentiel lui-même est faux |
| Fraîcheur de la cote offerte | **< 15 min** | ton payload a montré jusqu'à 17,2 h |
| Marge du book de placement | < 6 % | au-delà, l'écart est de la marge, pas de la valeur |
| Plage de cotes acceptées | 1,40 – 6,00 | ~10 % de marge sur une cote de 10,00[31] |
| Temps avant le coup d'envoi | > 45 min | en dessous, les limites chutent et les lignes se resserrent |
| Mise | Kelly quart, plafonnée à 1 % du capital, exposition totale ≤ 5 % | Kelly plein augmente le risque de ruine sous mauvaise calibration[8] |
| Formation des combinés | **interdite** | croissance divisée par 6,3 à 5 jambes, 20 % de risque de 50 pertes consécutives |
| Taux de signal perdu | mesuré automatiquement, publié | une cote peut disparaître avant d'être prise ; s'il est élevé, l'edge est théorique |
| Vérification humaine | 10 recommandations/semaine tirées au hasard, cote du book ouverte manuellement et comparée au feed | seul contrôle que le prix du feed est bien un prix disponible |
| Critère d'arrêt | CLV < +1 % après 800 paris → arrêt | seuil de décision de F5 |

---

## 7. Stack

| Couche | Choix | Motif (contrainte 4 Go) |
|---|---|---|
| Langage | Python 3.12 | écosystème |
| HTTP | `httpx` + retry/backoff | robustesse réseau |
| Stockage chaud | **SQLite** en WAL | pas de serveur, ~20 Mo |
| Stockage froid | **Parquet + zstd** | 5× plus petit que CSV ; rétention 90 j |
| Requêtes analytiques | **DuckDB** | travaille hors mémoire — indispensable à 4 Go |
| Ordonnancement | `systemd` timers ou `cron` | pas de dépendance lourde |
| Push | Telegram Bot API | gratuit, instantané, historique côté serveur |
| Analyse LLM (F6) | **API distante** | pas de GPU ; un LLM local cannibalise le cache disque |
| Swap | 4 Go | évite l'OOM-kill du collecteur |
| Supervision | `logrotate` + alerte si le collecteur n'a rien écrit depuis 10 min | la panne silencieuse est le risque n°1 |

---

## 8. Invariants à tester (avant toute recommandation réelle)

1. **Aucune ligne de `recommendation` n'est jamais `UPDATE`-ée** sauf pour remplir `close_price`, `clv`, `signal_lost`, `settled`, `won`. Aucun de ces champs ne peut provenir d'une saisie utilisateur.
2. Toute recommandation porte un `ev_detected ≥ seuil` et un `reason` vérifiable.
3. Le mapping d'équipes est validé : un même match est identifié de façon identique chez tous les books. **Sans ça, la comparaison est du bruit.**
4. Une cote dont `updated_at` dépasse le seuil n'entre jamais dans un calcul de valeur.
5. `closing_line` est écrit une seule fois, au plus tard possible, et jamais réécrit.
6. Le rapport de mesure est reproductible depuis la base seule.
7. Le collecteur écrit quelque chose au moins toutes les 10 minutes, sinon alerte.

---

## 9. Ce qui n'est PAS dans l'architecture — et pourquoi

| Écarté | Motif |
|---|---|
| Modèle de prédiction en production | Plafond RPS 0,19–0,21[9] ; aucun edge durable démontré contre une clôture sharp. Reste en F3, hors chemin critique, rôle de filtre optionnel |
| LLM local | Pas de GPU ; 1,5B int4 = 1,2 Go qui concurrencent le cache disque de la collecte |
| Site web consultable comme canal principal | Le levier de vitesse meurt dès qu'on attend que l'utilisateur ouvre une page |
| API de placement de paris | Aucun bookmaker n'en expose publiquement. Le placement reste manuel |
| Combinés | Marge composée[32] + croissance divisée par 6,3 |
| Marchés sans clôture sharp (National 1-2, Galles, Estonie, Lettonie) | Edge invérifiable[34] |
| Compte propriétaire | **Hors v1, décision ouverte** : seul moyen d'atteindre la preuve de **niveau 1** (exécutée). La v1 repose sur le **niveau 2** (prix observés) — voir §3 bis |

---

## 10. Ordre de construction

| Jalon | Livrable | Critère de sortie |
|---|---|---|
| **J1** | Collecteur + `odds_delta` | 14 jours de collecte continue sans trou > 10 min |
| **J2** | Normaliseur + mapping | 100 % des matchs du périmètre appariés entre books |
| **J3** | `closing_line` figée | clôture capturée pour > 95 % des événements suivis |
| **J4** | Moteur + `filtered_out` | taux de flags mesuré sur 2 semaines (paramètre inconnu à ce jour) |
| **J5** | Diffuseur + `bet` | 100 paris enregistrés en mode `signal` |
| **J6** | Mesure CLV | rapport reproductible, IC calculé |
| **J7** | Décision | CLV ≥ +2 % sur ≥ 500 paris → on continue ; sinon **arrêt** et bascule vers le contenu |

**Aucun jalon ne dépend d'un modèle de prédiction.** Si J7 échoue, le projet se réoriente sans avoir jeté de travail de modélisation.
