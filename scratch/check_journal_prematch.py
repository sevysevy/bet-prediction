import sqlite3
import re

def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

conn = sqlite3.connect('data/journal.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT match, selection, prob_fair, odds_offered, bookmaker, ev, created_at FROM recommendations ORDER BY id DESC")
all_recs = cur.fetchall()
print(f"Total rows in journal: {len(all_recs)}")

# Group by match and selection to see pre-match odds
sample_matches = ['Everton - Chelsea', 'Brentford - Liverpool', 'Venezia - Napoli', 'Strasbourg - Paris Saint Germain', 'Bayern Munich - RB Leipzig']
for target in sample_matches:
    print(f"\nSearching for {target}:")
    found = [r for r in all_recs if norm(target.split(' - ')[0]) in norm(r['match']) and norm(target.split(' - ')[1]) in norm(r['match'])]
    if found:
        for f in found[:3]:
            print(f"  {f['match']} | Sel: {f['selection']} | Prob: {f['prob_fair']:.1%} | Cote: {f['odds_offered']} ({f['bookmaker']}) | EV: {f['ev']:+.1%} | at: {f['created_at'][:16]}")
    else:
        print("  Not found in journal")
