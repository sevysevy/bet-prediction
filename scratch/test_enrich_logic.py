import sqlite3
import datetime
from src.feeds import KEYS
from src.build_site import collect_scores, norm_team_key, evaluate_outcome
from leagues import resolve_league

def load_prematch_db(db_path='data/journal.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT match, kickoff, selection, prob_fair, odds_offered, bookmaker, 
               sharp_ref, sharp_margin, ev, kelly_stake_pct, league, event_id, created_at
        FROM recommendations
        WHERE bookmaker != 'Score Officiel'
        ORDER BY id DESC
    """)
    recs = cur.fetchall()
    conn.close()

    prematch_by_pair = {}
    for r in recs:
        parts = (r['match'] or '').split(' - ')
        if len(parts) >= 2:
            h = norm_team_key(parts[0])
            a = norm_team_key(parts[1])
            pair = (h, a)
            if pair not in prematch_by_pair:
                prematch_by_pair[pair] = {}
            sel = r['selection']
            if sel not in prematch_by_pair[pair]:
                prematch_by_pair[pair][sel] = dict(r)
    return prematch_by_pair

def test():
    theodds_key = KEYS.get('theoddsapi')
    scores_map = collect_scores(theodds_key)
    prematch_db = load_prematch_db()
    
    rows = []
    # Test completed matches from scores_map
    added_count = 0
    for (h, a), sc in scores_map.items():
        if not sc.get('completed'):
            continue
        pm_sels = prematch_db.get((h, a)) or prematch_db.get((a, h))
        if not pm_sels:
            continue
        hs = sc.get('home_score')
        as_ = sc.get('away_score')
        if hs is None or as_ is None:
            continue
        home_t = sc.get('home_team')
        away_t = sc.get('away_team')
        lg_info = resolve_league(sc.get('league'))
        
        for sel, pm in pm_sels.items():
            outcome = evaluate_outcome('1X2', sel, home_t, away_t, hs, as_)
            rows.append({
                'match': f"{home_t} - {away_t}",
                'sel': sel,
                'prob': pm['prob_fair'],
                'price': pm['odds_offered'],
                'book': pm['bookmaker'],
                'ev': pm['ev'],
                'status': 'FINISHED',
                'score_str': f"{hs} - {as_}",
                'outcome': outcome
            })
            added_count += 1
            
    print(f"Added {added_count} authentic pre-match selections for completed matches:")
    for r in rows:
        badge = "WON (Gagné)" if r['outcome'] == 'WON' else "LOST (Perdu)"
        print(f"  {r['match']} [{r['score_str']}] | {r['sel']} | {r['prob']:.1%} @ {r['price']} ({r['book']}) | EV: {r['ev']:+.1%} -> {badge}")

if __name__ == '__main__':
    test()
