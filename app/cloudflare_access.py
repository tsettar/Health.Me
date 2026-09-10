"""Cloudflare Access policy management.

Copied verbatim (generic, not app-specific) from ClaudeCode/tcg-tracker's
app/cloudflare_access.py. health.me sits behind a Cloudflare Access
application — nobody reaches the app at all unless their email is already
allowed by an Access policy, which normally means going into the Cloudflare
dashboard by hand. This lets an admin add someone from health.me's own Admin
page instead, via the Cloudflare API, without touching anything else on the
policy.
"""
import os
import httpx

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_ACCESS_POLICY_ID = os.environ.get("CF_ACCESS_POLICY_ID")

API_BASE = "https://api.cloudflare.com/client/v4"

# Read-only fields Cloudflare rejects if they're echoed back from a GET into
# a PUT body — confirmed by trial against the live API (both the /id and the
# newer /uid alias need dropping, along with reusable-policy metadata).
_READONLY_FIELDS = ("id", "uid", "created_at", "updated_at", "reusable", "app_count")


class CloudflareAccessError(Exception):
    pass


def is_configured() -> bool:
    return bool(CF_API_TOKEN and CF_ACCOUNT_ID and CF_ACCESS_POLICY_ID)


async def add_email_to_policy(email: str) -> bool:
    """Add `email` to the Access policy's allow list, preserving every other
    field on the policy untouched. Returns True if it was added, False if it
    was already present (no-op, not an error).

    Uses the reusable-policy endpoint (/access/policies/{id}), not the
    app-scoped one (/access/apps/{app}/policies/{id}) — Cloudflare rejects
    writes to a reusable policy through the app-scoped endpoint even though
    reads succeed there, which is a confusing way to fail."""
    if not is_configured():
        raise CloudflareAccessError(
            "Cloudflare Access integration isn't configured on the server "
            "(missing CF_API_TOKEN / CF_ACCOUNT_ID / CF_ACCESS_POLICY_ID)"
        )

    url = f"{API_BASE}/accounts/{CF_ACCOUNT_ID}/access/policies/{CF_ACCESS_POLICY_ID}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        data = resp.json()
        if not resp.is_success or not data.get("success"):
            raise CloudflareAccessError(f"Failed to fetch Access policy: {data.get('errors') or resp.text}")
        policy = data["result"]

        include = policy.get("include") or []
        already_present = any(
            (rule.get("email") or {}).get("email", "").lower() == email.lower()
            for rule in include
        )
        if already_present:
            return False

        include = include + [{"email": {"email": email}}]

        # Send back everything the policy already had — only `include`
        # actually changes.
        body = {k: v for k, v in policy.items() if k not in _READONLY_FIELDS}
        body["include"] = include

        put_resp = await client.put(url, headers=headers, json=body)
        put_data = put_resp.json()
        if not put_resp.is_success or not put_data.get("success"):
            raise CloudflareAccessError(f"Failed to update Access policy: {put_data.get('errors') or put_resp.text}")
        return True


async def remove_email_from_policy(email: str) -> bool:
    """Remove `email` from the Access policy's allow list, preserving every
    other field and every other rule untouched. Returns True if it was
    removed, False if it wasn't present (no-op, not an error).

    Mirrors add_email_to_policy's GET-then-PUT-via-the-reusable-endpoint
    approach — see that function's docstring for why the reusable endpoint
    is required for writes."""
    if not is_configured():
        raise CloudflareAccessError(
            "Cloudflare Access integration isn't configured on the server "
            "(missing CF_API_TOKEN / CF_ACCOUNT_ID / CF_ACCESS_POLICY_ID)"
        )

    url = f"{API_BASE}/accounts/{CF_ACCOUNT_ID}/access/policies/{CF_ACCESS_POLICY_ID}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        data = resp.json()
        if not resp.is_success or not data.get("success"):
            raise CloudflareAccessError(f"Failed to fetch Access policy: {data.get('errors') or resp.text}")
        policy = data["result"]

        include = policy.get("include") or []
        new_include = [
            rule for rule in include
            if (rule.get("email") or {}).get("email", "").lower() != email.lower()
        ]
        if len(new_include) == len(include):
            return False

        body = {k: v for k, v in policy.items() if k not in _READONLY_FIELDS}
        body["include"] = new_include

        put_resp = await client.put(url, headers=headers, json=body)
        put_data = put_resp.json()
        if not put_resp.is_success or not put_data.get("success"):
            raise CloudflareAccessError(f"Failed to update Access policy: {put_data.get('errors') or put_resp.text}")
        return True
