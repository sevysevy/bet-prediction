import json

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])

# Option A: Strict Strike Rate p >= 65%, Cote >= 1.25, EV >= -0.03
opt_a = [s for s in sels if s['prob'] >= 0.65 and s['price'] >= 1.25 and s['ev'] >= -0.03]

# Option C Tier 1: Coffre-fort (p >= 65%, Cote >= 1.25)
tier_1 = [s for s in sels if s['prob'] >= 0.65 and s['price'] >= 1.25]

# Option C Tier 2: Pepites Value (p >= 45%, EV > 0.0, price <= 2.20)
tier_2 = [s for s in sels if 0.45 <= s['prob'] < 0.65 and s['ev'] > 0.0 and s['price'] <= 2.20]

print(f"Option A (Filtre Ultra-Solide p>=65%, EV>=-3%): {len(opt_a)} sélections")
print(f"Option C - Tier 1 (Bases Solides / Coffre-Fort p>=65%): {len(tier_1)} sélections")
print(f"Option C - Tier 2 (Pépites Value 45-65% avec EV>0): {len(tier_2)} sélections")

print("\n--- Échantillon Tier 1 (Bases Solides / Coffre-Fort) ---")
seen = set()
for s in sorted(tier_1, key=lambda x: -x['prob']):
    if s['match'] not in seen:
        seen.add(s['match'])
        print(f"  {s['match']} -> {s['sel']} | Chance: {s['prob']*100:.1f}% | Cote: {s['price']} ({s['book']}) | EV: {s['ev']*100:+.1f}%")
        if len(seen) >= 6:
            break

print("\n--- Échantillon Tier 2 (Pépites Value avec EV > 0) ---")
seen = set()
for s in sorted(tier_2, key=lambda x: -x['ev']):
    if s['match'] not in seen:
        seen.add(s['match'])
        print(f"  {s['match']} -> {s['sel']} | Chance: {s['prob']*100:.1f}% | Cote: {s['price']} ({s['book']}) | EV: {s['ev']*100:+.1f}%")
        if len(seen) >= 6:
            break
