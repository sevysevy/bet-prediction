# Fiche F1 v2 — Couverture sportive et compétitions cibles

Statut : `Décomposée — non gelée` · Révision 2 · Périmètre demandé par Yves Chris : championnats européens
Dépend de : F0 · Bloque : F2, F3, F5, F12

## ① État actuel

Aucun actif. Périmètre souhaité exprimé (v1) :
France Ligue 1 / Ligue 2 / National 1 / National 2 · Allemagne Bundesliga 1-2 · Italie Serie A-B ·
Espagne Liga 1-2 · Angleterre PL / Championship / League One / League Two / National League ·
puis « les D1 et D2 des pays européens » : Pays de Galles, Estonie, Lettonie, etc.

## ② État de l'art et vérification de couverture

### Méthode de vérification
La contrainte opérationnelle est l'**accès** : Pinnacle a fermé son API publique en juillet 2025 [33],
la clôture sharp passe donc aujourd'hui par un agrégateur. La liste de couverture de l'agrégateur [34]
est donc le document de référence : une compétition absente de cette liste est une compétition où
aucune clôture sharp n'est **obtenable**, donc où l'edge est **invérifiable**.

⚠️ Limites de cette vérification :
- La liste Pinnacle elle-même est derrière un mur d'authentification (non vérifiable sans compte).
- OddsPortal et BetExplorer renvoient des pages anti-robot : couverture par bookmaker non vérifiable.
- Conclusion : [34] établit ce qui est **obtenable via API**, pas ce que Pinnacle price exactement.
  Écart possible à trancher par un test avec clé API gratuite (voir §4, T1).

### Verdict par compétition demandée

| Compétition demandée | Couverture API [34] | Verdict |
|---|---|---|
| France — Ligue 1 | ✅ | Retenu — palier A |
| France — Ligue 2 | ✅ | Retenu — palier A |
| France — National 1 | ❌ | **Écarté — invérifiable** |
| France — National 2 | ❌ | **Écarté — invérifiable** |
| Allemagne — Bundesliga | ✅ | Retenu — palier A |
| Allemagne — Bundesliga 2 | ✅ (+ 3. Liga ✅) | Retenu — palier A |
| Italie — Serie A / Serie B | ✅ ✅ | Retenu — palier A |
| Espagne — La Liga / La Liga 2 | ✅ ✅ | Retenu — palier A |
| Angleterre — Premier League | ✅ | Retenu — palier A |
| Angleterre — Championship | ✅ | Retenu — palier A |
| Angleterre — League One / League Two | ✅ ✅ | Retenu — palier A |
| Angleterre — National League (5e niveau) | ❌ | **Écarté — invérifiable** |
| Pays-Bas, Portugal, Belgique, Turquie, Grèce, Autriche, Suisse, Danemark, Norvège, Pologne, Russie, Écosse, Irlande, Finlande (D1) | ✅ | Retenu — **palier B** |
| Suède — Allsvenskan + Superettan | ✅ ✅ | Retenu — palier B (seul D2 mineur couvert) |
| Pays de Galles | ❌ | **Écarté — invérifiable** |
| Estonie | ❌ | **Écarté — invérifiable** |
| Lettonie | ❌ | **Écarté — invérifiable** |
| D2 des pays mineurs (hors Suède) | ❌ | **Écarté — invérifiable** |
| Coupes : FA Cup, EFL Cup, Coupe de France, DFB-Pokal, Coppa Italia, Copa del Rey | ✅ | Retenu — option |
| UCL, UEL, UECL, qualifications UCL, Ligue des Nations, qualif. Euro / CdM | ✅ | Retenu — option |

### La tension structurelle, quantifiée

Le périmètre souhaité contient l'essentiel de ce qui est **vérifiable** (palier A) et l'intégralité de
ce qui **ne l'est pas** (le « etc. » : pays de Galles, Estonie, Lettonie, National 1-2, 5e niveau anglais).

Or la contrainte d'échantillon joue en sens inverse : atteindre 500 paris (seuil de décision de F5)
demande du volume. Estimation (matchs par journée × 3 issues × books mous surveillés) :

