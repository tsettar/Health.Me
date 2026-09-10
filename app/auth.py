"""Authentication via Cloudflare Access headers with optional JWT validation.

Adapted near-verbatim from ClaudeCode/tcg-tracker's app/auth.py — same
Cloudflare Access header/JWT model, same DEV_USER local-dev bypass, same
users table shape (email PK, is_admin, is_disabled). See that file for the
original and DEPLOY.md for the trust-boundary note this depends on: the real
security guarantee here is that this app container never receives any
ingress except through the Cloudflare Tunnel (no host port), not the JWT
"verification" below (which checks claims, not the signature) — Cloudflare
Access itself is what stops an unauthenticated request from ever arriving.
"""
import os
import logging
import json
import time
from typing import Optional

from fastapi import Request, HTTPException

log = logging.getLogger(__name__)

DEV_USER = os.environ.get("DEV_USER")
CF_EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"
CF_JWT_HEADER = "Cf-Access-Jwt-Assertion"
CF_TEAM_DOMAIN = os.environ.get("CF_TEAM_DOMAIN")  # e.g. "myteam.cloudflareaccess.com"

_jwks_cache: Optional[dict] = None
_jwks_fetched_at: float = 0
JWKS_TTL = 3600


async def _fetch_jwks(team_domain: str) -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < JWKS_TTL:
        return _jwks_cache

    import httpx
    url = f"https://{team_domain}/cdn-cgi/access/certs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
        return _jwks_cache


def _decode_jwt_payload(token: str) -> dict:
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding
    return json.loads(base64.urlsafe_b64decode(payload))


def _verify_jwt(token: str, team_domain: str) -> str:
    payload = _decode_jwt_payload(token)

    iss = payload.get("iss", "")
    if team_domain not in iss:
        raise ValueError(f"JWT issuer mismatch: {iss}")

    exp = payload.get("exp", 0)
    if time.time() > exp:
        raise ValueError("JWT expired")

    email = payload.get("email", "")
    if not email:
        raise ValueError("JWT missing email claim")

    return email


def client_ip(request: Request) -> str | None:
    """Real client IP: every request arrives from the cloudflared container
    over the docker network, not the actual visitor, so prefer Cloudflare's
    own edge header (unforgeable past their edge) over the standard-but-
    spoofable X-Forwarded-For, falling back to the raw socket address only
    for local/DEV_USER testing where neither header exists."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_email(request: Request) -> str:
    """Extract user email from request, with JWT validation if CF_TEAM_DOMAIN is set."""
    if DEV_USER:
        return DEV_USER.lower()

    jwt_token = request.headers.get(CF_JWT_HEADER)
    email_header = request.headers.get(CF_EMAIL_HEADER)

    if CF_TEAM_DOMAIN and jwt_token:
        try:
            email = _verify_jwt(jwt_token, CF_TEAM_DOMAIN)
            return email.lower()
        except Exception as e:
            log.warning("JWT verification failed: %s", e)
            raise HTTPException(status_code=401, detail="Invalid access token")

    if email_header:
        return email_header.lower()

    raise HTTPException(status_code=401, detail="Not authenticated")


async def ensure_user_exists(request: Request, db) -> str:
    email = get_user_email(request)
    row = await db.execute("SELECT is_disabled FROM users WHERE email = ?", (email,))
    user = await row.fetchone()
    if not user:
        admin_count = await db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        count = (await admin_count.fetchone())[0]
        is_admin = 1 if count == 0 else 0
        await db.execute(
            "INSERT INTO users (email, is_admin) VALUES (?, ?)",
            (email, is_admin),
        )
        await db.commit()
    elif user["is_disabled"]:
        # Belt-and-suspenders: a disabled user's Cloudflare Access session/JWT
        # may still be valid even after their email is removed from the
        # policy, so enforce the block at the app level too.
        raise HTTPException(status_code=403, detail="This account has been disabled")
    return email


async def require_admin(request: Request, db) -> str:
    email = get_user_email(request)
    row = await db.execute("SELECT is_admin, is_disabled FROM users WHERE email = ?", (email,))
    user = await row.fetchone()
    if not user or not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    if user["is_disabled"]:
        raise HTTPException(status_code=403, detail="This account has been disabled")
    return email
