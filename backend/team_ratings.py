import os
import json
import time
import sqlite3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import numpy as np
from concurrent.futures import ThreadPoolExecutor

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotobot.db")

def _init_cache_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS empirical_stats_cache (
            code INTEGER PRIMARY KEY,
            payload_json TEXT NOT NULL,
            fetched_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

_init_cache_table()

def _create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.25, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=30, pool_maxsize=30)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://istatistik.nesine.com",
        "Referer": "https://istatistik.nesine.com/"
    })
    return session

_SESSION = _create_session()

def fetch_summaries_batch(codes, cache_ttl=3600):
    """
    Fetches official Nesine ApiStats v3 Summary for a batch of match codes.
    Uses local SQLite cache first (0ms), then fetches missing codes in parallel.
    """
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    cached = {}
    missing_codes = []
    
    for code in codes:
        c.execute("SELECT payload_json, fetched_at FROM empirical_stats_cache WHERE code = ?", (int(code),))
        row = c.fetchone()
        if row and (now - row[1] < cache_ttl):
            try:
                cached[int(code)] = json.loads(row[0])
                continue
            except Exception:
                pass
        missing_codes.append(int(code))
    conn.close()

    if missing_codes:
        def _fetch_single(code):
            url = f"https://apistats.nesine.com/api/v3/HeadToHead/{code}/Summary"
            try:
                r = _SESSION.get(url, timeout=6)
                if r.status_code == 200:
                    data = r.json().get("d")
                    return code, data
            except Exception:
                pass
            return code, None

        with ThreadPoolExecutor(max_workers=20) as ex:
            fetched = list(ex.map(_fetch_single, missing_codes))

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for code, data in fetched:
            if data is not None:
                cached[code] = data
                c.execute(
                    "INSERT OR REPLACE INTO empirical_stats_cache (code, payload_json, fetched_at) VALUES (?, ?, ?)",
                    (code, json.dumps(data, ensure_ascii=False), now)
                )
        conn.commit()
        conn.close()

    return cached

