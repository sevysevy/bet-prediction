import json
from collections import Counter
import datetime

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])

# Check matches with today's date
today_prefix = "2026-10-17"
today_sels = [s for s in sels if (s.get('kickoff') or '').startswith(today_prefix)]
print(f"Total selections today ({today_prefix}): {len(today_sels)}")

status_counts = Counter(s.get('status') for s in today_sels)
print("Status counts for today:")
for st, cnt in status_counts.items():
    print(f"  {st}: {cnt}")

for st in status_counts.keys():
    print(f"\nSample for status {st}:")
    for s in [x for x in today_sels if x.get('status') == st][:5]:
        print(f"  {s.get('match')} | kickoff: {s.get('kickoff')} | status: {s.get('status')} | score: {s.get('score_str')}")
