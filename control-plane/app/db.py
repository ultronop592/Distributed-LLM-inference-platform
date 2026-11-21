import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.getenv("GATEWAY_DB", "gateway.db")


@contextmanager
def session():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with session() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                prefix TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id INTEGER NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )


def insert_key(name, key_hash, prefix):
    with session() as conn:
        cursor = conn.execute(
            "INSERT INTO api_keys (name, key_hash, prefix, created_at) VALUES (?, ?, ?, ?)",
            (name, key_hash, prefix, int(time.time())),
        )
        return cursor.lastrowid


def get_active_by_hash(key_hash):
    with session() as conn:
        return conn.execute(
            "SELECT id, name FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()


def list_keys():
    with session() as conn:
        rows = conn.execute(
            "SELECT id, name, prefix, created_at, revoked_at FROM api_keys ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def revoke_key(key_id):
    with session() as conn:
        cursor = conn.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (int(time.time()), key_id),
        )
        return cursor.rowcount > 0


def record_usage(key_id, prompt_tokens, completion_tokens):
    with session() as conn:
        conn.execute(
            "INSERT INTO usage (key_id, prompt_tokens, completion_tokens, created_at) VALUES (?, ?, ?, ?)",
            (key_id, prompt_tokens, completion_tokens, int(time.time())),
        )


def usage_summary():
    with session() as conn:
        rows = conn.execute(
            """
            SELECT k.id, k.name, k.prefix,
                   COUNT(u.id) AS requests,
                   COALESCE(SUM(u.prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(u.completion_tokens), 0) AS completion_tokens
            FROM api_keys k
            LEFT JOIN usage u ON u.key_id = k.id
            GROUP BY k.id
            ORDER BY k.id
            """
        ).fetchall()
        return [dict(row) for row in rows]