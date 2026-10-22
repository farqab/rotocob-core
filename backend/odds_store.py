"""
Odds archive and prediction log, kept in its own SQLite file (odds_history.db).

Kept separate from rotobot.db (which is tracked in git) so that frequent writes from the
poller do not produce binary diffs, and so that WAL mode can let the poller write while
backtests read at the same time.
"""
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(ROOT, "odds_history.db")

# Turkey has used a fixed UTC+03:00 offset since 2016 (no DST), so a fixed offset is exact.
TURKEY_TZ = timezone(timedelta(hours=3))

# Confidence thresholds for the closing line, in seconds between the last poll that saw
# the match and its scheduled start.
CLOSING_HIGH_SECONDS = 5 * 60
CLOSING_MEDIUM_SECONDS = 30 * 60

DDL = """
CREATE TABLE IF NOT EXISTS matches (
    match_code INTEGER PRIMARY KEY,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    league TEXT,
    match_time_local TEXT NOT NULL,
    match_time_utc REAL NOT NULL,
    first_seen_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS odds_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookmaker TEXT NOT NULL DEFAULT 'Nesine',
    match_code INTEGER NOT NULL REFERENCES matches(match_code),
    market_type TEXT NOT NULL,            -- 'TOTAL' | 'MONEYLINE'
    mtid INTEGER,                         -- Nesine market id (149, 226, 142, 1, ...)
    is_main INTEGER NOT NULL DEFAULT 0,
    line REAL,                            -- TOTAL barem; NULL for MONEYLINE
    over_odds REAL,
    under_odds REAL,
    home_odds REAL,                       -- MONEYLINE
    away_odds REAL,
    recorded_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_odds_lookup
    ON odds_history (match_code, market_type, mtid, line, recorded_at);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_code INTEGER NOT NULL REFERENCES matches(match_code),
    market_type TEXT NOT NULL,
    mtid INTEGER,
    selected_line REAL,
    selected_side TEXT NOT NULL,          -- 'OVER' | 'UNDER' | 'MS1' | 'MS2'
    odds_at_prediction REAL NOT NULL,
    model_prob REAL NOT NULL,
    edge_pct REAL NOT NULL,
    ev_roi_pct REAL NOT NULL,
    recorded_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predictions_lookup
    ON predictions (match_code, market_type, recorded_at);
"""


def connect(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path=DEFAULT_DB_PATH):
    conn = connect(path)
    try:
        conn.executescript(DDL)
        conn.commit()
    finally:
        conn.close()


_TIME_FORMATS = ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


def parse_match_time(text):
    """
    Parse a Nesine start time (local Turkish time) into (local_text, utc_epoch).
    Returns None if the format is not recognised; such matches are skipped, not guessed.
    """
    for fmt in _TIME_FORMATS:
        try:
            local = datetime.strptime(text.strip(), fmt).replace(tzinfo=TURKEY_TZ)
        except (ValueError, AttributeError):
            continue
        return text.strip(), local.timestamp()
    return None


def upsert_match(conn, m, now=None):
    """Insert or refresh a match. Returns False if its start time cannot be parsed."""
    now = time.time() if now is None else now
    parsed = parse_match_time(m.get("game_date") or "")
    if parsed is None:
        return False
    local_text, utc_epoch = parsed
    conn.execute(
        """
        INSERT INTO matches (match_code, home_team, away_team, league,
                             match_time_local, match_time_utc, first_seen_at, last_seen_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
        ON CONFLICT(match_code) DO UPDATE SET
            home_team = excluded.home_team,
            away_team = excluded.away_team,
            league = excluded.league,
            match_time_local = excluded.match_time_local,
            match_time_utc = excluded.match_time_utc,
            last_seen_at = excluded.last_seen_at
        """,
        (int(m["code"]), m.get("home_team", ""), m.get("away_team", ""), m.get("league"),
         local_text, utc_epoch, now, now),
    )
    return True


