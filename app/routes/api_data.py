"""Per-user CRUD over the generic `records` table — backs peptide-tracker.html's
`store` object in 'server' mode (see app/main.py's ALLOWED_COLLECTIONS note).
"""
import json

from fastapi import APIRouter, Request, Response

from ..auth import ensure_user_exists
from ..db import get_db

router = APIRouter(prefix="/api/data", tags=["data"])

# Must match apps/peptide-tracker.html's COLLECTIONS array exactly. This is
# the one guardrail that keeps the schema-free `records` table from being an
# arbitrary key-value store for any authenticated user — anything outside
# this set is rejected before it ever reaches SQL.
ALLOWED_COLLECTIONS = {"programs", "vials", "logs", "settings", "labs", "genome"}

# Generous but bounded — genome findings (~50KB) is the largest single
# record; this leaves headroom without allowing unbounded uploads.
MAX_BODY_BYTES = 2_000_000


@router.get("")
async def get_all_data(request: Request):
    """All 6 collections as id-keyed maps, for store.init()'s one-shot hydration."""
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        rows = await db.execute_fetchall(
            "SELECT collection, id, data FROM records WHERE user_email = ?", (email,)
        )
        out = {col: {} for col in ALLOWED_COLLECTIONS}
        for r in rows:
            if r["collection"] in out:
                out[r["collection"]][r["id"]] = json.loads(r["data"])
        return out
    finally:
        await db.close()


@router.put("/{collection}/{id}")
async def put_record(collection: str, id: str, request: Request, response: Response):
    if collection not in ALLOWED_COLLECTIONS:
        response.status_code = 400
        return {"error": f"Unknown collection: {collection}"}
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        response.status_code = 413
        return {"error": "Record too large"}
    obj = await request.json()
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        await db.execute(
            "INSERT INTO records (user_email, collection, id, data, updated_at) "
            "VALUES (?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(user_email, collection, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (email, collection, id, json.dumps(obj)),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{collection}/batch")
async def put_batch(collection: str, request: Request, response: Response):
    """Bulk upsert — backs store.putMany, i.e. the existing Import UI."""
    if collection not in ALLOWED_COLLECTIONS:
        response.status_code = 400
        return {"error": f"Unknown collection: {collection}"}
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES * 20:
        response.status_code = 413
        return {"error": "Batch too large"}
    records = await request.json()
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        count = 0
        for id, obj in records.items():
            await db.execute(
                "INSERT INTO records (user_email, collection, id, data, updated_at) "
                "VALUES (?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(user_email, collection, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (email, collection, id, json.dumps(obj)),
            )
            count += 1
        await db.commit()
        return {"ok": True, "count": count}
    finally:
        await db.close()


@router.delete("/{collection}/{id}")
async def delete_record(collection: str, id: str, request: Request, response: Response):
    if collection not in ALLOWED_COLLECTIONS:
        response.status_code = 400
        return {"error": f"Unknown collection: {collection}"}
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        await db.execute(
            "DELETE FROM records WHERE user_email = ? AND collection = ? AND id = ?",
            (email, collection, id),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
