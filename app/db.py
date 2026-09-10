"""SQLite database initialization and connection management.

One generic `records` table serves every collection (programs/vials/logs/
settings/labs/genome) instead of a table per collection — the client already
sends complete, self-contained JSON objects and does all cross-referencing
(programId/vialId) itself, so there's nothing relational for the server to
model. This also makes "delete a user and everything they own" a single
`DELETE FROM records WHERE user_email=?` instead of a hand-maintained list of
tables that has to be remembered every time a new collection appears
client-side.

DB path/connection pattern mirrors ClaudeCode/tcg-tracker's app/db.py: a
fresh aiosqlite connection per request, closed in a `finally`, WAL mode, no
connection pool.
"""
import os
from pathlib import Path

import aiosqlite

DATA_DIR = Path(os.environ.get("HEALTHME_DATA_DIR", "/dbdata"))
DB_PATH = DATA_DIR / "health-me.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email       TEXT PRIMARY KEY,
    is_admin    INTEGER DEFAULT 0,
    is_disabled INTEGER DEFAULT 0,
    display_name TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- collection: 'programs'|'vials'|'logs'|'settings'|'labs'|'genome' — see
-- ALLOWED_COLLECTIONS in routes/api_data.py, the server-side allowlist that
-- keeps this schema-free table from being an open key-value store for any
-- authenticated user. 'settings' and 'genome' each only ever have one row,
-- id 'main' — same convention the client already uses for settings.
CREATE TABLE IF NOT EXISTS records (
    user_email  TEXT NOT NULL,
    collection  TEXT NOT NULL,
    id          TEXT NOT NULL,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_email, collection, id)
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_records_user_col ON records(user_email, collection);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def _ensure_column(db, table: str, column: str, ddl: str) -> None:
    """Add a column to an already-existing table if it isn't there yet —
    SQLite has no "ADD COLUMN IF NOT EXISTS". Needed because CREATE TABLE IF
    NOT EXISTS in SCHEMA only shapes brand-new databases."""
    cols = await db.execute_fetchall(f"PRAGMA table_info({table})")
    if not any(c["name"] == column for c in cols):
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await _ensure_column(db, "users", "display_name", "display_name TEXT")
        await db.executescript(INDEXES)
        await db.commit()
    finally:
        await db.close()
