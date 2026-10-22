"""
Archive Nesine basketball odds and the model's recommendations on a fixed interval.

Usage:
    python3 scripts/odds_poller.py                       # poll forever, every 150 s
    python3 scripts/odds_poller.py --interval 180 --db /path/to/odds_history.db
    python3 scripts/odds_poller.py --once                # single poll, then exit

Runs as its own process; it does not start with the web server.
"""
import argparse
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import odds_store  # noqa: E402
from backend.odds_poller import poll_once, run_forever  # noqa: E402
from backend.nesine_basket_scraper import fetch_live_nesine_basketball  # noqa: E402


def engine_prediction(match):
    """Model recommendation for one match, in the shape predictions expects (or None)."""
    from backend.simulation_engine import simulate_basketball_match

    sim = simulate_basketball_match(match, num_simulations=5000)
    if not sim.get("verified") or not sim.get("rec_side"):
        return None
    side = sim["rec_side"]
    line = sim["nesine_line"]
    main_line = match.get("line_total")
    mtid = match.get("total_mtid") if main_line is not None and float(line) == float(main_line) else 149
    return {
        "market_type": "TOTAL",
        "mtid": mtid,
        "selected_line": float(line),
        "selected_side": side,
        "odds_at_prediction": sim["odds_over"] if side == "OVER" else sim["odds_under"],
        "model_prob": sim["prob_over"] if side == "OVER" else sim["prob_under"],
        "edge_pct": sim["best_edge"],
        "ev_roi_pct": sim["best_ev_roi"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=odds_store.DEFAULT_DB_PATH, help="path to odds_history.db")
    parser.add_argument("--interval", type=float, default=150, help="seconds between polls")
    parser.add_argument("--backoff-base", type=float, default=30, help="first retry delay after a failure")
    parser.add_argument("--backoff-cap", type=float, default=900, help="maximum retry delay")
    parser.add_argument("--no-predictions", action="store_true", help="archive odds only")
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    odds_store.init_db(args.db)
    conn = odds_store.connect(args.db)
    predict = None if args.no_predictions else engine_prediction
    try:
        if args.once:
            print(poll_once(conn, fetch_live_nesine_basketball, predict=predict))
        else:
            run_forever(conn, fetch_live_nesine_basketball, predict=predict,
                        interval=args.interval, backoff_base=args.backoff_base,
                        backoff_cap=args.backoff_cap)
    except KeyboardInterrupt:
        logging.info("stopped")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
