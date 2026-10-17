import datetime
import re
from src.feeds import KEYS, get
from src.build_site import norm_team_key

def test_scores():
    key = KEYS.get('theoddsapi')
    leagues = ['soccer_epl', 'soccer_france_ligue_one', 'soccer_germany_bundesliga', 'soccer_spain_la_liga', 'soccer_italy_serie_a']
    
    scores_map = {}
    for lg in leagues:
        try:
            data, _ = get(f'https://api.the-odds-api.com/v4/sports/{lg}/scores', {'apiKey': key, 'daysFrom': 2})
            for m in data:
                h = norm_team_key(m.get('home_team'))
                a = norm_team_key(m.get('away_team'))
                scores = m.get('scores') or []
                h_score, a_score = None, None
                for s in scores:
                    if norm_team_key(s.get('name')) == h:
                        h_score = int(s.get('score', 0))
                    elif norm_team_key(s.get('name')) == a:
                        a_score = int(s.get('score', 0))
                
                scores_map[(h, a)] = {
                    'completed': m.get('completed', False),
                    'home_team': m.get('home_team'),
                    'away_team': m.get('away_team'),
                    'home_score': h_score,
                    'away_score': a_score,
                    'last_update': m.get('last_update')
                }
        except Exception as e:
            print(f'{lg} err:', e)
            
    print(f'Total matches with score info: {len(scores_map)}')
    completed = [v for v in scores_map.values() if v['completed']]
    print(f'Completed matches: {len(completed)}')
    for c in completed[:5]:
        print(f"  {c['home_team']} {c['home_score']} - {c['away_score']} {c['away_team']} (Terminé)")
        
    live = [v for v in scores_map.values() if not v['completed'] and v['home_score'] is not None]
    print(f'Live matches: {len(live)}')
    for l in live[:5]:
        print(f"  {l['home_team']} {l['home_score']} - {l['away_score']} {l['away_team']} (En direct)")

if __name__ == '__main__':
    test_scores()
