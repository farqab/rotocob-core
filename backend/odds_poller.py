"""
Polling logic for the odds archive. The CLI wrapper lives in scripts/odds_poller.py.

Kept separate from the web app on purpose: running a poller inside uvicorn would start one
poller per worker, each writing the same rows and each calling Nesine.
"""
import logging
import time

from . import odds_store

log = logging.getLogger("odds_poller")

ALT_TOTAL_MTID = 149


def build_markets(match):
    """Turn one parsed bulletin match into the market rows to archive."""
    markets = []
    main_line = match.get("line_total")
    main_mtid = match.get("total_mtid")
    seen = set()
    if main_line is not None and match.get("odds_total_over") and match.get("odds_total_under"):
        markets.append({
            "market_type": "TOTAL", "mtid": main_mtid, "is_main": 1,
            "line": float(main_line),
            "over_odds": float(match["odds_total_over"]),
            "under_odds": float(match["odds_total_under"]),
        })
        seen.add((main_mtid, float(main_line)))

    for alt in match.get("alt_totals") or []:
        key = (ALT_TOTAL_MTID, float(alt["line"]))
        if key in seen:
            continue  # the main line already covers this barem
        seen.add(key)
        markets.append({
            "market_type": "TOTAL", "mtid": ALT_TOTAL_MTID, "is_main": 0,
            "line": float(alt["line"]),
            "over_odds": float(alt["over"]),
            "under_odds": float(alt["under"]),
        })

    if match.get("odds_ms_home") and match.get("odds_ms_away"):
        markets.append({
            "market_type": "MONEYLINE", "mtid": match.get("ms_mtid"), "is_main": 1,
            "line": None,
            "home_odds": float(match["odds_ms_home"]),
            "away_odds": float(match["odds_ms_away"]),
        })
    return markets


def poll_once(conn, fetch, predict=None, now=None):
    """
    Fetch the bulletin once and archive it. `fetch` returns a list of parsed matches;
    `predict` (optional) maps a match to a prediction dict or None.
    Returns counters for logging and tests.
    """
    now = time.time() if now is None else now
    stats = {"matches": 0, "unparsed_time": 0, "odds_rows": 0, "predictions": 0}
    matches = fetch()
    with conn:
        for m in matches:
            if not odds_store.upsert_match(conn, m, now):
                stats["unparsed_time"] += 1
                continue
            stats["matches"] += 1
            stats["odds_rows"] += odds_store.record_markets(conn, m["code"], build_markets(m), now)
            if predict is not None:
                pred = predict(m)
                if pred and odds_store.record_prediction_if_changed(conn, m["code"], pred, now):
                    stats["predictions"] += 1
    return stats


def next_delay(failures, interval, backoff_base, backoff_cap):
    """Normal interval after a success; exponential backoff (capped) after consecutive failures."""
    if failures <= 0:
        return interval
    return min(backoff_cap, backoff_base * (2 ** (failures - 1)))


def run_forever(conn, fetch, predict=None, interval=150, backoff_base=30, backoff_cap=900,
                sleep=time.sleep, max_iterations=None):
    failures = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            stats = poll_once(conn, fetch, predict=predict)
            failures = 0
            log.info("poll ok: %s", stats)
        except Exception:  # network, TLS, parse errors: log and back off, never crash the loop
            failures += 1
            log.exception("poll failed (consecutive failures: %d)", failures)
        sleep(next_delay(failures, interval, backoff_base, backoff_cap))
