import os
import re
import sys
from src.feeds import KEYS, get, norm_theodds, norm_oddspapi, modele_commun, pick_sharp
from src.build_site import collect_oddspapi

def clean_team_name(name):
    s = name.lower()
    s = re.sub(r'\b(fc|cf|osc|rc|as|ac|ss|rb|fsv|sc|us|ogc|vfl|bvb)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def test():
    theodds_key = KEYS.get('theoddsapi')
    oddspapi_key = KEYS.get('oddspapi')
    print('Testing coupling...')
    
    # 1. Fetch top 5 leagues from TheOddsAPI
    top_leagues = ['soccer_epl', 'soccer_france_ligue_one', 'soccer_germany_bundesliga', 'soccer_spain_la_liga', 'soccer_italy_serie_a']
    theodds_raw = []
    for lg in top_leagues:
        try:
            data, _ = get(f'https://api.the-odds-api.com/v4/sports/{lg}/odds', {'apiKey': theodds_key, 'regions': 'eu', 'markets': 'h2h'})
            theodds_raw.extend(data)
        except Exception as e:
            print(f'{lg} err: {e}')
            
    theodds_events = norm_theodds(theodds_raw)
    print(f'TheOdds events: {len(theodds_events)}')
    
    # 2. Fetch OddsPapi
    oddspapi_events, _ = collect_oddspapi(oddspapi_key)
    print(f'OddsPapi events: {len(oddspapi_events)}')
    
    # 3. Build index of TheOdds matches by clean (home, away)
    theodds_index = {}
    for ev in theodds_events:
        h = clean_team_name(ev['home'])
        a = clean_team_name(ev['away'])
        theodds_index[(h, a)] = ev
        theodds_index[(a, h)] = ev

    # 4. Merge
    merged_count = 0
    all_events = []
    theodds_matched = set()

    for op_ev in oddspapi_events:
        h = clean_team_name(op_ev['home'])
        a = clean_team_name(op_ev['away'])
        matched = theodds_index.get((h, a))
        if matched and op_ev.get('market_type') == '1X2 (Résultat)':
            # Fusion des bookmakers pour le 1X2 !
            theodds_matched.add(matched['id'])
            merged_count += 1
            existing_book_names = {b['name'].lower() for b in op_ev['books']}
            for b in matched['books']:
                if b['name'].lower() not in existing_book_names:
                    op_ev['books'].append(b)
        all_events.append(op_ev)

    # Ajouter les events TheOdds qui n'étaient pas dans OddsPapi
    for to_ev in theodds_events:
        if to_ev['id'] not in theodds_matched:
            all_events.append(to_ev)

    print(f'Merged matches: {merged_count}')
    print(f'Total combined events: {len(all_events)}')

    rows = modele_commun(all_events)
    val_bets = [r for r in rows if r['ev'] > 0]
    print(f'Total selections: {len(rows)}')
    print(f'Positive EV selections (Value Bets): {len(val_bets)}')
    for v in val_bets[:5]:
        print(f"  [{v['league']}] {v['match']} -> {v['sel']} ({v['prob']:.1%}) @ {v['book']} {v['price']} | EV: {v['ev']:+.1%}")

if __name__ == '__main__':
    test()
