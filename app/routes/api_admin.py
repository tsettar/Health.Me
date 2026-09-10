"""Admin endpoints for user management — mirrors
ClaudeCode/tcg-tracker's app/routes/api_admin.py (invite/disable/enable/
toggle-admin/delete), adapted to health.me's single `records` table (which
makes delete-user simpler: one DELETE instead of a per-table list).
"""
from fastapi import APIRouter, Request, Response

from ..auth import require_admin
from ..cloudflare_access import add_email_to_policy, remove_email_from_policy, CloudflareAccessError
from ..db import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def list_users(request: Request):
    db = await get_db()
    try:
        await require_admin(request, db)
        rows = await db.execute_fetchall(
            """
            SELECT u.email, u.display_name, u.is_admin, u.is_disabled, u.created_at,
                   (SELECT COUNT(*) FROM records r WHERE r.user_email = u.email AND r.collection = 'programs') AS program_count
            FROM users u
            ORDER BY u.created_at
            """
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("/users/invite")
async def invite_user(request: Request, response: Response):
    """Add an email to the Cloudflare Access policy that gates health.me, so
    that person can actually reach the app — then pre-create their local
    user row so they show up in the list immediately instead of waiting for
    their first login."""
    db = await get_db()
    try:
        await require_admin(request, db)
        body = await request.json()
        email = (body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            response.status_code = 400
            return {"error": "Enter a valid email address"}

        try:
            added = await add_email_to_policy(email)
        except CloudflareAccessError as e:
            response.status_code = 502
            return {"error": str(e)}

        row = await db.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not await row.fetchone():
            await db.execute("INSERT INTO users (email, is_admin) VALUES (?, 0)", (email,))
            await db.commit()

        return {"ok": True, "email": email, "added_to_policy": added}
    finally:
        await db.close()


@router.post("/users/{email}/disable")
async def disable_user(email: str, request: Request, response: Response):
    """Remove the user's email from the Cloudflare Access policy so they can
    no longer reach health.me, but keep their account row and all their data
    intact so they can be re-enabled later."""
    db = await get_db()
    try:
        admin_email = await require_admin(request, db)
        if email == admin_email:
            response.status_code = 400
            return {"error": "Cannot disable your own account"}

        row = await db.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not await row.fetchone():
            response.status_code = 404
            return {"error": "User not found"}

        try:
            removed = await remove_email_from_policy(email)
        except CloudflareAccessError as e:
            response.status_code = 502
            return {"error": str(e)}

        await db.execute("UPDATE users SET is_disabled = 1 WHERE email = ?", (email,))
        await db.commit()
        return {"ok": True, "email": email, "removed_from_policy": removed}
    finally:
        await db.close()


@router.post("/users/{email}/enable")
async def enable_user(email: str, request: Request, response: Response):
    """Add the user's email back to the Cloudflare Access policy and clear
    their disabled flag, restoring access to their existing account/data."""
    db = await get_db()
    try:
        await require_admin(request, db)

        row = await db.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not await row.fetchone():
            response.status_code = 404
            return {"error": "User not found"}

        try:
            added = await add_email_to_policy(email)
        except CloudflareAccessError as e:
            response.status_code = 502
            return {"error": str(e)}

        await db.execute("UPDATE users SET is_disabled = 0 WHERE email = ?", (email,))
        await db.commit()
        return {"ok": True, "email": email, "added_to_policy": added}
    finally:
        await db.close()


@router.post("/users/{email}/admin")
async def toggle_admin(email: str, request: Request, response: Response):
    db = await get_db()
    try:
        admin_email = await require_admin(request, db)
        body = await request.json()
        is_admin = 1 if body.get("is_admin") else 0

        if email == admin_email and not is_admin:
            response.status_code = 400
            return {"error": "Cannot remove your own admin status"}

        await db.execute("UPDATE users SET is_admin = ? WHERE email = ?", (is_admin, email))
        await db.commit()
        return {"ok": True, "email": email, "is_admin": bool(is_admin)}
    finally:
        await db.close()


@router.delete("/users/{email}")
async def delete_user(email: str, request: Request, response: Response):
    """Permanently delete a user account and everything they own, and strip
    them from the Cloudflare Access policy. Unlike disable, this cannot be
    undone. Single DELETE across the generic records table — no per-
    collection list to keep in sync as health.me grows new collections."""
    db = await get_db()
    try:
        admin_email = await require_admin(request, db)
        if email == admin_email:
            response.status_code = 400
            return {"error": "Cannot delete your own account"}

        row = await db.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not await row.fetchone():
            response.status_code = 404
            return {"error": "User not found"}

        try:
            await remove_email_from_policy(email)
        except CloudflareAccessError as e:
            response.status_code = 502
            return {"error": str(e)}

        await db.execute("DELETE FROM records WHERE user_email = ?", (email,))
        await db.execute("DELETE FROM users WHERE email = ?", (email,))
        await db.commit()
        return {"ok": True, "email": email}
    finally:
        await db.close()
