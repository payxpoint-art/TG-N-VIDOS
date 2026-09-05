import sqlite3
import json
from contextlib import contextmanager

DB_PATH = "backup.db"

MAX_LOG_LINES = 100


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS backup_progress (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT,
            destination_id TEXT,
            destination_name TEXT,
            last_message_id INTEGER DEFAULT 0,
            total_videos INTEGER DEFAULT 0,
            total_photos INTEGER DEFAULT 0,
            total_files INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle',
            logs TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()


def get_progress(channel_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM backup_progress WHERE channel_id=?", (channel_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["logs"] = json.loads(result.get("logs") or "[]")
        except Exception:
            result["logs"] = []
        return result


def upsert_progress(channel_id, **fields):
    existing = get_progress(channel_id)
    with get_db() as conn:
        if existing:
            keys = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE backup_progress SET {keys} WHERE channel_id=?",
                (*fields.values(), channel_id)
            )
        else:
            cols = ", ".join(["channel_id"] + list(fields.keys()))
            qs = ", ".join(["?"] * (len(fields) + 1))
            conn.execute(
                f"INSERT INTO backup_progress ({cols}) VALUES ({qs})",
                (channel_id, *fields.values())
            )


def add_log(channel_id, message):
    progress = get_progress(channel_id) or {}
    logs = progress.get("logs", [])
    logs.append(message)
    if len(logs) > MAX_LOG_LINES:
        logs = logs[-MAX_LOG_LINES:]
    upsert_progress(channel_id, logs=json.dumps(logs))
