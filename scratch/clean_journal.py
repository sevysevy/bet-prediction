import sqlite3

conn = sqlite3.connect('data/journal.db')
with conn:
    res = conn.execute("DELETE FROM recommendations WHERE bookmaker = 'Score Officiel'")
    print(f"Purged {res.rowcount} fake Score Officiel rows from journal.db")

total = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
print(f"Remaining clean rows: {total}")
conn.close()
