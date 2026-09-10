# Deploying health.me

Architecture (mirrors `ClaudeCode/tcg-tracker`'s CardOx deployment):

```
Browser -> Cloudflare Edge -> Cloudflare Access (email login gate)
        -> Cloudflare Tunnel (encrypted, outbound-only)
        -> cloudflared container -> health-me container (localhost:8080)
```

No inbound ports are opened; `cloudflared` makes an outbound-only connection
to Cloudflare. **The `health-me` app container must never receive any other
ingress** — no host port beyond `127.0.0.1:8080:8080` (for local debugging
only), no reverse proxy, nothing. The app's auth (`app/auth.py`) checks JWT
*claims*, not a cryptographic signature — the real security boundary is that
Cloudflare Access is the only way traffic reaches this container at all. A
"quick debug" port-forward or an alternate proxy in front of it would let
unauthenticated requests straight through.

## 1. Create a Tunnel

Cloudflare dashboard -> Zero Trust -> Networks -> Tunnels -> Create a tunnel.
Name it (e.g. `health-me`), copy the token it shows you — that's `TUNNEL_TOKEN`.

Add a **Public Hostname** route on the tunnel: pick a subdomain (e.g.
`health.yourdomain.com`), service type `HTTP`, target `health-me:8080` (the
docker-compose service name — both containers share a network, so this
resolves without any port publishing).

## 2. Create an Access Application + Policy

Zero Trust -> Access -> Applications -> Add an application -> Self-hosted.
Application domain: the same hostname you routed the tunnel to.

Add a Policy (Allow rule): specific emails, or an email-domain rule, for
whoever should be able to log in. Auth method: One-time PIN (email OTP) is
simplest — no separate identity provider needed.

Note your **team domain** (Zero Trust -> Settings -> Custom Pages, or just
the URL your team's Access login page uses) — that's `CF_TEAM_DOMAIN`, e.g.
`myteam.cloudflareaccess.com`.

## 3. API token for the in-app Admin page

The Admin page's Invite/Disable/Enable buttons call the Cloudflare API
directly (rather than you editing the policy by hand each time). Create:

- An **API Token** (My Profile -> API Tokens -> Create Token) scoped to your
  account with Access: Apps and Policies edit permission -> `CF_API_TOKEN`.
- Your **Account ID** (visible on any Zero Trust page, or Account Home) ->
  `CF_ACCOUNT_ID`.
- The specific **Policy ID** you created in step 2 (visible in that policy's
  URL in the dashboard, or via `GET /accounts/{account_id}/access/policies`)
  -> `CF_ACCESS_POLICY_ID`.

If you'd rather skip this and just manage the allowed emails by hand in the
Cloudflare dashboard, leave these three blank — the app still works, the
Admin page's invite/disable/enable buttons just show a clear error instead.

## 4. Bring it up

```bash
cp .env.example .env   # fill in TUNNEL_TOKEN, CF_TEAM_DOMAIN, CF_API_TOKEN, CF_ACCOUNT_ID, CF_ACCESS_POLICY_ID
docker compose up -d --build
```

Visit the hostname you routed in step 1. The first person to log in becomes
admin automatically.

## 5. Seed your existing data (optional, one-time)

If you have `data/labs-history.json` / `data/genome-findings.json` (or your
own equivalents) to bring in for a specific account:

```bash
docker compose exec health-me python seed_admin_data.py you@example.com
```

Safe to run before or after that email's first login.

## Local development (no Cloudflare needed)

Set `DEV_USER=you@example.com` in `.env` (or export it directly) — every
request is then treated as authenticated as that email, no Cloudflare Access
or Tunnel required at all:

```bash
DEV_USER=you@example.com uvicorn app.main:app --reload --port 8080
```

or via compose, with `cloudflared` simply not started:

```bash
docker compose up -d --build health-me
```

**Never set `DEV_USER` in production** — it disables all real authentication.
