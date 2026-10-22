import numpy as np
import time
from .team_ratings import parse_empirical_match_data, fetch_summaries_batch

def simulate_basketball_match(match_data, summary_d=None, num_simulations=5000, fetch_missing=True):
    """
    RotoBot-Grade 100% Empirical Monte Carlo Engine (Zero Fallback):
    1. Extracts real historical regular-time (4Q, OT-stripped) match scores from Nesine ApiStats v3.
    2. Applies Venue-Split (Home/Away), Same-League, and Standings weighting.
    3. Runs 5,000 deterministic Monte Carlo simulations using empirical team variance.
    4. Applies Empirical Bayes shrinkage & Outlier Quarantine (>22 pt divergence guard).
    """
    start_time = time.time()
    code = match_data.get("code", 0)
    nesine_line = float(match_data.get("line_total", 160.5))
    over_odds = float(match_data.get("odds_total_over", 1.85))
    under_odds = float(match_data.get("odds_total_under", 1.85))

    if summary_d is None and code and fetch_missing:
        batch = fetch_summaries_batch([code])
        summary_d = batch.get(int(code))

    emp = parse_empirical_match_data(code, summary_d)
    if not emp:
        return {
            "verified": False,
            "status": "NO_DATA",
            "num_simulations": 0,
            "elapsed_seconds": round(time.time() - start_time, 3),
            "pace": None,
            "home_win_prob": 0.5,
            "away_win_prob": 0.5,
            "projected_home_score": None,
            "projected_away_score": None,
            "projected_total": None,
            "raw_empirical_total": None,
            "nesine_line": nesine_line,
            "prob_over": 0.5,
            "prob_under": 0.5,
            "odds_over": over_odds,
            "odds_under": under_odds,
            "ev_over_pct": 0.0,
            "ev_under_pct": 0.0,
            "recommendation": "VERİ YOK — ANALİZ DIŞI",
            "rec_side": None,
            "best_ev": 0.0,
            "empirical_meta": None
        }

    h = emp["home"]
    a = emp["away"]

    # Category and League Awareness
    cat = (match_data.get("category") or "").upper()
    is_nba = bool(match_data.get("is_nba") or (cat == "NBA") or (nesine_line >= 215.0))
    is_wnba = bool(match_data.get("is_wnba") or (cat == "WNBA"))

    # Raw empirical expectation from real historical matches (Home Court Advantage +1.2 / -1.2)
    raw_home = (h["pf"] + a["pa"]) / 2.0 + 1.2
    raw_away = (a["pf"] + h["pa"]) / 2.0 - 1.2
    raw_total = raw_home + raw_away

    # Benchmark calibration & Small-Sample / Pre-season Exhibition Guard
    if is_nba:
        benchmark_total = 228.5
        total_samples = h["n"] + a["n"]
        if total_samples < 16:
            # Pre-season exhibition contamination protection: anchor prior to both market line and 228.5 benchmark
            prior_total = 0.65 * nesine_line + 0.35 * benchmark_total
            sample_confidence = min(0.60, 0.35 + total_samples / 50.0)
        else:
            prior_total = nesine_line
            sample_confidence = min(0.75, 0.55 + total_samples / 100.0)
    elif is_wnba:
        benchmark_total = 154.5
        prior_total = nesine_line
        sample_confidence = min(0.75, 0.55 + (h["n"] + a["n"]) / 100.0)
    else:
        prior_total = nesine_line
        sample_confidence = min(0.75, 0.55 + (h["n"] + a["n"]) / 100.0)

    adj_total = sample_confidence * raw_total + (1.0 - sample_confidence) * prior_total
    scale_ratio = adj_total / raw_total if raw_total > 0 else 1.0

    mu_home = raw_home * scale_ratio
    mu_away = raw_away * scale_ratio

    # Empirical team game-to-game standard deviation with realistic basketball floor
    min_team_sd = 9.8 if nesine_line >= 210 else 8.2
    sigma_home = max(min_team_sd, float(np.sqrt((h["std_pf"] ** 2 + a["std_pa"] ** 2) / 2.0)))
    sigma_away = max(min_team_sd, float(np.sqrt((a["std_pf"] ** 2 + h["std_pa"] ** 2) / 2.0)))

    # Deterministic RNG seeded by match code + line so simulations are 100% reproducible
    seed_val = int(code) + int(round(nesine_line * 10))
    rng = np.random.default_rng(seed_val)

    # Estimated Pace & Asymmetric High-Tempo Positive Right Tail
    est_pace = round((raw_total / 2.24) if is_nba else (raw_total / 2.18), 1)
    if is_nba:
        is_high_tempo = bool(est_pace >= 102.0 or nesine_line >= 238.0)
    else:
        is_high_tempo = bool(est_pace >= 79.0 or (est_pace >= 77.0 and nesine_line >= 174.0))

    # Correlated pace shock (with positive right-tail skew for explosive shootouts)
    if is_high_tempo:
        base_shock = rng.normal(0.0, 3.0, num_simulations)
        tempo_skew = rng.exponential(1.5, num_simulations) - 1.5
        shared_tempo_shock = base_shock + tempo_skew
    else:
        shared_tempo_shock = rng.normal(0.0, 3.2, num_simulations)
    home_scores = rng.normal(mu_home, sigma_home, num_simulations) + shared_tempo_shock
    away_scores = rng.normal(mu_away, sigma_away, num_simulations) + shared_tempo_shock
    total_scores = home_scores + away_scores

    home_wins = np.sum(home_scores > away_scores)
    home_win_prob = float(home_wins / num_simulations)
    away_win_prob = 1.0 - home_win_prob

    proj_home = round(float(np.mean(home_scores)), 1)
    proj_away = round(float(np.mean(away_scores)), 1)
    proj_total = round(float(np.median(total_scores)), 1)

    # Evaluate across open MTID 149 lines (or main line) using De-Vigged Fair Market Probability
    alt_totals = match_data.get("alt_totals") or [{"line": nesine_line, "under": under_odds, "over": over_odds}]
    best_line = nesine_line
    best_over_odds = over_odds
    best_under_odds = under_odds

    over_count = np.sum(total_scores > nesine_line)
    under_count = num_simulations - over_count
    prob_over = round(float(over_count / num_simulations), 3)
    prob_under = round(float(under_count / num_simulations), 3)

    # De-vigged Fair Probability Edge for main line (accounts for Nesine's 1.61/1.61 margin)
    imp_over = 1.0 / over_odds
    imp_under = 1.0 / under_odds
    imp_sum = imp_over + imp_under
    fair_prob_over = imp_over / imp_sum
    fair_prob_under = imp_under / imp_sum

    ev_over = round((prob_over - fair_prob_over) * 100.0, 1)
    ev_under = round((prob_under - fair_prob_under) * 100.0, 1)

    # Also check alternate lines with higher payout odds (1.65 - 1.92) if they yield superior edge
    for alt in alt_totals:
        l_val = alt["line"]
        o_ov = alt["over"]
        o_un = alt["under"]
        if o_ov < 1.55 or o_un < 1.55:
            continue
        p_ov = float(np.sum(total_scores > l_val) / num_simulations)
        p_un = 1.0 - p_ov
        f_ov = (1.0 / o_ov) / ((1.0 / o_ov) + (1.0 / o_un))
        f_un = 1.0 - f_ov
        edge_ov = round((p_ov - f_ov) * 100.0, 1)
        edge_un = round((p_un - f_un) * 100.0, 1)
        if o_ov >= 1.65 and edge_ov > ev_over and p_ov >= 0.55:
            best_line = l_val
            best_over_odds = o_ov
            best_under_odds = o_un
            prob_over = round(p_ov, 3)
            prob_under = round(p_un, 3)
            ev_over = edge_ov
            ev_under = edge_un
        elif o_un >= 1.65 and edge_un > ev_under and p_un >= 0.55:
            best_line = l_val
            best_over_odds = o_ov
            best_under_odds = o_un
            prob_over = round(p_ov, 3)
            prob_under = round(p_un, 3)
            ev_over = edge_ov
            ev_under = edge_un

    nesine_line = best_line
    over_odds = best_over_odds
    under_odds = best_under_odds

    recommendation = "PAS"
    rec_ev = 0.0
    rec_side = None
    coupon_grade = "PASS"

    # Outlier Quarantine Guard: if raw historical average differs from market line by > 22 pts
    is_quarantined = abs(raw_total - nesine_line) > 22.0

    # Pace Guard: in explosive high-tempo games, prevent blind ALT bets unless strong edge
    pace_guard_active = False
    if is_high_tempo and (prob_under > prob_over):
        if prob_under < 0.58 or ev_under < 7.5:
            pace_guard_active = True

    if is_quarantined:
        recommendation = "BAREM SAPMASI (PAS)"
    elif pace_guard_active:
        recommendation = "YÜKSEK TEMPO RİSKİ (PAS)"
    elif ev_over >= 4.5 and prob_over >= 0.55 and ev_over > ev_under:
        recommendation = f"ÜST {nesine_line}"
        rec_ev = ev_over
        rec_side = "OVER"
        coupon_grade = "DIAMOND" if (prob_over >= 0.58 and ev_over >= 7.5) else "VALUE"
    elif ev_under >= 4.5 and prob_under >= 0.55 and ev_under > ev_over:
        recommendation = f"ALT {nesine_line}"
        rec_ev = ev_under
        rec_side = "UNDER"
        coupon_grade = "DIAMOND" if (prob_under >= 0.58 and ev_under >= 7.5) else "VALUE"

    elapsed = round(time.time() - start_time, 3)

    return {
        "verified": True,
        "status": "QUARANTINED" if is_quarantined else ("PACE_GUARD" if pace_guard_active else "VERIFIED"),
        "num_simulations": num_simulations,
        "elapsed_seconds": elapsed,
        "pace": est_pace,
        "is_high_tempo": is_high_tempo,
        "coupon_grade": coupon_grade,
        "home_win_prob": round(home_win_prob, 3),
        "away_win_prob": round(away_win_prob, 3),
        "projected_home_score": proj_home,
        "projected_away_score": proj_away,
        "projected_total": proj_total,
        "raw_empirical_total": round(raw_total, 1),
        "nesine_line": nesine_line,
        "prob_over": prob_over,
        "prob_under": prob_under,
        "odds_over": over_odds,
        "odds_under": under_odds,
        "ev_over_pct": ev_over,
        "ev_under_pct": ev_under,
        "recommendation": recommendation,
        "rec_side": rec_side,
        "best_ev": rec_ev,
        "empirical_meta": {
            "home_n": h["n"],
            "away_n": a["n"],
            "home_pf": h["pf"],
            "home_pa": h["pa"],
            "away_pf": a["pf"],
            "away_pa": a["pa"],
            "home_recent": h["recent"][:3],
            "away_recent": a["recent"][:3],
            "ot_stripped": h["ot_stripped"] + a["ot_stripped"]
        }
    }
