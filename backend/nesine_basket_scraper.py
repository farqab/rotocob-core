import urllib.request
import json
import ssl
import re

NESINE_BULLETIN_URL = "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"
NESINE_AUTH = "Basic RDQ3MDc4RDMtNjcwQi00OUJBLTgxNUYtM0IyMjI2MTM1MTZCOkI4MzJCQjZGLTQwMjgtNDIwNS05NjFELTg1N0QxRTZEOTk0OA=="

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Authorization': NESINE_AUTH,
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nesine.com',
    'Referer': 'https://www.nesine.com/'
}

def fetch_live_nesine_basketball():
    """
    Fetches the full pre-match basketball bulletin directly from Nesine CDN.
    Accurately categorizes WNBA (40m Women), NBA (48m Men), and European basketball (40m).
    """
    req = urllib.request.Request(NESINE_BULLETIN_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        data = resp.read().decode('utf-8')
        js = json.loads(data)

    sg = js.get("sg", {})
    ea = sg.get("EA", [])
    la = {l['LID']: l['N'] for l in sg.get("LA", [])}

    raw_bball = [e for e in ea if e.get("TYPE") == 2]
    parsed_matches = []

    for m in raw_bball:
        code = m.get("C")
        date_str = m.get("D", "")
        time_str = m.get("T", "")
        home_team = m.get("HN", "").strip()
        away_team = m.get("AN", "").strip()
        league_id = m.get("LC")
        league_name = la.get(league_id, "Uluslararası Basketbol")
        mbs = m.get("EMBS") or m.get("MBS", 1)
        
        # Rigorous Category Disambiguation (NEVER confuse WNBA with Men's NBA)
        lg_lower = league_name.lower()
        h_lower = home_team.lower()
        a_lower = away_team.lower()

        is_wnba = (
            "wnba" in lg_lower or 
            "(k)" in h_lower or "(k)" in a_lower or 
            "kadın" in lg_lower or "women" in lg_lower or
            "valkyries" in h_lower or "valkyries" in a_lower
        )
        is_nba = not is_wnba and bool(re.search(r'\bnba\b', lg_lower))

        if is_wnba:
            base_pace = 73.5
            expected_total = 154.5
            category = "WNBA"
        elif is_nba:
            base_pace = 100.0
            expected_total = 228.0
            category = "NBA"
        elif "euroleague" in lg_lower:
            base_pace = 72.8
            expected_total = 165.0
            category = "EUROLEAGUE"
        else:
            base_pace = 73.0
            expected_total = 162.0
            category = "EUROPE"

        # Parse markets from MA — select the TRUE balanced main line (minimum |odds_under - odds_over|)
        best_total_line = None
        best_total_over_odds = None
        best_total_under_odds = None
        best_odds_diff = 999.0
        alt_totals = []
        
        match_winner_home_odds = None
        match_winner_away_odds = None

        for mk in m.get("MA", []):
            mtid = mk.get("MTID")
            sov = mk.get("SOV", 0.0)
            oca = mk.get("OCA", [])

            # Match Winner (Maç Sonucu 1/2) - MTID 142 or MTID 1
            if mtid in (142, 1) and len(oca) >= 2:
                match_winner_home_odds = oca[0].get("O")
                match_winner_away_odds = oca[1].get("O")

            # Main Total Points Over/Under (Maç Toplam Sayı Alt/Üst) - MTID 149 or MTID 226
            if mtid in (149, 226) and len(oca) >= 2 and sov and sov > 80:
                o_under = None
                o_over = None
                for oc in oca:
                    if oc.get("N") == 1:
                        o_under = oc.get("O")
                    elif oc.get("N") == 2:
                        o_over = oc.get("O")
                if o_under and o_over:
                    if mtid == 149:
                        alt_totals.append({
                            "line": float(sov),
                            "under": float(o_under),
                            "over": float(o_over)
                        })
                    diff = abs(float(o_under) - float(o_over))
                    # Prefer MTID 149 and most balanced odds
                    penalty = 0.0 if mtid == 149 else 0.15
                    if (diff + penalty) < best_odds_diff:
                        best_odds_diff = diff + penalty
                        best_total_line = float(sov)
                        best_total_under_odds = float(o_under)
                        best_total_over_odds = float(o_over)

        if best_total_line is None:
            continue

        match_data = {
            "id": f"nesine_{code}",
            "code": code,
            "home_team": home_team,
            "away_team": away_team,
            "league": league_name,
            "category": category,
            "is_nba": is_nba,
            "is_wnba": is_wnba,
            "game_date": f"{date_str} {time_str}",
            "mbs": mbs,
            "mbs_warning": f"⚠️ MBS {mbs} — En az {mbs} maçlık kombine zorunlu" if mbs > 1 else "✅ MBS 1 — Tek Maç Oynanabilir",
            "pace": base_pace,
            "line_total": best_total_line,
            "odds_total_over": best_total_over_odds,
            "odds_total_under": best_total_under_odds,
            "alt_totals": alt_totals,
            "odds_ms_home": match_winner_home_odds,
            "odds_ms_away": match_winner_away_odds,
            "markets_count": len(m.get("MA", []))
        }
        parsed_matches.append(match_data)

    return parsed_matches

if __name__ == "__main__":
    matches = fetch_live_nesine_basketball()
    print(f"Toplam {len(matches)} maç çekildi.")
    wnba_sample = [m for m in matches if m["is_wnba"]][:2]
    for w in wnba_sample:
        print(f"WNBA Match: {w['home_team']} vs {w['away_team']} | Barem: {w['line_total']} (Pace: {w['pace']})")
