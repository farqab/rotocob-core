-- RotoBot-Core SQLite Database Schema
-- Provides 1:1 drop-in replacement for RotoBot Supabase tables

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    game_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    pace REAL DEFAULT 100.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    team TEXT NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    minutes_projected REAL DEFAULT 30.0,
    usg_pct REAL DEFAULT 0.20,
    ts_pct REAL DEFAULT 0.55,
    reb_rate REAL DEFAULT 0.10,
    ast_rate REAL DEFAULT 0.15,
    tov_rate REAL DEFAULT 0.10,
    status TEXT DEFAULT 'ACTIVE',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_props (
    id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    game_id TEXT NOT NULL,
    market_type TEXT NOT NULL, -- 'Points', 'Rebounds', 'Assists', 'PRA', 'Threes'
    line REAL NOT NULL,
    over_odds REAL NOT NULL,
    under_odds REAL NOT NULL,
    bookmaker TEXT NOT NULL, -- 'Nesine', 'Pinnacle', 'DraftKings'
    projected_median REAL,
    model_over_prob REAL,
    model_under_prob REAL,
    ev_over_pct REAL,
    ev_under_pct REAL,
    recommendation TEXT, -- 'OVER', 'UNDER', 'PASS'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(player_id) REFERENCES players(id),
    FOREIGN KEY(game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    num_simulations INTEGER DEFAULT 5000,
    home_win_prob REAL,
    away_win_prob REAL,
    projected_home_score REAL,
    projected_away_score REAL,
    projected_total REAL,
    spread REAL,
    detailed_json TEXT, -- Full score distributions & player medians
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS chat_threads (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT 'New Analysis',
    mode TEXT DEFAULT 'betting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    data_payload TEXT, -- JSON artifacts/simulations
    liked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
);
