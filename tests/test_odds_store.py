import sqlite3
from datetime import datetime

import pytest

from backend import odds_store
from backend.odds_store import (
    closing_line, connect, init_db, parse_match_time,
    record_markets, record_prediction_if_changed, upsert_match,
)


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "odds.db")
    init_db(path)
    conn = connect(path)
    yield conn
    conn.close()


def _match(code=1, game_date="22.10.2026 20:00", home="A", away="B"):
    return {"code": code, "game_date": game_date, "home_team": home, "away_team": away, "league": "NBA"}


def _total(line=170.5, over=1.9, under=1.9, mtid=149, is_main=1):
    return {"market_type": "TOTAL", "mtid": mtid, "is_main": is_main, "line": line,
            "over_odds": over, "under_odds": under}


def test_init_creates_tables_and_wal(tmp_path):
    path = str(tmp_path / "odds.db")
    init_db(path)
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"matches", "odds_history", "predictions"} <= names
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.close()


def test_foreign_key_rejects_unknown_match(db):
    with pytest.raises(sqlite3.IntegrityError):
        record_markets(db, 999, [_total()], now=1.0)
        db.commit()


def test_parse_match_time_is_turkey_local():
    from datetime import timezone

    local_text, utc = parse_match_time("22.10.2026 20:00")
    assert local_text == "22.10.2026 20:00"
    # 20:00 at UTC+3 is 17:00 UTC
    assert utc == datetime(2026, 10, 22, 17, 0, 0, tzinfo=timezone.utc).timestamp()


def test_parse_match_time_rejects_unknown_format():
    assert parse_match_time("tomorrow evening") is None


def test_upsert_keeps_first_seen_and_updates_last_seen(db):
    upsert_match(db, _match(), now=100.0)
    upsert_match(db, _match(), now=400.0)
    db.commit()
    row = db.execute("SELECT first_seen_at, last_seen_at FROM matches WHERE match_code=1").fetchone()
    assert row["first_seen_at"] == 100.0
    assert row["last_seen_at"] == 400.0


def test_upsert_skips_unparseable_time(db):
    assert upsert_match(db, _match(game_date="bilinmiyor"), now=1.0) is False


def test_delta_filter_skips_unchanged_odds(db):
    upsert_match(db, _match(), now=1.0)
    assert record_markets(db, 1, [_total()], now=1.0) == 1
    assert record_markets(db, 1, [_total()], now=2.0) == 0
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0] == 1


def test_delta_filter_records_changed_odds(db):
    upsert_match(db, _match(), now=1.0)
    record_markets(db, 1, [_total(over=1.9)], now=1.0)
    assert record_markets(db, 1, [_total(over=1.85)], now=2.0) == 1
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0] == 2


def test_different_lines_are_separate_markets(db):
    upsert_match(db, _match(), now=1.0)
    n = record_markets(db, 1, [_total(line=170.5), _total(line=171.5, is_main=0)], now=1.0)
    assert n == 2


def test_closing_line_is_last_row_before_start(db):
    tip = parse_match_time("22.10.2026 20:00")[1]
    upsert_match(db, _match(), now=tip - 3600)
    record_markets(db, 1, [_total(line=170.5, over=1.9)], now=tip - 3600)
    record_markets(db, 1, [_total(line=171.5, over=1.8)], now=tip - 60)
    record_markets(db, 1, [_total(line=172.5, over=1.7)], now=tip + 120)  # after the start: ignored
    db.commit()
    cl = closing_line(db, 1, mtid=149)
    assert cl["line"] == 171.5
    assert cl["over_odds"] == 1.8


def test_closing_line_confidence_reflects_how_recently_match_was_seen(db):
    tip = parse_match_time("22.10.2026 20:00")[1]
    upsert_match(db, _match(), now=tip - 120)          # seen 2 minutes before start
    record_markets(db, 1, [_total()], now=tip - 120)
    db.commit()
    assert closing_line(db, 1, mtid=149)["confidence"] == "high"

    upsert_match(db, _match(code=2, game_date="22.10.2026 20:00"), now=tip - 2 * 3600)
    record_markets(db, 2, [_total()], now=tip - 2 * 3600)
    db.commit()
    assert closing_line(db, 2, mtid=149)["confidence"] == "low"


def test_closing_line_none_when_no_odds_before_start(db):
    upsert_match(db, _match(), now=1.0)
    db.commit()
    assert closing_line(db, 1, mtid=149) is None


def test_prediction_logged_only_on_change(db):
    upsert_match(db, _match(), now=1.0)
    pred = {"market_type": "TOTAL", "mtid": 149, "selected_line": 170.5, "selected_side": "OVER",
            "odds_at_prediction": 1.9, "model_prob": 0.58, "edge_pct": 6.0, "ev_roi_pct": 10.2}
    assert record_prediction_if_changed(db, 1, pred, now=1.0) is True
    assert record_prediction_if_changed(db, 1, pred, now=2.0) is False
    changed = dict(pred, odds_at_prediction=1.95)
    assert record_prediction_if_changed(db, 1, changed, now=3.0) is True
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 2
