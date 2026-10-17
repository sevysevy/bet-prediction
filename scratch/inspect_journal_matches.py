import sqlite3

conn = sqlite3.connect('data/journal.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT DISTINCT match, MIN(created_at) as min_ca, MAX(created_at) as max_ca FROM recommendations WHERE bookmaker != 'Score Officiel' GROUP BY match ORDER BY max_ca DESC LIMIT 40")
for r in cur.fetchall():
    print(f"{r['match']} (from {r['min_ca'][:16]} to {r['max_ca'][:16]})")
