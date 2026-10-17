import sqlite3

conn = sqlite3.connect('data/journal.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT match, selection, prob_fair, odds_offered, bookmaker, ev, kelly_stake_pct, kickoff, created_at 
    FROM recommendations 
    WHERE bookmaker != 'Score Officiel' AND odds_offered > 1.01
    ORDER BY id ASC
""")
rows = cur.fetchall()
print('Real pre-match recommendations logged in DB:', len(rows))
unique_matches = set(r['match'] for r in rows)
print('Distinct matches:', len(unique_matches))
for r in rows[-5:]:
    m = r['match']
    s = r['selection']
    p = r['prob_fair']
    pr = r['odds_offered']
    b = r['bookmaker']
    ev = r['ev']
    t = r['created_at'][:16]
    print(f"  {m} | {s} | {p:.1%} @ {pr} ({b}) | EV: {ev:+.1%} | {t}")
