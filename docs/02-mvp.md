# MVP — « Les événements et combinés qui ont le plus de chance de passer »

Version 1 · 2026-10-15 · Périmètre : **2 à 3 championnats, pré-match, 1X2 + moneyline**

---

## 1. Ce qu'on construit, en une phrase

Une **page générée automatiquement** qui affiche, pour les matchs du jour, les sélections classées par
**probabilité de passer** — et les combinés les plus probables construits à partir de ces sélections.

## 2. La bonne nouvelle : ce MVP ne nécessite AUCUNE donnée historique

C'est le pivot important. La « chance de passer » n'a pas besoin d'être **prédite** : le marché la
**donne**. Une cote n'est rien d'autre qu'une probabilité déguisée, à la marge près.

| Ce qu'on croyait nécessaire | Réalité pour ce MVP |
|---|---|
| 10 ans de résultats | ❌ inutile |
| Un modèle entraîné (Dixon-Coles, GBM) | ❌ inutile |
| Machine puissante | ❌ inutile — 4 Go suffisent largement |
| Historique de cotes | ❌ inutile |
| **Des cotes du jour, dévigorisées** | ✅ **c'est tout** |

**Conséquence : le MVP est livrable cette semaine, sans le jalon J1 de l'architecture.**
Toute la machinerie de collecte continue, de capture de clôture et de mesure CLV reste valable, mais
elle n'est **pas** un prérequis pour cette page.

---

## 3. Le pipeline — 5 étapes, un seul script

```
 ① FETCH          25 lignes   →  cotes du jour, 1 book sharp + 2-3 books mous
        │
 ② DEVI G        30 lignes   →  p_fair = proba_normalisée(cotes sharp)
        │                       (jamais 1/cote brut : biaisé)
        │
 ③ PROBA          5 lignes   →  « chance de passer » = p_fair
        │
 ④ COMBINÉS      40 lignes   →  produit des p_fair, jambes de matchs DIFFÉRENTS
        │
 ⑤ RENDU         60 lignes   →  page HTML statique
```

**Total : ~160 lignes de Python.** Pas de base de données, pas de serveur web : un fichier HTML écrit
par un `cron` une fois par jour. Sur 4 Go, c'est indolore.

---

## 4. Ce que la page affiche — et pourquoi deux classements

Chaque sélection porte **deux** chiffres, et c'est non négociable :

| Colonne | Sens |
|---|---|
| **Chance de passer** | la probabilité du marché, dévigorisée — calibrée, fiable |
| **Cote** | la meilleure cote disponible, avec le book qui la propose |
| **EV** | ce que tu gagnes ou perds en espérance sur cette mise |

```
┌──────────────────────────────────────────────────────────────────────┐
│  LES PLUS PROBABLES — aujourd'hui                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Sélection               Chance   Cote   Book     EV                  │
│ ──────────────────────────────────────────────────────────────────── │
│ Man City gagne            90 %   1,06   BookM  −4,6 %                │
│ Bayern gagne              88 %   1,08   BookN  −4,8 %                │
│ Over 0,5 but              86 %   1,09   BookM  −6,3 %                │
│ Lille ne perd pas         85 %   1,10   BookO  −6,5 %                │
│ Real gagne                80 %   1,18   BookN  −5,6 %                │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  COMBINÉS LES PLUS PROBABLES                                         │
├──────────────────────────────────────────────────────────────────────┤
│ # Jambes  Chance   Cote   EV                                         │
│ ──────────────────────────────────────────────────────────────────── │
│ 2 jambes   81 %    1,10   −11,0 %   ⚠                                │
│ 3 jambes   73 %    1,15   −16,0 %   ⚠⚠                               │
│ 5 jambes   59 %    1,27   −25,3 %   ⚠⚠⚠                              │
│ 8 jambes   43 %    1,46   −37,3 %   ✖                                │
└──────────────────────────────────────────────────────────────────────┘
```

### Le chiffre à ne pas perdre de vue

| Jambes | Chance de passer | Marge effective | EV (book à 6 %) |
|---|---|---|---|
| 1 | 90,0 % | 6,0 % | −5,7 % |
| 2 | 81,0 % | 11,6 % | −11,0 % |
| 3 | 72,9 % | 16,9 % | −16,0 % |
| 5 | 59,0 % | 26,6 % | −25,3 % |
| 8 | 43,0 % | 39,0 % | −37,3 % |

