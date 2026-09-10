"""health.me — FastAPI application."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .db import init_db
from .auth import ensure_user_exists
from .db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Only index.html and apps/peptide-tracker.html land here (see Dockerfile) —
# NOT apps/blood-test-dashboard.html or apps/genome-dashboard.html (Tim's
# real historical labs and raw 23andMe SNP data), and NOT data/*.json.
# Cloudflare Access gates the whole hostname, not individual paths, so once
# any other user is invited, anything under this directory is reachable by
# them — those files must never be copied in here.
STATIC_DIR = Path(os.environ.get("HEALTHME_STATIC_DIR", "/app/static"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="health.me", lifespan=lifespan)

# Register API routers BEFORE the catch-all static route below — Starlette
# matches in registration order, so a misordered catch-all would silently
# swallow every API request.
from .routes.api_data import router as data_router
from .routes.api_admin import router as admin_router

app.include_router(data_router)
app.include_router(admin_router)


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/api/me")
async def me(request: Request):
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        row = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = await row.fetchone()
        return {
            "email": user["email"],
            "display_name": user["display_name"],
            "is_admin": bool(user["is_admin"]),
            "created_at": user["created_at"],
        }
    finally:
        await db.close()


@app.put("/api/me")
async def update_me(request: Request):
    db = await get_db()
    try:
        email = await ensure_user_exists(request, db)
        body = await request.json()
        display_name = (body.get("display_name") or "").strip()[:80] or None
        await db.execute("UPDATE users SET display_name = ? WHERE email = ?", (display_name, email))
        await db.commit()
        return {"ok": True, "display_name": display_name}
    finally:
        await db.close()


@app.get("/{path:path}")
async def static_fallback(path: str):
    """Serve the exact static file if it exists (index.html, apps/peptide-tracker.html).
    Empty path -> index.html. No SPA-style fallback-to-index for unknown
    paths — health.me isn't a client-routed app at the URL level, so an
    unknown path is just a 404."""
    if not path:
        path = "index.html"
    file_path = STATIC_DIR / path
    try:
        file_path.relative_to(STATIC_DIR)
    except ValueError:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if file_path.is_file():
        return FileResponse(file_path)
    return JSONResponse({"error": "Not found"}, status_code=404)
