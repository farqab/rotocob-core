import numpy as np

def calculate_ev(model_prob, odds):
    """
    Calculates Expected Value percentage:
    EV% = (Model Probability * Decimal Odds - 1.0) * 100
    """
    ev = (model_prob * odds - 1.0) * 100.0
    return round(ev, 2)

def calculate_kelly_stake(model_prob, odds, bankroll=1000.0, fractional_kelly=0.25):
    """
    Quarter-Kelly Criterion for bankroll risk management.
    b = odds - 1
    f* = (b * p - q) / b
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    p = model_prob
    q = 1.0 - p
    f_star = (b * p - q) / b
    if f_star <= 0:
        return 0.0
    recommended_pct = f_star * fractional_kelly
    return round(bankroll * recommended_pct, 2)

def evaluate_prop_bet(projected_median, line, over_odds, under_odds, stat_std=4.5):
    """
    Calculates empirical probability of Over vs Under using normal CDF approximation.
    """
    from scipy.stats import norm
    
    # Probability of Over (X > line)
    # Continuity correction line + 0.5 for discrete NBA stats
    z = (line - projected_median) / stat_std
    under_prob = norm.cdf(z)
    over_prob = 1.0 - under_prob
    
    ev_over = calculate_ev(over_prob, over_odds)
    ev_under = calculate_ev(under_prob, under_odds)
    
    recommendation = "PASS"
    best_ev = max(ev_over, ev_under)
    
    if best_ev > 5.0: # Minimum 5% Edge threshold
        recommendation = "OVER" if ev_over > ev_under else "UNDER"
        
    return {
        "projected_median": round(float(projected_median), 1),
        "line": line,
        "over_prob": round(float(over_prob), 3),
        "under_prob": round(float(under_prob), 3),
        "ev_over_pct": ev_over,
        "ev_under_pct": ev_under,
        "recommendation": recommendation,
        "recommended_stake": calculate_kelly_stake(over_prob if recommendation == "OVER" else under_prob,
                                                   over_odds if recommendation == "OVER" else under_odds)
    }
