import json
import datetime
from src.build_site import evaluate_outcome, norm_team_key

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])
now = datetime.datetime.now(datetime.timezone.utc)

today_sels = [s for s in sels if (s.get('kickoff') or '').startswith('2026-10-17')]

fixed_finished = []
fixed_live = []

for s in today_sels:
    ko = s.get('kickoff')
    dt = datetime.datetime.fromisoformat(ko.replace('Z', '+00:00')) if ko else None
    diff_min = (now - dt).total_seconds() / 60 if dt else 0
    hs = s.get('home_score')
    as_ = s.get('away_score')
    
    if diff_min > 135:
        # Match started > 2h15 ago -> FINISHED
        outcome = evaluate_outcome(s.get('market_type'), s.get('sel'), s.get('match').split(' - ')[0], s.get('match').split(' - ')[1], hs, as_)
        fixed_finished.append((s.get('match'), s.get('sel'), f"{hs} - {as_}", outcome, diff_min))
    else:
        fixed_live.append((s.get('match'), s.get('sel'), f"{hs} - {as_}", diff_min))

print(f"Total today: {len(today_sels)}")
print(f"Should be FINISHED (> 135 min): {len(fixed_finished)}")
print(f"Should be genuinely LIVE (in play right now): {len(fixed_live)}")

print("\nSample FINISHED matches:")
seen = set()
for m, sel, sc, out, diff in fixed_finished:
    if m not in seen:
        seen.add(m)
        print(f"  {m} [{sc}] -> {sel}: {out} (Kickoff il y a {diff/60:.1f}h)")

print("\nSample genuinely LIVE matches (currently in second half):")
seen = set()
for m, sel, sc, diff in fixed_live:
    if m not in seen:
        seen.add(m)
        print(f"  {m} [{sc}] (Kickoff il y a {diff:.0f} min)")
