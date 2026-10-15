# Fiche F5 — Détection de valeur et preuve par le CLV (Closing Line Value)

Statut : `Décomposée — non gelée` · Dernière mise à jour : 2026-10-15
Dépend de : F3 (moteur), F4 (évaluation) · Bloque : F9 (track record), F8 (bankroll)

## ① État actuel

Aucun actif : pas de base de paris, pas de collecte de cotes de clôture, pas d'outil de mesure. Rien n'est construit.
Il n'existe donc **aucune preuve, ni positive ni négative**, sur la capacité de la plateforme à battre une cote de clôture.

## ② État de l'art (ce qui est établi, contesté, ou non documenté)

### Établi
- La cote de clôture d'un book sharp (Pinnacle, Circa) est le meilleur estimateur public disponible ; sous l'hypothèse martingale, les cotes antérieures sont statistiquement non significatives [22].
- Le marché absorbe l'information avec un délai médian d'environ 3 heures ; la clôture est significativement plus exacte que l'ouverture [16].
- Les lignes surréagissent : variations négativement autocorrélées, exploitables [17].
- La marge n'est pas uniforme : ~2,5 % en moyenne, mais ~10 % sur une cote de 10,00 [31]. La perte moyenne réelle dépasse la formule d'overround de ~20 % (foot) et ~40 % (tennis) [28].
- Le handicap asiatique, très concurrentiel, ne présente pas de biais favori-outsider [26].
- Sur 11 ligues, 8 sont efficientes ; 3 seulement laissent des opportunités [5].
- Le CLV mesuré contre la clôture sharp **dévigorisée** est une estimation de la valeur attendue : ROI attendu ≈ CLV [30].
- Cas réel de validation : ~20 000 paris, profit 3,4 % vs valeur attendue 4,0 % [30].

### Chiffres de dimensionnement (calculés)
Écart-type du P&L ≈ 1,00 par pari à cote 2,00 ; écart-type du CLV ≈ 0,10 [30]. Test bilatéral 5 %, puissance 80 % :

| Edge à détecter | Paris via le P&L | Paris via le CLV | Gain |
|---|---|---|---|
| 1,0 % | 78 489 | 785 | 100× |
| 2,0 % | 19 623 | 197 | 100× |
| 3,0 % | 8 721 | 88 | 99× |
| 5,0 % | 3 140 | 32 | 98× |

### Contesté / instable
- **Edge détecté ≠ edge réalisable.** Backtest public : flags de valeur battant la clôture Pinnacle dévigorisée de +2,29 % (±0,30, n = 2 649) ; +1,85 % au moment de la détection ; +0,79 % au prix réellement disponible dans l'heure [32].
- ~50 modèles construits par le même praticien : aucun ne bat le marché sharp après marge [32].

### Non documenté / limite du critère
- Les « odds originators » (modèle réellement original encore inconnu du marché) **ne montrent pas de CLV au début** : leur information n'est pas encore dans la ligne [30]. Le CLV n'est donc pas un critère valable pour la phase 1 d'un modèle original.
- Aucune source académique ne mesure le taux d'échec des sites de prédiction, ni la corrélation entre CLV affiché publiquement et ROI réel.

## ③ Décisions à trancher

- **D1 — Référence sharp** : Pinnacle, Circa, ou exchange (Betfair) ? Que faire quand aucune n'existe sur le marché ciblé ?
- **D2 — Méthode de dévigorisation** : probabilités normalisées (retenues) ou inverse des cotes (biaisée — à proscrire) [3].
- **D3 — Fenêtre de mesure** : moyenne glissante sur 100 paris, décision sur 300–500.
- **D4 — Critère de décision** : seuil de go/no-go, chiffré.
- **D5 — Critère de remplacement pour un modèle original** en phase 1 (calibration ECE/RPS) [7][8].
- **D6 — Indépendance de la mesure** : si la sélection des paris utilise la ligne sharp (Pinnacle) comme référence, alors mesurer le CLV contre la même ligne sharp **n'est pas une validation indépendante**. Exiger une période de test **pré-enregistrée** (dates, ligues, marchés, modèle figé, aucun re-entraînement) et publier les résultats quoi qu'il arrive.
- **D7 — Exécution** : anticiper la limitation de compte (diversité de books, exchange) ou renoncer au pari propriétaire [20][21].

## ④ Spécification cible (à geler)

**Table `bets`** — une ligne par pari, écrite au moment du pari, jamais modifiée ensuite :
`bet_id`, `placed_at` (UTC), `book`, `market`, `selection`, `odds_taken`, `stake`, `model_version`, `model_prob`,
`close_odds_sharp`, `close_source`, `close_captured_at`, `devig_method`, `close_fair_prob`, `clv`.

**Rapport CLV** : moyenne, intervalle de confiance, n, courbe glissante 100, décomposition par book / ligue / marché / odds bucket, et **table `pari pris en compte`** (aucune exclusion après coup, sauf pari annulé par le book).

**Critère de décision gelé** (proposition) :
- CLV moyen ≥ **+2,0 %** sur ≥ 500 paris, contre clôture sharp dévigorisée → edge jugé réel, on continue.
- CLV moyen entre +1,0 % et +2,0 % après 1 000 paris → zone grise, on ne généralise pas, on ne monétise pas.
- CLV moyen < **+1,0 %** après 800 paris → pas d'edge. Arrêt du pari propriétaire, basculement vers le contenu.

**Critères d'acceptation**
1. Le pipeline CLV tourne sans intervention manuelle et horodate chaque pari à la seconde.
2. La dévigorisation utilise la méthode par probabilités normalisées, testée sur un jeu de référence.
3. Le rapport CLV est reproductible depuis la table `bets` seule.
4. Aucun pari retiré du décompte après enregistrement.

## Questions ouvertes

- Q1 : quelle référence sharp pour les ligues africaines, et sinon, le projet accepte-t-il un edge invérifiable ?
- Q2 : le CLV est-il un critère adapté si la stratégie repose sur la vitesse (levier b) plutôt que sur le prix ?
- Q3 : quelle est la tolérance de la plateforme au fait de devoir annoncer publiquement un CLV négatif ?

## Preuve externe

| Source ID | Comportement ou explication attendue | Pertinence |
|---|---|---|
| [3] | La méthode par inverse des cotes est biaisée en faveur de l'efficience ; utiliser les probabilités normalisées | Détermine D2 |
| [16] | La clôture est plus exacte que l'ouverture ; délai médian d'absorption ~3 h | Justifie la référence de clôture |
| [17] | Surréaction des lignes, autocorrélation négative exploitable | Levier (b) |
| [22] | Sous l'hypothèse martingale, la dernière cote est le meilleur prédicteur | Fondement du CLV |
| [26] | Pas de biais favori-outsider sur le handicap asiatique | Filtre de marché |
| [28] | L'overround sous-estime la perte réelle de 20 % (foot) / 40 % (tennis) | Seuil de rentabilité |
| [30] | ROI attendu ≈ CLV ; écarts-types P&L 1,00 vs CLV 0,10 ; limite du CLV pour un odds originator | Dimensionnement + D5 |
| [31] | Marge non uniforme, ~10 % sur une cote de 10,00 | Éviter les cotes longues |
| [32] | Edge détecté +2,29 % → réalisable +0,79 % ; 50 modèles, aucun ne bat le marché sharp | Cadrage des attentes |
| [20][21] | Limitations et fermetures de comptes gagnants | D7 |
