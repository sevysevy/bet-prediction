import json
import re
from collections import defaultdict

def norm_team(s: str) -> str:
    s = str(s or "").lower().strip()
    s = re.sub(r'\bst\b', 'saint', s)
    s = re.sub(r'\butd\b', 'united', s)
    s = re.sub(r'\bman\b', 'manchester', s)
    s = re.sub(r'\bsg\b', 'saint germain', s)
    s = re.sub(r'\b(fc|cf|osc|rc|as|ac|ss|rb|fsv|sc|us|ogc|vfl|bvb|afc)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def get_match_key(s: dict) -> str:
    match_str = s.get('match', '')
    if ' - ' in match_str:
        h, a = match_str.split(' - ', 1)
        ko = (s.get('kickoff') or '')[:10]
        return f"{norm_team(h)}_vs_{norm_team(a)}_{ko}"
    return s.get('match_id') or match_str

with open('_site/data.json', encoding='utf-8') as f:
    data = json.load(f)

sels = data.get('selections', [])

# Noise bin: p < 0.40 strictly excluded
# Tier 1 (Coffre-Fort): p >= 0.65, cote >= 1.25
# Tier 2 (Pépites Value): 0.45 <= p < 0.65, EV > 0.01, 1.50 <= cote <= 2.30

t1_candidates = []
t2_candidates = []

for s in sels:
    p = s.get('prob') or 0.0
    price = s.get('price') or 0.0
    ev = s.get('ev') or 0.0
    
    # Noise exclusion
    if p < 0.40:
        continue
        
    if p >= 0.65 and price >= 1.25:
        t1_candidates.append(s)
    elif 0.45 <= p < 0.65 and ev > 0.01 and 1.50 <= price <= 2.30:
        t2_candidates.append(s)

print(f"Total raw Tier 1 candidates: {len(t1_candidates)}")
print(f"Total raw Tier 2 candidates: {len(t2_candidates)}")

# Group by match key
t1_by_match = defaultdict(list)
for s in t1_candidates:
    t1_by_match[get_match_key(s)].append(s)

t2_by_match = defaultdict(list)
for s in t2_candidates:
    t2_by_match[get_match_key(s)].append(s)

print(f"Distinct matches in Tier 1: {len(t1_by_match)}")
print(f"Distinct matches in Tier 2: {len(t2_by_match)}")

# Check if any match in both
match_overlap = set(t1_by_match.keys()).intersection(set(t2_by_match.keys()))
print(f"Overlap between matches in T1 and T2: {len(match_overlap)}")

# How to select best in Tier 1?
# Objective: strike rate > 75% -> "la plus sûre"
# Primary sort: prob (highest first), then EV (highest first), then price (highest first)
t1_selected = []
for mk, lst in t1_by_match.items():
    best = sorted(lst, key=lambda x: (x.get('prob', 0), x.get('ev', 0), x.get('price', 0)), reverse=True)[0]
    t1_selected.append(best)

# How to select best in Tier 2?
# Objective: value bet -> "la plus attractive"
# Primary sort: ev (highest first), then prob (highest first), then price (highest first)
t2_selected = []
for mk, lst in t2_by_match.items():
    best = sorted(lst, key=lambda x: (x.get('ev', 0), x.get('prob', 0), x.get('price', 0)), reverse=True)[0]
    t2_selected.append(best)

avg_p1_prob = sum(s['prob'] for s in t1_selected) / len(t1_selected) if t1_selected else 0
avg_p1_price = sum(s['price'] for s in t1_selected) / len(t1_selected) if t1_selected else 0

avg_p2_prob = sum(s['prob'] for s in t2_selected) / len(t2_selected) if t2_selected else 0
avg_p2_price = sum(s['price'] for s in t2_selected) / len(t2_selected) if t2_selected else 0
avg_p2_ev = sum(s['ev'] for s in t2_selected) / len(t2_selected) if t2_selected else 0

print(f"\n--- PALIER 1 : COFFRE-FORT (Bases Solides) ---")
print(f"Count: {len(t1_selected)}")
print(f"Average Prob (Estimated Strike Rate): {avg_p1_prob*100:.2f}% (Target > 75%: {'VALIDÉ' if avg_p1_prob >= 0.75 else 'ATTENTION'})")
print(f"Average Odds: {avg_p1_price:.2f}")

print(f"\n--- PALIER 2 : PÉPITES VALUE ---")
print(f"Count: {len(t2_selected)}")
print(f"Average Prob: {avg_p2_prob*100:.2f}%")
print(f"Average Odds: {avg_p2_price:.2f}")
print(f"Average EV: {avg_p2_ev*100:+.2f}%")

print(f"\nTOTAL QUALIFIÉS PORTAIL 1: {len(t1_selected) + len(t2_selected)}")
