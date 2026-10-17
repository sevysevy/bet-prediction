import json
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

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
    match_str = s.get('match') or ''
    if ' - ' in match_str:
        h, a = match_str.split(' - ', 1)
        ko = (s.get('kickoff') or '')[:10]
        return f"{norm_team(h)}_vs_{norm_team(a)}_{ko}"
    return str(s.get('match_id') or match_str)

with open('_site/data.json', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])

def run_portal_1(selections, arbitration="safest"):
    # 1. Classification
    candidates_by_match = defaultdict(list)
    bruit_count = 0
    
    for s in selections:
        p = s.get('prob')
        price = s.get('price')
        ev = s.get('ev')
        
        if p is None or price is None or price <= 1.0:
            continue
            
        # Corbeille a bruit : exclusion stricte de p < 0.40
        if p < 0.40:
            bruit_count += 1
            continue
            
        tier = None
        # Palier 1 'Coffre-Fort'
        if p >= 0.65 and price >= 1.25:
            tier = "coffre_fort"
        # Palier 2 'Pépites Value'
        elif 0.45 <= p < 0.65 and (ev or 0) > 0.01 and 1.50 <= price <= 2.30:
            tier = "pepite_value"
            
        if tier:
            c = dict(s)
            c["_tier"] = tier
            mk = get_match_key(s)
            candidates_by_match[mk].append(c)
            
    # 2. Match deduplication & arbitration
    qualified = []
    for mk, cands in candidates_by_match.items():
        if arbitration == "safest":
            # Priority: coffre_fort over pepite_value, then highest prob, highest ev, highest price
            best = sorted(
                cands,
                key=lambda x: (
                    1 if x["_tier"] == "coffre_fort" else 0,
                    x.get("prob") or 0.0,
                    x.get("ev") or 0.0,
                    x.get("price") or 0.0
                ),
                reverse=True
            )[0]
        elif arbitration == "attractive":
            # Priority: pepite_value over coffre_fort, then highest ev, highest prob, highest price
            best = sorted(
                cands,
                key=lambda x: (
                    1 if x["_tier"] == "pepite_value" else 0,
                    x.get("ev") or 0.0,
                    x.get("prob") or 0.0,
                    x.get("price") or 0.0
                ),
                reverse=True
            )[0]
        else:
            best = cands[0]
            
        tier = best.pop("_tier")
        if tier == "coffre_fort":
            best["tier"] = "coffre_fort"
            best["badge"] = "🛡️ Coffre-Fort"
            best["label"] = "Bases Solides"
            best["strike_rate_estime"] = round((best.get("prob") or 0.0) * 100, 1)
        else:
            best["tier"] = "pepite_value"
            best["badge"] = "💎 Pépites Value"
            best["label"] = "Pépites Value"
            best["strike_rate_estime"] = round((best.get("prob") or 0.0) * 100, 1)
            
        qualified.append(best)
        
    # Sort: coffre_fort first (descending prob), then pepite_value (descending ev)
    cf = sorted([q for q in qualified if q["tier"] == "coffre_fort"], key=lambda x: -(x.get("prob") or 0))
    pv = sorted([q for q in qualified if q["tier"] == "pepite_value"], key=lambda x: -(x.get("ev") or 0))
    return cf + pv, bruit_count

res_safest, b1 = run_portal_1(sels, "safest")
res_attr, b2 = run_portal_1(sels, "attractive")

print(f"=== RESULTATS ARBITRATION: SAFEST ===")
cf_s = [s for s in res_safest if s['tier'] == 'coffre_fort']
pv_s = [s for s in res_safest if s['tier'] == 'pepite_value']
print(f"Total qualifiés: {len(res_safest)}")
print(f"  - 🛡️ Coffre-Fort (Bases Solides): {len(cf_s)}")
print(f"    * Cote moyenne: {sum(s['price'] for s in cf_s)/len(cf_s):.2f}")
print(f"    * Probabilité moyenne (Strike Rate estimé): {sum(s['prob'] for s in cf_s)/len(cf_s)*100:.2f}%")
print(f"    * EV moyen: {sum(s['ev'] for s in cf_s)/len(cf_s)*100:+.2f}%")
print(f"  - 💎 Pépites Value: {len(pv_s)}")
print(f"    * Cote moyenne: {sum(s['price'] for s in pv_s)/len(pv_s):.2f}")
print(f"    * Probabilité moyenne (Strike Rate estimé): {sum(s['prob'] for s in pv_s)/len(pv_s)*100:.2f}%")
print(f"    * EV moyen: {sum(s['ev'] for s in pv_s)/len(pv_s)*100:+.2f}%")
print(f"Corbeille à bruit (p < 0.40): {b1} sélections")

print(f"\n=== RESULTATS ARBITRATION: ATTRACTIVE ===")
cf_a = [s for s in res_attr if s['tier'] == 'coffre_fort']
pv_a = [s for s in res_attr if s['tier'] == 'pepite_value']
print(f"Total qualifiés: {len(res_attr)}")
print(f"  - 🛡️ Coffre-Fort: {len(cf_a)}")
print(f"  - 💎 Pépites Value: {len(pv_a)}")
