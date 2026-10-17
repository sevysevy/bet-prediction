import json
from collections import Counter, defaultdict

with open('_site/data.json', encoding='utf-8') as f:
    data = json.load(f)

sels = data.get('selections', [])
print(f"Total sélections brutes: {len(sels)}")

statuses = Counter(s.get('status') for s in sels)
print('Statuts:', dict(statuses))

# 1. Bruit: p < 0.40
bruit = [s for s in sels if (s.get('prob') or 0) < 0.40]
print(f"Corbeille à bruit (p < 0.40): {len(bruit)} sélections")

# 2. Palier 1 brut: p >= 0.65, cote >= 1.25
p1_raw = [s for s in sels if (s.get('prob') or 0) >= 0.65 and (s.get('price') or 0) >= 1.25]
p1_matches = set(s['match'] for s in p1_raw)
print(f"Palier 1 brut (p >= 0.65, cote >= 1.25): {len(p1_raw)} sélections couvrant {len(p1_matches)} matches")

# 3. Palier 2 brut: 0.45 <= p < 0.65, EV > 0.01, 1.50 <= cote <= 2.30
p2_raw = [s for s in sels if 0.45 <= (s.get('prob') or 0) < 0.65 and (s.get('ev') or 0) > 0.01 and 1.50 <= (s.get('price') or 0) <= 2.30]
p2_matches = set(s['match'] for s in p2_raw)
print(f"Palier 2 brut (0.45 <= p < 0.65, EV > 0.01, 1.50 <= cote <= 2.30): {len(p2_raw)} sélections couvrant {len(p2_matches)} matches")

# Overlap between p1 matches and p2 matches
overlap = p1_matches.intersection(p2_matches)
print(f"Matches avec candidats à la fois en P1 et P2: {len(overlap)}")

# Examine Palier 2 details
print("\nDétail des candidats Palier 2:")
for s in p2_raw:
    print(f"  {s['match']} | {s['sel']} | p={s['prob']:.3f} | cote={s['price']} | EV={s['ev']*100:+.2f}% | book={s['book']}")

# Examine Palier 1 top & bottom
print("\nÉchantillon Palier 1 (trié par p décroissant):")
for s in sorted(p1_raw, key=lambda x: -x['prob'])[:10]:
    print(f"  {s['match']} | {s['sel']} | p={s['prob']:.3f} | cote={s['price']} | EV={s['ev']*100:+.2f}% | book={s['book']}")

