import sqlite3
from src.build_site import norm_team_key, evaluate_outcome

def get_prematch_evaluations(db_path='data/journal.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # On récupère les vraies recommandations pré-match (pas les scores officiels)
    # Triées par id DESC pour avoir la dernière évaluation avant le coup d'envoi
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
                prematch_by_pair[pair] = []
            
            # Ne garder que la dernière évaluation pour chaque sélection distincte
            sel = r['selection']
            if not any(existing['selection'] == sel for existing in prematch_by_pair[pair]):
                prematch_by_pair[pair].append(dict(r))

    return prematch_by_pair

if __name__ == '__main__':
    evals = get_prematch_evaluations()
    print(f"Total distinct match pairs with pre-match evaluations: {len(evals)}")
    # Sample
    for pair, items in list(evals.items())[:5]:
        print(f"\nMatch: {items[0]['match']}")
        for it in items:
            print(f"  {it['selection']} | {it['prob_fair']:.1%} @ {it['odds_offered']} ({it['bookmaker']}) | EV: {it['ev']:+.1%}")