**Les deux critères s'opposent frontalement** : plus les jambes sont favorites, plus la « chance de
passer » est élevée — et plus l'EV s'effondre. Une page qui n'affiche que la chance de passer oriente
mécaniquement l'utilisateur vers les paris les **plus perdants**.

Le MVP fait donc exactement ce qui est demandé, **plus la colonne EV**. Ce n'est pas du scepticisme :
c'est le seul moyen que la page ne soit pas un piège.

**Le retournement, à connaître** : si chaque jambe a un *vrai* edge de +4 %, le combiné devient
+4,0 % à 1 jambe, +8,2 % à 2, +12,5 % à 3, +21,7 % à 5. Les combinés ne sont pas *par nature* mauvais —
ils amplifient. Ils amplifient aujourd'hui une marge négative.

---

## 5. La règle de construction des combinés

| Règle | Valeur |
|---|---|
| Jambes autorisées | uniquement `p_fair ≥ 0,75` |
| Nombre de jambes | 2 à 4. **Au-delà de 4 → refusé** |
| Corrélation | **une seule jambe par match** (deux marchés du même match sont corrélés : le produit des probabilités est alors faux) |
| Tri | par chance de passer (comme demandé) |
| Affichage EV | obligatoire, formaté en rouge si < −10 % |
| Classement alternatif | un onglet « meilleure valeur » triant par EV, même s'il est vide |

L'onglet « meilleure valeur » **sera vide la plupart des jours.** C'est le résultat honnête, et le
laisser visible vaut mieux que le supprimer.

---

## 6. Stack

| Élément | Choix | Motif |
|---|---|---|
| Langage | Python 3.12, `requests` | 160 lignes |
| Sortie | **un fichier HTML statique** | zéro serveur, zéro base, zéro RAM au repos |
| Cadence | `cron` quotidien + un rafraîchissement toutes les 30 min avant les matchs | 140 s de latence non requises ici |
| Hébergement | le même VPS, servi par `caddy`/`nginx` | quelques Mo |
| Bibliothèque | `httpx`, `jinja2` (ou f-string) | rien de lourd |

**Mémoire au repos : ~0.** La page est un fichier sur disque.

---

## 7. Critères d'acceptation

1. La page se génère sans intervention et affiche les matchs du jour.
2. Chaque ligne porte : sélection, chance de passer, cote, book, **EV**.
3. La dévigorisation est vérifiée : la somme des probabilités fair d'un événement = 1,0000.
4. Aucun combiné ne mélange deux sélections du même match.
5. Aucun combiné à plus de 4 jambes n'est proposé.
6. Le temps de génération < 30 s pour 3 championnats.
7. Le bandeau d'étiquetage est présent : *« probabilités issues des cotes du marché, non des pronostics. Aucune performance garantie. »*

---

## 8. Ce qui n'est PAS dans ce MVP — et pourquoi

| Écarté | Motif |
|---|---|
| Modèle de prédiction | inutile : la cote *est* la probabilité (et la modélisation ne bat pas la clôture[9]) |
| Historique, backtest, CLV | ce sont les jalons J1–J6, à garder pour plus tard |
| Notifications push | la page suffit pour valider l'idée |
| Compte utilisateur, paiement | validation d'abord |
| Championnats sans cote sharp (National 1-2, Galles, Estonie, Lettonie) | probabilités faussées par la marge[34] |
| In-play | hors périmètre |

---

## 9. Le seul risque à surveiller

Le produit tel que demandé **fonctionne** : la « chance de passer » est exactement la probabilité du
marché, et le marché est bien calibré. Un utilisateur qui parie sur les favoris à 90 % gagnera
effectivement ~90 % de ses paris.

Il perdra de l'argent quand même — 5 à 6 % de sa mise en espérance sur les simples, 25 % sur un
combiné à 5 jambes. **Le MVP dit donc la vérité sur la probabilité et le mensonge sur la rentabilité,
sauf si la colonne EV est affichée.** C'est la seule ligne de défense, et elle tient en une colonne.
