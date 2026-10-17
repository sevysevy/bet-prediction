import json
import math

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])

def compute_portal2_score(p, price, ev=None, p_threshold=0.40, k_scale=25.0):
    if p <= 0.0 or p >= 1.0 or price <= 1.0:
        return 0.0, 0.0, 0.0, 0.0, "C"
        
    if ev is None:
        ev = (p * price) - 1.0
        
    if ev <= 0.0:
        return 0.0, 0.0, 0.0, 0.0, "C"
        
    # Variance / Standard deviation
    # sigma = sqrt(p * (1 - p)) * (price - 1)
    sigma = math.sqrt(p * (1.0 - p)) * (price - 1.0)
    if sigma <= 1e-6:
        return 0.0, 0.0, 0.0, 0.0, "C"
        
    sharpe = ev / sigma
    
    # Sharp collapse for p < 0.40:
    # Uses steep polynomial decay (p / 0.40)^6
    if p < p_threshold:
        penalty = (p / p_threshold) ** 6.0
    else:
        penalty = 1.0 + 0.50 * (p - p_threshold)
        
    penalized_sharpe = sharpe * penalty
    
    # Bet Quality Index (0 to 100)
    bqi = round(100.0 * (1.0 - math.exp(-k_scale * penalized_sharpe)), 1)
    
    if bqi >= 80.0:
        grade = "A+"
    elif bqi >= 65.0:
        grade = "A"
    elif bqi >= 50.0:
        grade = "B+"
    elif bqi >= 35.0:
        grade = "B"
    else:
        grade = "C"
        
    return sigma, sharpe, penalized_sharpe, bqi, grade

scored_list = []
for s in sels:
    p = float(s.get('prob', 0))
    price = float(s.get('price', 1.0))
    ev = float(s.get('ev', (p * price) - 1.0))
    sigma, sharpe, pen_sharpe, bqi, grade = compute_portal2_score(p, price, ev)
    if bqi > 0:
        item = dict(s)
        item['sigma'] = round(sigma, 4)
        item['sharpe'] = round(sharpe, 4)
        item['penalized_sharpe'] = round(pen_sharpe, 4)
        item['bqi_score'] = bqi
        item['grade'] = grade
        scored_list.append(item)

best_by_match = {}
for s in scored_list:
    m = s.get('match') or s.get('match_id')
    if m not in best_by_match or s['bqi_score'] > best_by_match[m]['bqi_score']:
        best_by_match[m] = s

top_list = sorted(best_by_match.values(), key=lambda x: x['bqi_score'], reverse=True)

print(f"{'#':<3} | {'Grade':<5} | {'Score':<5} | {'Match':<36} | {'Selection':<18} | {'p':<6} | {'Cote':<5} | {'EV':<7} | {'Sharpe':<6}")
print("-" * 100)
for i, s in enumerate(top_list[:30], 1):
    m = s.get('match', '')[:35]
    sel = s.get('sel', '')[:18]
    p_str = f"{s['prob']*100:.1f}%"
    odds_str = f"{s['price']:.2f}"
    ev_str = f"{s['ev']*100:+.1f}%"
    sharpe_str = f"{s['sharpe']:.3f}"
    print(f"{i:<3} | {s['grade']:<5} | {s['bqi_score']:<5} | {m:<36} | {sel:<18} | {p_str:<6} | {odds_str:<5} | {ev_str:<7} | {sharpe_str:<6}")
