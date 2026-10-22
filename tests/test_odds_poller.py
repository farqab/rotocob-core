import pytest

from backend import odds_store
from backend.odds_poller import build_markets, next_delay, poll_once, run_forever


def _parsed(code=1, game_date="22.10.2026 20:00", **overrides):
    m = {
        "code": code, "home_team": "A", "away_team": "B", "league": "NBA",
        "game_date": game_date, "line_total": 170.5, "total_mtid": 226,
        "odds_total_over": 1.9, "odds_total_under": 1.9,
        "alt_totals": [{"line": 170.5, "over": 1.9, "under": 1.9},   # duplicates main: skipped
                       {"line": 175.5, "over": 2.1, "under": 1.7}],
        "odds_ms_home": 1.6, "odds_ms_away": 2.3, "ms_mtid": 142,
    }
    m.update(overrides)
    return m


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "odds.db")
    odds_store.init_db(path)
    c = odds_store.connect(path)
    yield c
    c.close()


def test_build_markets_dedupes_main_line_and_includes_moneyline():
    # Main total is market 149, so the alt 170.5 on market 149 is the same barem: skipped.
    markets = build_markets(_parsed(total_mtid=149))
    kinds = [(m["market_type"], m["mtid"], m["line"], m["is_main"]) for m in markets]
    assert kinds == [
        ("TOTAL", 149, 170.5, 1),
        ("TOTAL", 149, 175.5, 0),
        ("MONEYLINE", 142, None, 1),
    ]


def test_build_markets_keeps_same_line_from_a_different_market_id():
    # Main total on market 226 and an alt on market 149 at the same line are kept separately:
    # they are different Nesine markets and may carry different odds.
    markets = build_markets(_parsed(total_mtid=226))
    assert ("TOTAL", 149, 170.5, 0) in [(m["market_type"], m["mtid"], m["line"], m["is_main"]) for m in markets]


def test_build_markets_skips_missing_odds():
    markets = build_markets(_parsed(odds_total_over=None, alt_totals=[], odds_ms_home=None))
    assert markets == []


def test_next_delay_normal_then_capped_backoff():
    assert next_delay(0, interval=150, backoff_base=30, backoff_cap=900) == 150
    assert next_delay(1, interval=150, backoff_base=30, backoff_cap=900) == 30
    assert next_delay(2, interval=150, backoff_base=30, backoff_cap=900) == 60
    assert next_delay(3, interval=150, backoff_base=30, backoff_cap=900) == 120
    assert next_delay(20, interval=150, backoff_base=30, backoff_cap=900) == 900


def test_poll_once_archives_and_is_idempotent(conn):
    fetch = lambda: [_parsed(total_mtid=149)]
    first = poll_once(conn, fetch, now=1000.0)
    assert first["matches"] == 1
    assert first["odds_rows"] == 3  # main total + one alt total + moneyline
    second = poll_once(conn, fetch, now=1150.0)
    assert second["odds_rows"] == 0  # delta filter: nothing changed
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1


def test_poll_once_counts_unparseable_times_without_writing(conn):
    stats = poll_once(conn, lambda: [_parsed(game_date="???")], now=1.0)
    assert stats["unparsed_time"] == 1
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0] == 0


def test_run_forever_backs_off_on_failure_and_recovers(conn):
    calls = {"n": 0}
    sleeps = []

    def flaky_fetch():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ConnectionError("CDN down")
        return [_parsed()]

    run_forever(conn, flaky_fetch, interval=150, backoff_base=30, backoff_cap=900,
                sleep=sleeps.append, max_iterations=4)
    assert sleeps == [30, 60, 150, 150]  # two failures back off, then normal interval resumes
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1


def test_predict_hook_records_prediction_once(conn):
    pred = {"market_type": "TOTAL", "mtid": 226, "selected_line": 170.5, "selected_side": "OVER",
            "odds_at_prediction": 1.9, "model_prob": 0.58, "edge_pct": 6.0, "ev_roi_pct": 10.2}
    stats1 = poll_once(conn, lambda: [_parsed()], predict=lambda m: pred, now=1.0)
    stats2 = poll_once(conn, lambda: [_parsed()], predict=lambda m: pred, now=2.0)
    assert stats1["predictions"] == 1
    assert stats2["predictions"] == 0
