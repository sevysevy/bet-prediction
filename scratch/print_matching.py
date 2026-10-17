import json

with open('_site/data.json', 'r', encoding='utf-8') as f:
    sels = json.load(f)['selections']

for s in sels:
    p = s.get('prob') or 0
    price = s.get('price') or 0
    ev = s.get('ev') or 0
    margin = s.get('sharp_margin') or 1.0
    sharp = s.get('sharp') or ''
    if p >= 0.55 and 1.35 <= price <= 2.30 and ev >= 0.0:
        print(f"Match: {s.get('match_id')} | {s.get('match')} | Sel: {s.get('sel')} | Odds: {price} | Prob: {p:.4f} | EV: {ev:.4f} | Margin: {margin:.4f} | Sharp: {sharp} | Book: {s.get('book')}")
