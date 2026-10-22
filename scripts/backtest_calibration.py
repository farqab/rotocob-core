"""
Walk-forward calibration and Brier-score backtest for the basketball total-points model.

Read-only: opens rotobot.db with mode=ro and writes nothing.

For every finished match (in date order) the script uses only earlier games for each team,
builds the engine's parsed-empirical input, and asks the engine for P(total > line) at
five synthetic lines around the team-based projection. Outcomes are then compared with the
predictions.

Limitations (see docs/CALIBRATION_REPORT.md):
- Lines are synthetic (projection +/- 8 points), not historical market lines.
- No historical odds are stored, so ROI cannot be backtested here.
- Venue / league / standings blending from team_ratings.py is not replicated.

Usage:  python3 scripts/backtest_calibration.py
"""
import collections
import datetime
import json
import math
import os
import re
import sqlite3
import sys
from math import erf, sqrt

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.simulation_engine import simulate_basketball_match  # noqa: E402

DB_PATH = os.path.join(ROOT, "rotobot.db")
WINDOW = 15                 # prior games used per team
MIN_HISTORY = 5             # minimum prior games per team
LINE_OFFSETS = [-8, -4, 0, 4, 8]
NUM_SIMULATIONS = 5000

TR_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
     "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])}


def parse_date(text):
    m = re.match(r"\s*(\d{1,2})\s+(\S+)\s+(\d{4})", text or "")
    if not m:
        return None
    month = TR_MONTHS.get(m.group(2))
    if not month:
        return None
    return datetime.date(int(m.group(3)), month, int(m.group(1)))


def regular_time_score(score_list):
    """Sum periods 201..204 (regular time, OT excluded). None if any period is missing."""
    sm = {x["TY"]: (x.get("HTS"), x.get("ATS")) for x in score_list if "TY" in x}
    periods = [201, 202, 203, 204]
    if not all(k in sm and sm[k][0] is not None and sm[k][1] is not None for k in periods):
        return None
    return sum(sm[k][0] for k in periods), sum(sm[k][1] for k in periods)


def load_matches():
    """Collect unique finished matches from the empirical_stats_cache table."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    seen = {}
    for (payload,) in con.execute("select payload_json from empirical_stats_cache"):
        data = json.loads(payload)
        for key in ("SLM", "SCH"):
            for ml in (data.get(key) or {}).get("ML", []) or []:
                for tt in ml.get("TT", []) or []:
                    for tm in tt.get("TMS", []) or []:
                        for m in tm.get("ML", []) or []:
                            mid = m.get("MID")
                            if mid is not None and mid not in seen:
                                seen[mid] = m
    con.close()

    rows = []
    for mid, m in seen.items():
        scores = regular_time_score(m.get("SC", []))
        date = parse_date(m.get("POFMD")) or parse_date(m.get("FMD"))
        if scores is None or date is None:
            continue
        league = (m.get("LG") or {}).get("N") or ""
        if "yaz" in league.lower() or "summer" in league.lower():
            continue  # exhibition leagues, as the engine already guards against
        home = (m.get("HT") or {}).get("TID")
        away = (m.get("AT") or {}).get("TID")
        rows.append({"mid": mid, "date": date.isoformat(), "home": home, "away": away,
                     "h": scores[0], "a": scores[1], "total": scores[0] + scores[1]})
    rows.sort(key=lambda r: (r["date"], r["mid"]))
    return rows


def team_empirical(history, tid, date):
    games = [g for g in history[tid] if g[0] < date][-WINDOW:]
    if len(games) < MIN_HISTORY:
        return None
    weights = np.exp(-np.arange(len(games))[::-1] * 0.14)
    weights /= weights.sum()
    pf = np.array([g[1] for g in games], dtype=float)
    pa = np.array([g[2] for g in games], dtype=float)
    return {
        "n": len(games),
        "pf": float(np.sum(pf * weights)),
        "pa": float(np.sum(pa * weights)),
        "std_pf": float(np.clip(np.std(pf), 4.8, 13.5)),
        "std_pa": float(np.clip(np.std(pa), 4.8, 13.5)),
        "recent": [], "ot_stripped": 0, "tid": tid, "name": "",
    }


def normal_cdf(z):
    return 0.5 * (1 + erf(z / sqrt(2)))


def run():
    rows = load_matches()
    history = collections.defaultdict(list)
    records = []  # (engine_prob_over, naive_prob_over, outcome, line)
    evaluated = 0

    for r in rows:
        h, a = r["home"], r["away"]
        if h is not None and a is not None:
            eh = team_empirical(history, h, r["date"])
            ea = team_empirical(history, a, r["date"])
            if eh and ea:
                raw_home = (eh["pf"] + ea["pa"]) / 2.0 + 1.2
                raw_away = (ea["pf"] + eh["pa"]) / 2.0 - 1.2
                raw_total = raw_home + raw_away
                sd_total = math.sqrt(eh["std_pf"] ** 2 + ea["std_pa"] ** 2
                                     + eh["std_pa"] ** 2 + ea["std_pf"] ** 2)
                base = round(raw_total)
                for k in LINE_OFFSETS:
                    line = base + k + 0.5
                    sim = simulate_basketball_match(
                        {"code": int(r["mid"]), "line_total": float(line),
                         "odds_total_over": 1.9, "odds_total_under": 1.9},
                        empirical={"home": eh, "away": ea},
                        num_simulations=NUM_SIMULATIONS)
                    if not sim.get("verified"):
                        continue
                    outcome = 1 if r["total"] > line else 0
                    naive = 1 - normal_cdf((line - raw_total) / sd_total)
                    records.append((sim["prob_over"], naive, outcome, line))
                evaluated += 1
        # Strict walk-forward: add this match to history only after predicting it
        if h is not None and a is not None:
            history[h].append((r["date"], r["h"], r["a"], r["mid"]))
            history[a].append((r["date"], r["a"], r["h"], r["mid"]))

    return rows, evaluated, records


def report(rows, evaluated, records):
    p = np.array([x[0] for x in records])
    naive = np.array([x[1] for x in records])
    y = np.array([x[2] for x in records])
    print(f"finished matches parsed: {len(rows)}")
    print(f"matches evaluated (walk-forward): {evaluated}")
    print(f"prediction records (match x line): {len(records)}")
    print(f"Brier engine:       {np.mean((p - y) ** 2):.4f}")
    print(f"Brier naive normal: {np.mean((naive - y) ** 2):.4f}")
    print(f"Brier constant 0.5: {np.mean((0.5 - y) ** 2):.4f}")
    print(f"base rate over: {y.mean():.3f}   mean engine prediction: {p.mean():.3f}")
    print("calibration (engine):")
    edges = np.linspace(0, 1, 11)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum():
            print(f"  [{lo:.1f},{hi:.1f})  n={m.sum():5d}  predicted={p[m].mean():.3f}  observed={y[m].mean():.3f}")


if __name__ == "__main__":
    report(*run())
