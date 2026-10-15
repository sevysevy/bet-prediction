# Décomposition du projet « Plateforme de prédiction de paris »

**Statut : décomposition uniquement — AUCUNE exécution lancée.**
Chaque fiche doit être gelée (étape ④) avant qu'un seul ticket d'exécution ne soit ouvert.

Cycle imposé pour chaque fiche : **① État de l'art → ② Comparaison marché/standards → ③ Décisions produit → ④ Spécification cible gelée**

---

## A. Contraintes scientifiques déjà gelées (non renégociables)

Issues de la revue de littérature (voir `01-etat-de-lart-scientifique.md`, à venir).

| # | Contrainte | Justification |
|---|---|---|
| C1 | Benchmark obligatoire = **cotes de clôture** (Pinnacle, Betfair), pas les cotes moyennes ni d'ouverture | La clôture est le meilleur prédicteur disponible ; les cotes antérieures sont statistiquement non significatives |
| C2 | Métriques de sélection = **RPS + log-loss + calibration (ECE)**. Jamais l'exactitude seule | Sélection par calibration : ROI moyen +34,69 % vs −35,17 % par exactitude (NBA) |
| C3 | Validation **temporelle walk-forward** stricte. Jamais de split aléatoire | Les splits non temporels gonflent les métriques ; petits échantillons = fausses inefficacités |
| C4 | Afficher la **marge** ET la **perte moyenne réelle** (pas seulement l'overround) | L'overround sous-estime la perte réelle de ~20 % (foot) et ~40 % (tennis) |
| C5 | Cibler les **poches d'inefficience documentées**, pas le résultat principal des grands championnats | 8 marchés sur 11 efficients (Angelini & De Angelis) ; inefficacités non persistantes |
| C6 | Module news = **extraction de faits**, pas analyse de sentiment brut | Revue de 64 études : sentiment = flux de réaction, performances prédictives instables |
| C7 | Preuve d'edge = **CLV** (valeur contre la ligne de clôture), pas le P&L | Le P&L est trop bruité ; les comptes gagnants sont limités/factored |
| C8 | Mise = **Kelly fractionnaire** + mesure du risque de ruine | ECE ≈ 0,11 → Kelly plein augmente le risque de ruine au lieu de la richesse |
| C9 | **Ne jamais promettre un rendement.** Communiquer un intervalle de confiance | Profits in-sample inconsistants out-of-sample ; inefficacités qui se dissipent |

---

## B. Les fiches

### F0 — Cadrage : modèle d'affaires et périmètre légal  · **BLOQUANT**
- **① État de l'art** : littérature économique sur les marchés de paris ; cadre légal camerounais (Loi 2015/012, décret 2019/2300/PM, régimes concession / autorisation / déclaration).
- **② Comparaison marché** : 3 modèles possibles — (a) média/pronostics payants, (b) affiliation, (c) opérateur licencié. Ce que chacun implique : capital, licence, risque.
- **③ Décisions** : modèle de revenus ; statut juridique d'un site d'analyse payante (≠ opérateur) ; juridiction(s) cible.
- **④ Gel** : note de cadrage + **avis d'un juriste camerounais** versé au dossier.
- ⚠️ Point non résolu par mes recherches : aucune source académique ni juridique trouvée sur le modèle économique des sites de pronostics. À trancher, pas à supposer.

### F1 — Couverture sportive et marchés cibles
- **①** : biais favori-outsider ; le handicap asiatique ne présente pas de FLB (marché très concurrentiel).
- **②** : football africain/Cameroun vs grands championnats européens ; 1X2 vs O/U vs BTTS vs handicap asiatique — marge, liquidité, couverture des cotes disponibles.
- **③** : liste fermée ligues × marchés × bookmakers.
- **④ Gel** : matrice de périmètre avec volume/liquidité estimés pour chaque couple.

### F2 — Socle de données (résultats + cotes)
- **①** : littérature sur l'absorption de l'information ; granularité temporelle des cotes.
- **②** : sources disponibles (archives publiques de cotes, APIs), profondeur historique, ouverture vs clôture vs mouvement minute par minute, droits d'usage.
- **③** : schéma de données, pipeline d'ingestion, journal de filiation.
- **④ Gel** : jeu de données de référence (≥ 5–10 saisons, clôture + ouverture + mouvements).

### F3 — Moteur de probabilités (le « maths lourdes »)
- **①** : Dixon & Coles 1997 (Poisson bivarié, composante dynamique, correction de dépendance) ; ratings Elo / pi-ratings / Berrar / GAP ; gradient boosting sur ratings.
- **②** : plafond empirique mesuré — Challenge 2017 : RPS 0,2063 / 52,43 % ; meilleurs postérieurs CatBoost+pi-ratings : 0,1925 / 55,82 %.
- **③** : architecture du modèle, protocole d'entraînement walk-forward, gestion du match nul (angle mort documenté).
- **④ Gel** : spécification du modèle **figée avant tout code**, avec baseline cotes de clôture obligatoire.

### F4 — Calibration et protocole d'évaluation
- **①** : scoring rules (RPS, Brier, log-loss), décomposition de la calibration, critique du RPS.
- **②** : calibration vs exactitude comme critère de sélection ; erreur de calibration observée (ECE ≈ 0,11) et son effet sur Kelly.
- **③** : grille d'acceptation chiffrée (seuil ECE, RPS < baseline cotes, robustesse par ligue/saison).
- **④ Gel** : protocole d'évaluation opposable — c'est lui qui décidera go/no-go pour tout le reste.

### F5 — Détection de valeur et mouvement de marché (CLV)
- **①** : hypothèse martingale ; surréaction des lignes (MLB) ; information récente sous-intégrée (délai médian ~3 h) ; stratégie par probabilités implicites agrégées.
- **②** : mesurer le CLV sans pari réel ; seuils ; comportement des mouvements.
- **③** : algorithme de détection, définition formelle de l'edge et du CLV cible.
- **④ Gel** : spec de l'indicateur + backtest reproductible partagé comme preuve interne.

### F6 — Module news et headlines
- **①** : NLP sur pré-articles de presse (+6,9 pts d'exactitude, nuls et longshots mieux détectés) ; Twitter/sentiment (résultats mitigés) ; in-play (aucun pouvoir prédictif) ; revue de 64 études (instabilité).
- **②** : quelles sources couvrent le football africain ? presse locale vs internationales ; fréquence ; fiabilité.
- **③** : **ontologie de faits** à extraire — blessures, compositions probables, rotation, changement d'entraîneur, calendrier surchargé, enjeux de fin de saison — plus que du score de sentiment.
- **④ Gel** : liste fermée de features texte + **règle de survie** : une feature n'est conservée que si elle améliore le RPS de façon significative en walk-forward. Garde-fou anti-p-hacking obligatoire.

### F7 — In-play / live (optionnel, après F5)
- **①** : le seul segment où le sentiment apporte un signal documenté (upsets, AUC ≈ 80 %) ; contrainte de latence et de rafraîchissement.
- **②** : faisabilité technique et coût des flux temps réel.
- **③** : go/no-go explicite.
- **④ Gel** : décision écrite, motif à l'appui.

### F8 — Gestion de bankroll et recommandations de mise
- **①** : critère de Kelly, Kelly fractionnaire, risque de ruine sous mauvaise calibration.
- **②** : plafonds par pari, exposition max, comportement en série de pertes.
- **③** : logique de mise + avertissements utilisateur obligatoires.
- **④ Gel** : spec de la logique de mise.

### F9 — Preuve, track record et transparence
- **①** : pourquoi les track records publics sont presque toujours invérifiables (survivorship, sélection, absence d'intervalle de confiance) ; preuve que les inefficacités publiées se dissipent.
- **②** : quels indicateurs publier (CLV médian, nb de paris, ROI avec IC, journal verrouillé, taux de limitation).
- **③** : format du track record + **règle de non-modification rétroactive**.
- **④ Gel** : spec de la page preuve.

### F10 — Produit, UX et monétisation
- **①** : protections joueurs exigées (18+, KYC, limites de dépôt, auto-exclusion) ; langues FR/EN ; mobile money (MTN/Orange) comme rails de paiement dominants.
- **②** : gratuit vs payant ; abonnement vs affiliation ; parcours utilisateur.
- **③** : spec produit, écrans clés, mentions légales.
- **④ Gel** : spec produit gelée.

### F11 — Conformité, risque opérationnel et jeu responsable
- **①** : licence (autorisation 5 ans, caution 200 M FCFA, domaine .cm, PSP exclusif, assurance RC, règlement certifié par huissier) ; fiscalité (15 % PBJ + 1 % sur dépôts/retraits) ; sanctions (6 mois–2 ans et/ou 5–25 M FCFA) ; protection des données.
- **②** : limitation/fermeture de comptes gagnants — le risque n'est pas hypothétique, il est documenté et il a mis fin à une stratégie pourtant profitable en argent réel.
- **③** : plan de conformité + stratégie d'exécution (diversité multi-books / exchange, ou renoncement au pari propriétaire).
- **④ Gel** : dossier de conformité validé par un juriste.

---

## C. Ordre de dépendance

```
F0 (cadrage, BLOQUANT)
 └─ F1 (périmètre sport/marchés)
     └─ F2 (données)
         └─ F3 (modèle)  ←→  F4 (évaluation)   [couple indissociable]
              └─ F5 (CLV/valeur)
                  ├─ F6 (news)      ← validation temporelle obligatoire
                  ├─ F8 (bankroll)  ← peut démarrer en parallèle de F6
                  └─ F7 (in-play)   ← go/no-go
                       └─ F9 (track record)
                            └─ F10 (produit) ── F11 (conformité)  [F11 dès F0]
```

**F11 (juriste) et F0 démarrent ensemble** : la décision juridique peut invalider tout le reste.

---

## D. Premier jalon recommandé (le plus petit livrable scientifiquement honnête)

Avant toute interface, avant tout contenu éditorial :

1. Jeu de données fermé : ≥ 5 saisons, cotes d'ouverture et de clôture, 2–3 bookmakers.
2. Un modèle Dixon-Coles de référence + une baseline naïve « cotes de clôture ».
3. Comparaison en RPS / log-loss / ECE en walk-forward.
4. Rapport de calibration + calcul de la marge et de la perte moyenne réelle.

**Critère d'échec assumé** : si le modèle ne bat pas la cote de clôture en RPS, alors le projet est un projet **de contenu et d'analyse**, pas de prédiction — et le modèle d'affaires change (F0 doit rouvrir). Cette conclusion est acceptable et doit être prévue dès maintenant.

---

## E. Hors périmètre pour l'instant

- Tout pari réel engagé par la plateforme ou ses fondateurs.
- Tout engagement de rendement, promesse de gain, ou classement de « pronostiqueurs ».
- Optimisation SEO / acquisition avant validation du jalon D.

---
*Document de décomposition — aucune exécution lancée. Prochaine étape : validation de l'ordre et du périmètre par Yves Chris, puis ouverture de F0 uniquement.*