| Périmètre | Books mous | Taux de flags | 500 paris en |
|---|---|---|---|
| Palier A seul (123 matchs/sem) | 1 | 2 % | **68 semaines** |
| Palier A seul | 5 | 2 % | **14 semaines** |
| Palier A + B (242 matchs/sem) | 1 | 2 % | 34 semaines |
| Palier A + B | 5 | 2 % | **7 semaines** |

**Enseignement central : le nombre de books mous surveillés pèse bien plus lourd que l'ajout de
championnats exotiques.** Élargir vers l'Estonie rapporte ~6 matchs/semaine et détruit la mesurabilité ;
surveiller 5 books au lieu d'1 multiplie l'échantillon par 5 sans rien coûter en vérifiabilité.

⚠️ Le taux de flags est **inconnu** : il doit être mesuré, pas supposé. C'est le paramètre T2 de F2.

## ③ Décisions à trancher

| # | Décision | Proposition |
|---|---|---|
| D1 | Palier A retenu tel quel | Oui, périmètre de départ |
| D2 | Palier B (D1 des pays mineurs) | Oui — **pour le volume, pas pour l'inefficience** |
| D3 | Palier C (National 1-2, 5e niveau anglais, Galles, Estonie, Lettonie, D2 mineures) | **Écarté**, avec motif écrit : pas de clôture sharp accessible |
| D4 | Nombre de books mous surveillés simultanément | ≥ 5 dès le départ (levier d'échantillon n°1) |
| D5 | Coupes et compétitions européennes | Incluses, mais matchs moins fréquents → n'entrent pas dans le calcul de volume |
| D6 | Marchés par match | 1X2 dans un premier temps ; O/U seulement après mesure de la marge observée |

## ④ Spécification cible (à geler)

Matrice `ligue × marché × book` avec colonnes : `pays`, `compétition`, `niveau`, `palier` (A/B/C),
`couvert_api` (oui/non, réf. [34]), `marge_observée_%`, `nb_matchs_par_journée`, `book_placement`,
`verdict`, `motif`.

**Règles gelées (proposition)**
1. Aucune ligne `couvert_api = non` n'entre dans le périmètre, **sauf** si une clôture sharp de
   substitution est démontrée sur ≥ 2 saisons (test T1).
2. ≥ 5 books mous surveillés dès le premier jour ; le nombre de books est un paramètre de dimensionnement,
   pas un détail d'implémentation.
3. Le taux de flags observé doit être publié avant toute décision de périmètre complémentaire.
4. Toute ligne écartée est écrite avec son motif — pas de silence sur ce qui a été abandonné.

**Tests à exécuter (bloquants avant gel)**
- **T1** : clé API gratuite → vérifier bookmaker par bookmaker quelles compétitions sont réellement
  servies, et si Pinnacle figure dans la région EU. Si absent, la référence sharp change de nature
  et **F5 doit être réécrite**.
- **T2** : mesurer le taux de flags réels sur 2 semaines de collecte, à seuil fixé, sur palier A.

## Questions ouvertes
- Q1 : la référence sharp retenue est-elle Pinnacle, ou un exchange (Betfair) si Pinnacle n'est pas
  distribué par l'agrégateur ?
- Q2 : le palier C est-il définitivement exclu, ou accepté en mode « contenu seulement » (analyses
  publiées, aucune prétention de mesure) ?
- Q3 : les compétitions africaines et la CAN — dans le périmètre contenu, ou hors sujet ?

## Preuve externe
| Source ID | Élément | Pertinence |
|---|---|---|
| [23] | En Angleterre, les divisions basses : moins de concurrence, volumes plus faibles, parieurs plus informés ; les books n'exploitent pas pleinement les cotes des concurrents | Explique pourquoi le palier C serait attractif… |
| [33] | Pinnacle a fermé son API publique en juillet 2025 ; le CLV n'est fiable que contre une clôture sharp | …et pourquoi il est hors d'atteinte |
| [34] | Liste officielle de couverture de l'agrégateur, par compétition | **Détermine le verdict de chaque ligne du tableau** |
| [5] | 8 marchés sur 11 efficients | Cadrage du palier A |
| [32] | Edge détecté +2,29 % → +0,79 % réalisable | Seuil de flags à mesurer |
