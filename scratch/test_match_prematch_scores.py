import sqlite3
import re
from src.feeds import KEYS, get
from src.build_site import collect_scores, norm_team_key, evaluate_outcome

def test():
    theodds_key = KEYS.get('theoddsapi')
    scores_map = collect_scores(theodds_key)
    print(f"Total scores in map: {len(scores_map)}")
    
    conn = sqlite3.connect('data/journal.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT match, selection, prob_fair, odds_offered, bookmaker, ev, kickoff, created_at FROM recommendations WHERE bookmaker != 'Score Officiel' ORDER BY id DESC")
    all_recs = cur.fetchall()
    
    # Map by (norm(home), norm(away))
    prematch_by_match = {}
    for r in all_recs:
        parts = r['match'].split(' - ')
        if len(parts) >= 2:
            h = norm_team_key(parts[0])
            a = norm_team_key(parts[1])
            key = (h, a)
            if key not in prematch_by_match:
                prematch_by_match[key] = []
            prematch_by_match[key].append(dict(r))
            
    print(f"Matches in journal: {len(prematch_by_match)}")
    
    # Check completed matches
    matched_completed = 0
    for (h, a), sc in scores_map.items():
        if not sc.get('completed'):
            continue
        recs = prematch_by_match.get((h, a)) or prematch_by_match.get((a, h))
        if recs:
            matched_completed += 1
            hs = sc.get('home_score')
            as_ = sc.get('away_score')
            print(f"\nMatch: {sc.get('home_team')} {hs} - {as_} {sc.get('away_team')} (Terminé)")
            # Unique selections
            seen_sels = set()
            for r in recs:
                s = r['selection']
                if s not in seen_sels:
                    seen_sels.add(s)
                    outcome = evaluate_outcome('1X2', s, sc.get('home_team'), sc.get('away_team'), hs, as_)
                    print(f"  Prono: {s} | Chance: {r['prob_fair']:.1%} | Cote: {r['odds_offered']} ({r['bookmaker']}) | EV: {r['ev']:+.1%} -> {outcome}")
                    
    print(f"\nTotal completed matches matched with real pre-match bets: {matched_completed}")

if __name__ == '__main__':
    test()
