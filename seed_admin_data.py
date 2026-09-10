"""One-time data-import script — mirrors ClaudeCode/tcg-tracker's migrate.py
convention. Not part of app startup; run manually once, after the target
user has an account (or it creates one).

Reads the committed reference JSON (data/labs-history.json,
data/genome-findings.json — Tim's own historical data, seeded from
data/seed_data/ in the container, NOT from the servable static tree, see
Dockerfile/main.py) and inserts it into that user's `records` rows.

Usage (inside the running container, or locally against the same DB path):
    python seed_admin_data.py tim@example.com
"""
import asyncio
import json
import sys
from pathlib import Path

from app.db import get_db, init_db, DATA_DIR

SEED_DIR = Path(__file__).parent / "data"
LABS_FILE = SEED_DIR / "labs-history.json"
GENOME_FILE = SEED_DIR / "genome-findings.json"


async def main(email: str):
    await init_db()
    db = await get_db()
    try:
        row = await db.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not await row.fetchone():
            print(f"Creating user {email} (not seen yet) — will become admin if they're the first user.")
            admin_count = await db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
            count = (await admin_count.fetchone())[0]
            await db.execute(
                "INSERT INTO users (email, is_admin) VALUES (?, ?)",
                (email, 1 if count == 0 else 0),
            )

        labs_count = 0
        if LABS_FILE.exists():
            data = json.loads(LABS_FILE.read_text(encoding="utf-8"))
            labs = data.get("labs", {})
            for id, obj in labs.items():
                await db.execute(
                    "INSERT INTO records (user_email, collection, id, data, updated_at) "
                    "VALUES (?, 'labs', ?, ?, datetime('now')) "
                    "ON CONFLICT(user_email, collection, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                    (email, id, json.dumps(obj)),
                )
                labs_count += 1
        else:
            print(f"Skipping labs: {LABS_FILE} not found")

        genome_count = 0
        if GENOME_FILE.exists():
            data = json.loads(GENOME_FILE.read_text(encoding="utf-8"))
            await db.execute(
                "INSERT INTO records (user_email, collection, id, data, updated_at) "
                "VALUES (?, 'genome', 'main', ?, datetime('now')) "
                "ON CONFLICT(user_email, collection, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (email, json.dumps(data)),
            )
            genome_count = len(data.get("findings", []))
        else:
            print(f"Skipping genome: {GENOME_FILE} not found")

        await db.commit()
        print(f"Seeded {email}: {labs_count} lab results, {genome_count} genome findings.")
    finally:
        await db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Usage: python seed_admin_data.py <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1].strip().lower()))