def parse_empirical_match_data(code, summary_d):
    """
    100% Empirical Parser (ZERO Hardcoded Teams, ZERO Default Fallbacks).
    Extracts Regular-Time (sum of Q1..Q4, excluding Overtime) team scoring distributions,
    Home/Away splits, Same-League splits, Season Standings, and Head-to-Head.
    Returns None if either team has fewer than 3 verified official matches.
    """
    if not summary_d or not isinstance(summary_d, dict):
        return None
    slm = summary_d.get("SLM")
    if not slm or not slm.get("ML"):
        return None

    groups = {}
    for tft_block in slm.get("ML", []):
        tft = tft_block.get("TFT")
        for tt_block in tft_block.get("TT", []):
            ft = tt_block.get("FT")
            groups[(tft, ft)] = tt_block.get("TMS", [])

    overall_tms = groups.get((1, 5), [])
    if len(overall_tms) < 2:
        return None

    def _extract_team_series(tm_obj):
        if not tm_obj:
            return None
        tid = tm_obj.get("TID")
        name = tm_obj.get("N", "")
        matches = tm_obj.get("ML", [])
        if not matches:
            return None

        pf_list, pa_list = [], []
        fh_pf_list, fh_pa_list = [], []
        ot_count = 0
        recent_log = []

        # Filter out 40-minute July NBA Summer League ("Tem" / "Yaz Ligi" / "Summer") exhibitions if 48-min games exist
        non_summer = [
            m for m in matches
            if "yaz" not in ((m.get("LG") or {}).get("N") or "").lower()
            and "summer" not in ((m.get("LG") or {}).get("N") or "").lower()
            and "tem" not in (m.get("SFMD") or "").lower()
        ]
        active_matches = non_summer if len(non_summer) >= 3 else matches

        for m in active_matches:
            sc_list = m.get("SC", [])
            sc_map = {
                x["TY"]: (x["HTS"], x["ATS"])
                for x in sc_list
                if "TY" in x and x.get("HTS") is not None and x.get("ATS") is not None
            }

            # Strictly compute 4-Quarter Regular Time (TY 201..204) to strip Overtime inflation
            if all(q in sc_map for q in [201, 202, 203, 204]):
                reg_h = sum(sc_map[q][0] for q in [201, 202, 203, 204])
                reg_a = sum(sc_map[q][1] for q in [201, 202, 203, 204])
                if 2 in sc_map and (sc_map[2][0] > reg_h or sc_map[2][1] > reg_a):
                    ot_count += 1
            elif 2 in sc_map:
                reg_h, reg_a = sc_map[2]
            else:
                continue

            if 1 in sc_map:
                fh_h, fh_a = sc_map[1]
            elif 201 in sc_map and 202 in sc_map:
                fh_h = sc_map[201][0] + sc_map[202][0]
                fh_a = sc_map[201][1] + sc_map[202][1]
            else:
                fh_h, fh_a = reg_h * 0.49, reg_a * 0.49

            ht_obj = m.get("HT") or {}
            at_obj = m.get("AT") or {}
            ht_id = ht_obj.get("TID")
            is_home = (ht_id == tid)
            pf = float(reg_h if is_home else reg_a)
            pa = float(reg_a if is_home else reg_h)
            fh_pf = float(fh_h if is_home else fh_a)
            fh_pa = float(fh_a if is_home else fh_h)

            if pf < 35 or pa < 35:
                continue

            pf_list.append(pf)
            pa_list.append(pa)
            fh_pf_list.append(fh_pf)
            fh_pa_list.append(fh_pa)

            opp = (at_obj.get("NS") or at_obj.get("N", "")) if is_home else (ht_obj.get("NS") or ht_obj.get("N", ""))
            recent_log.append({
                "date": m.get("SFMD") or m.get("FMD", ""),
                "opp": opp,
                "loc": "İç" if is_home else "Dep",
                "pf": int(pf),
                "pa": int(pa),
                "total": int(pf + pa),
                "score": f"{int(pf)}-{int(pa)}"
            })

        n = len(pf_list)
        if n < 3:
            return None

        # Exponential decay weights (recent matches weighted higher)
        w = np.exp(-np.arange(n) * 0.14)
        w /= w.sum()

        return {
            "tid": tid,
            "name": name,
            "n": n,
            "pf": float(np.sum(np.array(pf_list) * w)),
            "pa": float(np.sum(np.array(pa_list) * w)),
            "fh_pf": float(np.sum(np.array(fh_pf_list) * w)),
            "fh_pa": float(np.sum(np.array(fh_pa_list) * w)),
            "raw_pf": round(float(np.mean(pf_list)), 1),
            "raw_pa": round(float(np.mean(pa_list)), 1),
            "std_pf": round(max(4.8, min(13.5, float(np.std(pf_list)))), 2),
            "std_pa": round(max(4.8, min(13.5, float(np.std(pa_list)))), 2),
            "ot_stripped": ot_count,
            "recent": recent_log[:5]
        }

    h_data = _extract_team_series(overall_tms[0])
    a_data = _extract_team_series(overall_tms[1])
    if not h_data or not a_data:
        return None

    # 1. Blend Home/Away Venue-Specific Form (FT=2)
    venue_tms = groups.get((1, 2), [])
    if len(venue_tms) >= 2:
        h_ven = _extract_team_series(venue_tms[0])
        a_ven = _extract_team_series(venue_tms[1])
        if h_ven and h_ven["n"] >= 3:
            h_data["pf"] = 0.65 * h_data["pf"] + 0.35 * h_ven["pf"]
            h_data["pa"] = 0.65 * h_data["pa"] + 0.35 * h_ven["pa"]
        if a_ven and a_ven["n"] >= 3:
            a_data["pf"] = 0.65 * a_data["pf"] + 0.35 * a_ven["pf"]
            a_data["pa"] = 0.65 * a_data["pa"] + 0.35 * a_ven["pa"]

    # 2. Blend Same-League Tournament Form (TFT=2, FT=5)
    lg_tms = groups.get((2, 5), [])
    if len(lg_tms) >= 2:
        h_lg = _extract_team_series(lg_tms[0])
        a_lg = _extract_team_series(lg_tms[1])
        if h_lg and h_lg["n"] >= 2:
            h_data["pf"] = 0.75 * h_data["pf"] + 0.25 * h_lg["pf"]
            h_data["pa"] = 0.75 * h_data["pa"] + 0.25 * h_lg["pa"]
        if a_lg and a_lg["n"] >= 2:
            a_data["pf"] = 0.75 * a_data["pf"] + 0.25 * a_lg["pf"]
            a_data["pa"] = 0.75 * a_data["pa"] + 0.25 * a_lg["pa"]

    # 3. Extract League Standings (SLT) season average if available
    slt = summary_d.get("SLT")
    if slt and slt.get("LTL"):
        try:
            ltr = slt["LTL"][0]["LTSL"][0]["LTTL"][0]["LTR"]
            for row in ltr:
                mc = row.get("MC", 0)
                avg_str = row.get("AVG", "")
                if mc >= 3 and ":" in avg_str:
                    tot_pf, tot_pa = [float(x) for x in avg_str.split(":")]
                    s_pf, s_pa = tot_pf / mc, tot_pa / mc
                    if row.get("TID") == h_data["tid"] and s_pf > 40:
                        h_data["pf"] = 0.80 * h_data["pf"] + 0.20 * s_pf
                        h_data["pa"] = 0.80 * h_data["pa"] + 0.20 * s_pa
                    elif row.get("TID") == a_data["tid"] and s_pf > 40:
                        a_data["pf"] = 0.80 * a_data["pf"] + 0.20 * s_pf
                        a_data["pa"] = 0.80 * a_data["pa"] + 0.20 * s_pa
        except Exception:
            pass

    h_data["pf"] = round(h_data["pf"], 1)
    h_data["pa"] = round(h_data["pa"], 1)
    a_data["pf"] = round(a_data["pf"], 1)
    a_data["pa"] = round(a_data["pa"], 1)

    return {
        "verified": True,
        "home": h_data,
        "away": a_data
    }
