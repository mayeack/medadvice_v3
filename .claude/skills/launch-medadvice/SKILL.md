---
name: launch-medadvice
description: Launch / run / start / serve the MedAdvice app — either locally on http://localhost:8001 or publicly via a Cloudflare tunnel behind the access key. Use when asked to run, start, serve, boot, or expose this application, or to confirm it's serving.
---

# Launch MedAdvice

MedAdvice is a FastAPI app (`backend/main.py`) launched by `./run.sh`, which
activates `venv/`, then runs `python -m backend.main` → uvicorn on
**`0.0.0.0:8001`**. It serves a chat UI at `/app`, admin/governance UIs, `/docs`,
and the `/api/chat` + `/admin` JSON APIs.

There are **two launch modes** — pick based on what the user asked for:

| Mode | Reach | Use when |
|------|-------|----------|
| **A — Local** | `localhost` + your LAN | Day-to-day dev, testing a change |
| **B — Public tunnel** | A public HTTPS URL | Sharing the app over the internet |

Both modes run the *same* server (Mode B just adds a tunnel in front). The
access-key gate (below) applies identically to both.

## Prerequisites (both modes)

- `.env` exists with the AI provider key — for the default Anthropic provider,
  `ANTHROPIC_API_KEY=sk-ant-...`. Without it the app boots but chat fails.
- `venv/` exists (run.sh creates it and installs `requirements.txt` on first run).
- **Access key:** `ACCESS_KEY` in `.env` gates every route except `/health`.
  Empty/unset ⇒ gate disabled (open). Generate one with `openssl rand -hex 24`.

## The access-key gate (how to get in)

Enforced by `backend/middleware/access_key.py`. Two ways to authenticate:

- **Browser** → any gated URL shows a styled "Access required" page → **Enter
  access code** → `/login` form → enter the `ACCESS_KEY` value → an HttpOnly
  cookie is set and you land in the app. (`backend/routers/auth.py`,
  `frontend/login.html`.)
- **API / curl** → HTTP Basic Auth with the key as the password, any username:
  `curl -u x:$ACCESS_KEY ...`.

`/health` is the only unauthenticated route (used by health/uptime checks).

---

## Mode A — Local (localhost)

```bash
./run.sh                       # foreground; Ctrl+C stops it
# or, to keep your shell free, run it in the background and tail the log:
#   ./run.sh > /tmp/medadvice.log 2>&1 &
```

Wait for `Application startup complete`, then open **http://localhost:8001/app**
and log in with the access code.

Other URLs: `/admin-ui`, `/governance-ui`, `/docs`.

---

## Mode B — Public (Cloudflare quick tunnel)

Exposes the *locally running* server to the internet — no cloud deploy; local
SQLite (`medadvice.db`) and `.env` stay in place. The tunnel relies on the
access key for protection, so **make sure `ACCESS_KEY` is set** before sharing.

```bash
brew install cloudflared        # one-time prerequisite

# terminal 1 — the app (as in Mode A)
./run.sh

# terminal 2 — the public tunnel
./tunnel.sh                     # = cloudflared tunnel --url http://localhost:8001
```

`tunnel.sh` prints a `https://<random>.trycloudflare.com` URL — **a new one each
run** (quick tunnels are ephemeral). Open it in a browser and log in with the
access code; Cloudflare terminates TLS so the code travels encrypted.

To stop sharing, Ctrl+C the tunnel (terminal 2). The app keeps running.

---

## Verify it's serving

```bash
KEY=$(grep '^ACCESS_KEY=' .env | cut -d= -f2)
curl -s -o /dev/null -w "health=%{http_code}\n"            http://localhost:8001/health          # want 200
curl -s -o /dev/null -w "no-key=%{http_code}\n"            http://localhost:8001/admin/logs/metrics  # want 401
curl -s -o /dev/null -w "with-key=%{http_code}\n" -u x:$KEY http://localhost:8001/admin/logs/metrics # want 200
```

For Mode B, swap `http://localhost:8001` for the printed `trycloudflare.com` URL.

## Stop it

```bash
lsof -ti:8001 | xargs kill          # stop the app (add -9 if it lingers)
```
If launched in the foreground, Ctrl+C in that terminal instead.

## Gotchas (learned the hard way)

- **Reload loop:** with `DEBUG=True`, uvicorn auto-reloads on file changes. The
  app writes `medadvice.db` and `logs/*.json` as it serves, which would trigger
  a reload after almost every request — so `backend/main.py` passes
  `reload_excludes=["*.db","*.db-journal","*.db-wal","*.log","*.json"]`. Keep
  that. For a stable/public run, prefer `DEBUG=False` in `.env` (disables reload
  and verbose tracebacks entirely).
- **Two `cloudflared` runs = two different URLs.** The previous URL dies when you
  restart the tunnel. For a stable URL you'd need a named tunnel + a domain.
- **Synthetic data:** this is a demo app that deliberately injects synthetic
  PII/toxic/hallucinated content (`*_injection_rate` in `backend/config.py`).
  Don't treat it as a real medical service.
- **Port already in use:** something's already on 8001 — `lsof -ti:8001 | xargs
  kill`, or change `PORT` in `.env` (and pass the new port to `./tunnel.sh`).
