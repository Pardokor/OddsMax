#!/usr/bin/env python3
"""
Backend scraper pour Betclic, Winamax et ParionsSport
Lance avec : python backend.py
Écoute sur http://localhost:5000
"""

from flask import Flask, jsonify
from flask_cors import CORS
import requests
import json
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Autorise les appels depuis le site HTML

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'fr-FR,fr;q=0.9',
}

# ─── WINAMAX ────────────────────────────────────────────────────────────────

WINAMAX_SPORT_IDS = {
    'ligue1':       '/sports/football/competitions/96',
    'premier':      '/sports/football/competitions/7',
    'laliga':       '/sports/football/competitions/8',
    'seriea':       '/sports/football/competitions/9',
    'bundesliga':   '/sports/football/competitions/6',
    'champions':    '/sports/football/competitions/2',
}

def fetch_winamax(competition_path):
    url = f'https://www.winamax.fr/paris-sportifs{competition_path}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        # Winamax injecte les cotes dans le HTML en JSON
        match = re.search(r'PRELOADED_STATE\s*=\s*({.+?});\s*</script>', r.text, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(1))
        
        matches = []
        events = data.get('sportbook', {}).get('events', {})
        markets = data.get('sportbook', {}).get('markets', {})
        odds_data = data.get('sportbook', {}).get('odds', {})
        
        for event_id, event in events.items():
            if event.get('type') != 'MATCH':
                continue
            
            home = event.get('homeTeamName', '')
            away = event.get('awayTeamName', '')
            start = event.get('startAt', 0)
            
            # Trouver le marché 1X2
            h2h = None
            for market_id in event.get('mainMarketId', []):
                mkt = markets.get(str(market_id), {})
                if '1X2' in mkt.get('marketType', '') or mkt.get('label', '').startswith('Résultat'):
                    h2h = mkt
                    break
            if not h2h:
                continue
            
            bet_ids = h2h.get('odds', [])
            if len(bet_ids) < 2:
                continue
            
            result = {'home': home, 'away': away, 'start': start,
                      'home_odd': None, 'draw_odd': None, 'away_odd': None}
            
            for i, bet_id in enumerate(bet_ids):
                price = odds_data.get(str(bet_id), {}).get('odds')
                if price:
                    if i == 0: result['home_odd'] = price
                    elif i == 1: result['draw_odd'] = price
                    elif i == 2: result['away_odd'] = price
            
            matches.append(result)
        
        return matches
    except Exception as e:
        print(f'Winamax error: {e}')
        return []

# ─── BETCLIC ─────────────────────────────────────────────────────────────────

BETCLIC_SPORT_IDS = {
    'ligue1':     'https://www.betclic.fr/football-s1/ligue-1-c4',
    'premier':    'https://www.betclic.fr/football-s1/premier-league-c3',
    'laliga':     'https://www.betclic.fr/football-s1/la-liga-c6',
    'seriea':     'https://www.betclic.fr/football-s1/serie-a-c5',
    'bundesliga': 'https://www.betclic.fr/football-s1/bundesliga-c7',
    'champions':  'https://www.betclic.fr/football-s1/ligue-des-champions-c2',
}

def fetch_betclic(url):
    try:
        api_url = url.replace('betclic.fr/', 'betclic.fr/api/sport/') + '?includeOutrights=false'
        r = requests.get(api_url, headers={**HEADERS, 'Accept': 'application/json'}, timeout=10)
        data = r.json()
        
        matches = []
        for event in data.get('events', []):
            if event.get('type') != 'match':
                continue
            home = event.get('homeCompetitor', {}).get('name', '')
            away = event.get('awayCompetitor', {}).get('name', '')
            start = event.get('startAt', '')
            
            home_odd = draw_odd = away_odd = None
            for market in event.get('markets', []):
                if market.get('type') == 'threeway':
                    for sel in market.get('selections', []):
                        t = sel.get('type', '')
                        p = sel.get('odds')
                        if t == '1': home_odd = p
                        elif t == 'X': draw_odd = p
                        elif t == '2': away_odd = p
                    break
            
            if home_odd:
                matches.append({'home': home, 'away': away, 'start': start,
                                 'home_odd': home_odd, 'draw_odd': draw_odd, 'away_odd': away_odd})
        return matches
    except Exception as e:
        print(f'Betclic error: {e}')
        return []

# ─── PARIONS SPORT ──────────────────────────────────────────────────────────

PARIONS_COMPETITION_IDS = {
    'ligue1':     4,
    'premier':    3,
    'laliga':     6,
    'seriea':     5,
    'bundesliga': 7,
    'champions':  2,
}

def fetch_parionssport(comp_id):
    try:
        url = f'https://www.parionssport.fdj.fr/api/v2/events?competition={comp_id}&status=OPEN&count=50'
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        
        matches = []
        for event in data.get('events', []):
            home = event.get('homeTeam', {}).get('name', '')
            away = event.get('awayTeam', {}).get('name', '')
            start = event.get('startDate', '')
            
            home_odd = draw_odd = away_odd = None
            for market in event.get('marketGroups', [{}])[0].get('markets', []):
                if '1X2' in market.get('name', '') or market.get('type') == 'RESULT':
                    for sel in market.get('selections', []):
                        label = sel.get('label', '')
                        p = sel.get('odds')
                        if label == '1': home_odd = p
                        elif label == 'N': draw_odd = p
                        elif label == '2': away_odd = p
                    break
            
            if home_odd:
                matches.append({'home': home, 'away': away, 'start': start,
                                 'home_odd': home_odd, 'draw_odd': draw_odd, 'away_odd': away_odd})
        return matches
    except Exception as e:
        print(f'ParionsSport error: {e}')
        return []

# ─── ROUTES ──────────────────────────────────────────────────────────────────

SPORT_MAP = {
    'soccer_france_ligue_one':      'ligue1',
    'soccer_epl':                   'premier',
    'soccer_spain_la_liga':         'laliga',
    'soccer_italy_serie_a':         'seriea',
    'soccer_germany_bundesliga':    'bundesliga',
    'soccer_uefa_champs_league':    'champions',
}

@app.route('/odds/<sport_key>')
def get_odds(sport_key):
    comp = SPORT_MAP.get(sport_key, 'ligue1')
    
    result = {
        'winamax': fetch_winamax(WINAMAX_SPORT_IDS[comp]),
        'betclic': fetch_betclic(BETCLIC_SPORT_IDS[comp]),
        'parionssport': fetch_parionssport(PARIONS_COMPETITION_IDS[comp]),
    }
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    print('\n🚀 Backend OddsMax démarré sur http://localhost:5000')
    print('📡 Endpoints disponibles :')
    print('   GET /odds/soccer_france_ligue_one')
    print('   GET /odds/soccer_epl')
    print('   GET /odds/soccer_spain_la_liga')
    print('   GET /health\n')
    app.run(port=5000, debug=False)
