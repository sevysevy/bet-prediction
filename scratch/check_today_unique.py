import json

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])
today_sels = [s for s in sels if (s.get('kickoff') or '').startswith('2026-10-17')]

matches_seen = set()
for s in today_sels:
    m = s.get('match')
    if m not in matches_seen:
        matches_seen.add(m)
        print(f"{m} | kickoff: {s.get('kickoff')} | status: {s.get('status')} | score: {s.get('score_str')}")
