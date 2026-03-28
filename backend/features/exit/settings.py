import sqlite3, json

DB = "settings.db"

DEFAULT = {
    "action_thresholds": {
        "EXIT": 70,
        "TRIM": 50,
        "WATCH": 30
    },
    "function_scores": {
        "loss_severity": [5, 10, 18, 25],
        "risk_vs_median": [8, 14, 20],
        "risk_adj_inefficiency": [8, 14, 20],
        "trend_weakness": [10, 20],
        "concentration": [5, 10, 15]
    }
}

def _ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS exit_settings (id INTEGER PRIMARY KEY, config TEXT)")

def get_settings():
    conn = sqlite3.connect(DB)
    _ensure_table(conn)
    row = conn.execute("SELECT config FROM exit_settings WHERE id=1").fetchone()
    conn.close()
    return json.loads(row[0]) if row else DEFAULT

def save_settings(config: dict):
    conn = sqlite3.connect(DB)
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO exit_settings (id, config) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET config = excluded.config",
        (json.dumps(config),)
    )
    conn.commit()
    conn.close()

def reset_settings():
    conn = sqlite3.connect(DB)
    _ensure_table(conn)
    conn.execute("DELETE FROM exit_settings WHERE id=1")
    conn.commit()
    conn.close()
    return DEFAULT
