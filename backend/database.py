import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotobot.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "SCHEMA.sql")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[+] SQLite database initialized at: {DB_PATH}")

def seed_demo_data():
    conn = get_connection()
    c = conn.cursor()
    
    # Check if games already exist
    c.execute("SELECT COUNT(*) FROM games")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    # Seed Games
    games = [
        ("game_okc_sas_01", "Oklahoma City Thunder", "San Antonio Spurs", "2026-10-22 20:00:00", "scheduled", 0, 0, 102.5),
        ("game_bos_nyk_02", "Boston Celtics", "New York Knicks", "2026-10-22 19:30:00", "scheduled", 0, 0, 99.0),
        ("game_den_lal_03", "Denver Nuggets", "Los Angeles Lakers", "2026-10-22 22:00:00", "scheduled", 0, 0, 98.5)
    ]
    c.executemany("INSERT OR IGNORE INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", games)

    # Seed Key Players
    players = [
        ("p_sga", "OKC", "Shai Gilgeous-Alexander", "PG", 35.5, 0.32, 0.63, 0.08, 0.28, 0.09, "ACTIVE"),
        ("p_jdub", "OKC", "Jalen Williams", "SG", 33.0, 0.24, 0.58, 0.07, 0.22, 0.10, "ACTIVE"),
        ("p_chet", "OKC", "Chet Holmgren", "C", 31.0, 0.21, 0.62, 0.16, 0.12, 0.08, "ACTIVE"),
        ("p_wemby", "SAS", "Victor Wembanyama", "C", 34.0, 0.31, 0.59, 0.22, 0.19, 0.12, "ACTIVE"),
        ("p_cp3", "SAS", "Chris Paul", "PG", 28.0, 0.14, 0.54, 0.06, 0.35, 0.07, "ACTIVE"),
        ("p_vassell", "SAS", "Devin Vassell", "SG", 32.0, 0.23, 0.56, 0.07, 0.16, 0.08, "ACTIVE"),
        
        ("p_tatum", "BOS", "Jayson Tatum", "SF", 36.0, 0.30, 0.60, 0.13, 0.24, 0.09, "ACTIVE"),
        ("p_brown", "BOS", "Jaylen Brown", "SG", 34.0, 0.28, 0.57, 0.10, 0.18, 0.11, "ACTIVE"),
        ("p_brunson", "NYK", "Jalen Brunson", "PG", 36.0, 0.32, 0.59, 0.06, 0.32, 0.08, "ACTIVE"),
        ("p_kat", "NYK", "Karl-Anthony Towns", "C", 33.0, 0.25, 0.62, 0.19, 0.14, 0.11, "ACTIVE"),
        
        ("p_jokic", "DEN", "Nikola Jokic", "C", 35.5, 0.29, 0.65, 0.21, 0.42, 0.11, "ACTIVE"),
        ("p_murray", "DEN", "Jamal Murray", "PG", 33.0, 0.25, 0.57, 0.07, 0.26, 0.09, "ACTIVE"),
        ("p_lebron", "LAL", "LeBron James", "SF", 34.5, 0.27, 0.61, 0.12, 0.34, 0.12, "ACTIVE"),
        ("p_ad", "LAL", "Anthony Davis", "C", 35.0, 0.29, 0.62, 0.23, 0.15, 0.09, "ACTIVE")
    ]
    c.executemany("INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", players)

    # Seed Sample Props with Live Odds (+EV Calculations)
    props = [
        ("prop_01", "p_sga", "game_okc_sas_01", "Points", 30.5, 1.88, 1.92, "Nesine", 32.4, 0.585, 0.415, 10.0, -10.0, "OVER"),
        ("prop_02", "p_wemby", "game_okc_sas_01", "Rebounds", 11.5, 1.95, 1.85, "Nesine", 13.1, 0.624, 0.376, 21.7, -21.7, "OVER"),
        ("prop_03", "p_cp3", "game_okc_sas_01", "Assists", 7.5, 2.05, 1.76, "Nesine", 6.8, 0.410, 0.590, -15.9, 14.5, "UNDER"),
        ("prop_04", "p_tatum", "game_bos_nyk_02", "Points", 27.5, 1.90, 1.90, "Nesine", 28.9, 0.552, 0.448, 4.9, -4.9, "OVER"),
        ("prop_05", "p_jokic", "game_den_lal_03", "Assists", 9.5, 1.92, 1.88, "Nesine", 10.8, 0.610, 0.390, 17.1, -17.1, "OVER"),
        ("prop_06", "p_brunson", "game_bos_nyk_02", "Threes", 2.5, 2.10, 1.72, "Nesine", 2.9, 0.540, 0.460, 13.4, -13.4, "OVER")
    ]
    c.executemany("INSERT OR IGNORE INTO player_props VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", props)
    
    conn.commit()
    conn.close()
    print("[+] Seeded demo games, players, and +EV props.")

if __name__ == "__main__":
    init_db()
    seed_demo_data()