def _round(value):
    return None if value is None else round(float(value), 4)


def record_markets(conn, match_code, markets, now=None):
    """
    Write one row per market whose odds changed since its last recorded row (delta filter).
    Returns the number of rows inserted.
    """
    now = time.time() if now is None else now
    inserted = 0
    for mk in markets:
        new = (_round(mk.get("over_odds")), _round(mk.get("under_odds")),
               _round(mk.get("home_odds")), _round(mk.get("away_odds")))
        last = conn.execute(
            """
            SELECT over_odds, under_odds, home_odds, away_odds FROM odds_history
            WHERE match_code = ? AND market_type = ? AND mtid IS ? AND line IS ?
            ORDER BY recorded_at DESC, id DESC LIMIT 1
            """,
            (int(match_code), mk["market_type"], mk.get("mtid"), mk.get("line")),
        ).fetchone()
        if last is not None and tuple(_round(x) for x in last) == new:
            continue
        conn.execute(
            """
            INSERT INTO odds_history (match_code, market_type, mtid, is_main, line,
                                      over_odds, under_odds, home_odds, away_odds, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (int(match_code), mk["market_type"], mk.get("mtid"), int(bool(mk.get("is_main"))),
             mk.get("line"), new[0], new[1], new[2], new[3], now),
        )
        inserted += 1
    return inserted


def record_prediction_if_changed(conn, match_code, pred, now=None):
    """Log a recommendation unless the same side, line and odds were already logged last."""
    now = time.time() if now is None else now
    last = conn.execute(
        """
        SELECT selected_side, selected_line, odds_at_prediction FROM predictions
        WHERE match_code = ? AND market_type = ?
        ORDER BY recorded_at DESC, id DESC LIMIT 1
        """,
        (int(match_code), pred["market_type"]),
    ).fetchone()
    current = (pred["selected_side"], pred.get("selected_line"), _round(pred["odds_at_prediction"]))
    if last is not None and (last[0], last[1], _round(last[2])) == current:
        return False
    conn.execute(
        """
        INSERT INTO predictions (match_code, market_type, mtid, selected_line, selected_side,
                                 odds_at_prediction, model_prob, edge_pct, ev_roi_pct, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (int(match_code), pred["market_type"], pred.get("mtid"), pred.get("selected_line"),
         pred["selected_side"], pred["odds_at_prediction"], pred["model_prob"],
         pred["edge_pct"], pred["ev_roi_pct"], now),
    )
    return True


def closing_line(conn, match_code, mtid=None):
    """
    The last main-line TOTAL recorded before the match started, plus how fresh our view of
    the match was. Derived on demand; nothing is stored as a flag.
    Returns None if the match is unknown or no odds were recorded before its start.
    """
    match = conn.execute(
        "SELECT match_time_utc, last_seen_at FROM matches WHERE match_code = ?",
        (int(match_code),),
    ).fetchone()
    if match is None:
        return None
    row = conn.execute(
        """
        SELECT line, over_odds, under_odds, recorded_at FROM odds_history
        WHERE match_code = ? AND market_type = 'TOTAL' AND is_main = 1
          AND mtid IS ? AND recorded_at <= ?
        ORDER BY recorded_at DESC, id DESC LIMIT 1
        """,
        (int(match_code), mtid, match["match_time_utc"]),
    ).fetchone()
    if row is None:
        return None
    unseen = match["match_time_utc"] - match["last_seen_at"]
    if unseen <= CLOSING_HIGH_SECONDS:
        confidence = "high"
    elif unseen <= CLOSING_MEDIUM_SECONDS:
        confidence = "medium"
    else:
        confidence = "low"
    return {
        "match_code": int(match_code),
        "line": row["line"],
        "over_odds": row["over_odds"],
        "under_odds": row["under_odds"],
        "recorded_at": row["recorded_at"],
        "seconds_unseen_before_start": unseen,
        "confidence": confidence,
    }
