import sqlite3
from src.feeds import KEYS
from src.build_site import collect_scores, norm_team_key

theodds_key = KEYS.get('theoddsapi')
scores_map = collect_scores(theodds_key)
print(f"Total in scores_map: {len(scores_map)}")

conn = sqlite3.connect('data/journal.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT DISTINCT match FROM recommendations WHERE bookmaker != 'Score Officiel'")
journal_matches = [r['match'] for r in cur.fetchall()]
print(f"Distinct journal matches: {len(journal_matches)}")

completed = [m for m, sc in scores_map.items() if sc.get('completed')]
print(f"Completed in scores_map: {len(completed)}")
for (h, a) in completed:
    sc = scores_map[(h, a)]
    home_name = sc.get('home_team')
    away_name = sc.get('away_team')
    
    # check if in journal_matches
    match_found = []
    for jm in journal_matches:
        parts = jm.split(' - ')
        if len(parts) >= 2:
            jh = norm_team_key(parts[0])
            ja = norm_team_key(parts[1])
            if (h == jh and a == ja) or (h in jh and a in ja) or (jh in h and ja in a):
                match_found.append(jm)
    print(f"Completed: {home_name} vs {away_name} -> found in journal: {match_found}")
