import os
import sys
import json
import pytest

# Ensure the repo root is importable when running `pytest` from anywhere
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import backend.simulation_engine as engine
from backend.simulation_engine import simulate_basketball_match

DATA_PATH = os.path.join(ROOT, "data", "benchmark_matches.json")

# Benchmark features are stored rounded, so the rebuilt inputs differ slightly from the
# ones the stored outputs were produced with. These tolerances absorb that rounding.
TOTAL_TOL = 1.0
PROB_TOL = 0.02


def load_benchmarks():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _side_from_features(f):
    """Rebuild one team's parsed-empirical dict from the benchmark's stored features."""
    return {
        "n": f["sample_size"],
        "pf": f["points_scored_weighted"],
        "pa": f["points_allowed_weighted"],
        # Benchmark stores a single std; the engine uses separate PF/PA stds, so reuse it for both.
        "std_pf": f["std_scoring"],
        "std_pa": f["std_scoring"],
        "recent": f.get("recent_regular_time_games", []),
        "ot_stripped": 0,
        "tid": None,
        "name": f.get("name", ""),
    }


def _engine_inputs(b):
    m = b["metadata"]
    match_data = {
        "code": m["code"],
        "line_total": m["market_line"],
        "odds_total_over": m["odds_over"],
        "odds_total_under": m["odds_under"],
    }
    empirical = {
        "home": _side_from_features(b["empirical_features"]["home"]),
        "away": _side_from_features(b["empirical_features"]["away"]),
    }
    return match_data, empirical


@pytest.fixture
def no_network(monkeypatch):
    """Make any accidental network call fail loudly, so the test proves it runs offline."""
    def _forbidden(*args, **kwargs):
        raise AssertionError("network call attempted during offline simulation")
    monkeypatch.setattr(engine, "fetch_summaries_batch", _forbidden)


def test_benchmark_data_integrity():
    benchmarks = load_benchmarks()
    assert len(benchmarks) >= 5, "Should have at least 5 benchmark matches"
    for b in benchmarks:
        assert "metadata" in b
        assert "empirical_features" in b
        assert "simulation_output" in b


@pytest.mark.parametrize("idx", range(8))
def test_engine_runs_offline_and_reproduces_benchmark(idx, no_network):
    b = load_benchmarks()[idx]
    stored = b["simulation_output"]
    match_data, empirical = _engine_inputs(b)

    result = simulate_basketball_match(match_data, empirical=empirical, num_simulations=5000)

    assert result["verified"] is True
    assert result["num_simulations"] == 5000
    assert abs(result["projected_total"] - stored["projected_total"]) <= TOTAL_TOL
    assert abs(result["prob_under"] - stored["prob_under"]) <= PROB_TOL
    assert abs(result["prob_over"] - stored["prob_over"]) <= PROB_TOL


@pytest.mark.parametrize("idx", range(8))
def test_probabilities_are_consistent(idx, no_network):
    b = load_benchmarks()[idx]
    match_data, empirical = _engine_inputs(b)
    result = simulate_basketball_match(match_data, empirical=empirical, num_simulations=5000)

    assert 0.0 <= result["prob_under"] <= 1.0
    assert 0.0 <= result["prob_over"] <= 1.0
    assert abs(result["prob_under"] + result["prob_over"] - 1.0) < 1e-6


@pytest.mark.xfail(
    strict=True,
    reason="Known issue: recommendation gating uses Edge (model vs de-vigged fair prob), "
           "not ROI at the actual payout odds, so some recommended bets have negative ROI.",
)
def test_recommended_bets_have_positive_roi(no_network):
    negative = []
    for b in load_benchmarks():
        match_data, empirical = _engine_inputs(b)
        result = simulate_basketball_match(match_data, empirical=empirical, num_simulations=5000)
        side = result["rec_side"]
        if side is None:
            continue
        roi = result["ev_roi_over_pct"] if side == "OVER" else result["ev_roi_under_pct"]
        if roi <= 0:
            negative.append((match_data["code"], side, roi))
    assert not negative, f"Recommended bets with non-positive ROI: {negative}"
