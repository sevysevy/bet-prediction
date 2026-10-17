import json
from collections import Counter

with open('_site/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

sels = data.get('selections', [])

sharps = Counter(s.get('sharp') for s in sels)
print("Sharps distribution:", dict(sharps))

books = Counter(s.get('book') for s in sels)
print("Books distribution:", dict(books))

pinnacle_sels = [s for s in sels if (s.get('sharp') or '').lower() == 'pinnacle']
print(f"Total Pinnacle sharp: {len(pinnacle_sels)}")
pinnacle_c1 = [s for s in pinnacle_sels if (s.get('prob') or 0) >= 0.55]
pinnacle_c2 = [s for s in pinnacle_c1 if 1.35 <= (s.get('price') or 0) <= 2.30]
pinnacle_c3 = [s for s in pinnacle_c2 if (s.get('ev') or 0) >= 0.0]
print(f"Pinnacle prob >= 0.55: {len(pinnacle_c1)}")
print(f"Pinnacle prob >= 0.55 and 1.35 <= price <= 2.30: {len(pinnacle_c2)}")
print(f"Pinnacle prob >= 0.55 and 1.35 <= price <= 2.30 and ev >= 0: {len(pinnacle_c3)}")

for s in pinnacle_c2[:10]:
    print(f"  {s.get('match')} | {s.get('sel')} | P={s.get('prob'):.4f} | Odd={s.get('price')} | EV={s.get('ev'):.4f} | Margin={s.get('sharp_margin'):.4f} | Book={s.get('book')}")

# Check EVs in pinnacle_sels
evs = [s.get('ev') or 0 for s in pinnacle_sels]
print("Pinnacle EV min:", min(evs), "max:", max(evs))

# How EV is computed when book == sharp == Pinnacle:
# In Pinnacle lines: price is Pinnacle odds, prob is Pinnacle devigged prob.
# EV = prob * price - 1. Because of Pinnacle margin (e.g. 3-4%), prob * price is approx (1 / overround) * price * price? No, prob = (1/price)/overround, so prob * price = 1 / overround = 1 / (1 + margin) < 1 !
# Therefore, when book == Pinnacle (no soft bookmaker offering a higher price than Pinnacle's devigged price), EV = prob * price - 1 is ALWAYS NEGATIVE (approx -margin)!
# Only when another book (or exchange like Betfair with higher odds) is used, or when price > 1/prob, can EV >= 0!
