import json

with open('_site/data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

sels = d.get('selections', [])
finished = [s for s in sels if s.get('status') == 'FINISHED']
live = [s for s in sels if s.get('status') == 'LIVE']
score_officiel = [s for s in sels if s.get('book') == 'Score Officiel']
fake_odds = [s for s in sels if s.get('price') == 1.0 and s.get('prob') == 1.0]
won = [s for s in finished if s.get('outcome') == 'WON']
lost = [s for s in finished if s.get('outcome') == 'LOST']

print(f"Total selections: {len(sels)}")
print(f"Finished selections: {len(finished)}")
print(f"Live selections: {len(live)}")
print(f"Score Officiel rows: {len(score_officiel)}")
print(f"Fake 1.00 / 100% rows: {len(fake_odds)}")
print(f"Finished WON: {len(won)}")
print(f"Finished LOST: {len(lost)}")

print("\nSample finished selections:")
for s in finished[:10]:
    print(f"  {s.get('match')} [{s.get('score_str')}] | {s.get('sel')} | Chance: {s.get('prob')*100:.1f}% | Cote: {s.get('price')} ({s.get('book')}) | EV: {s.get('ev')*100:+.1f}% -> {s.get('outcome')}")

print("\nSample live selections:")
for s in live[:5]:
    print(f"  {s.get('match')} [{s.get('score_str')}] | {s.get('sel')} | Chance: {s.get('prob')*100:.1f}% | Cote: {s.get('price')} ({s.get('book')}) | EV: {s.get('ev')*100:+.1f}%")
