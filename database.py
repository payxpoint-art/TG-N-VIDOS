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
    # Ye table har successfully bheje gaye message ko permanently record karta
    # hai. Isse agar tool beech me restart ho jaye, dobara start karne par
    # wahi messages skip ho jayenge jo already bhej diye gaye the — chahe
    # 'last_message_id' checkpoint thoda peeche ho.
    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_messages (
            channel_id TEXT,
            message_id INTEGER,
            PRIMARY KEY (channel_id, message_id)
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


def is_already_sent(channel_id, message_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_messages WHERE channel_id=? AND message_id=?",
            (channel_id, message_id)
        ).fetchone()
        return row is not None


def mark_sent(channel_id, message_id):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_messages (channel_id, message_id) VALUES (?, ?)",
            (channel_id, message_id)
        )
