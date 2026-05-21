# Deploying to Railway

This app is a Flask service that runs a background refresh thread on a schedule.
It is served by gunicorn with a **single worker** (the thread must not be duplicated
across workers). This guide covers a from-scratch deploy with the Railway CLI, plus
the dashboard alternative.

## What's in this repo for deployment

| File | Purpose |
|------|---------|
| `requirements.txt` | Runtime deps (`flask`, `gunicorn`). Railway's builder installs these. |
| `Procfile` | Declares the `web:` process (the gunicorn start command). |
| `railway.json` | Config-as-code: NIXPACKS builder, start command, restart policy. |
| `runtime.txt` | Pins Python to 3.12 for the Nixpacks builder. |

The start command (kept identical in `Procfile` and `railway.json`):

```
gunicorn dealflow_agent.web:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

- `dealflow_agent.web:app` — the Flask app object at `src/dealflow_agent/web.py`.
  The package installs from `src/` via the existing `pyproject.toml`, so the
  `dealflow_agent` module is importable at runtime.
- `--bind 0.0.0.0:$PORT` — Railway injects `$PORT`; bind to it, do not hardcode.
- `--workers 1` — **required.** More than one worker would start multiple copies
  of the background scrape thread.
- `--timeout 120` — gives slow scrape/DB requests headroom before a worker restart.

---

## Option A — Deploy with the Railway CLI

### 1. Install the CLI and log in

```bash
# macOS / Linux
brew install railway
# or, without Homebrew:
#   npm i -g @railway/cli
#   curl -fsSL https://railway.com/install.sh | sh

railway login
```

`railway login` opens a browser to authenticate. On a headless machine use
`railway login --browserless` and paste the pairing code.

### 2. Create a project and link this directory

From the repo root (`/Users/andrewdimaulo/launch-deal-flow-agent`):

```bash
railway init          # creates a new Railway project, prompts for a name
```

This links the current directory to the new project (writes a project ref to
`.railway`/local config). If you already created the project in the dashboard,
run `railway link` instead and pick it from the list.

### 3. Set the environment variables

These are read by the app at runtime. Set them on Railway — do **not** commit them
(`.env` is git-ignored). `PORT` is provided by Railway automatically; you do not set it.

```bash
railway variables \
  --set "GMAIL_USER=your_gmail_address@gmail.com" \
  --set "GMAIL_APP_PASSWORD=your_16_char_app_password" \
  --set "EMAIL_FROM=your_gmail_address@gmail.com" \
  --set "EMAIL_TO=andrewdimaulozx@gmail.com" \
  --set "MIN_SCORE=2.0"
```

Required / read by the app:

| Variable | Notes |
|----------|-------|
| `GMAIL_USER` | Gmail address used to send. |
| `GMAIL_APP_PASSWORD` | Gmail **App Password** (16 chars), not your login password. |
| `EMAIL_FROM` | From address on outbound mail. |
| `EMAIL_TO` | Recipient of the digest. |
| `MIN_SCORE` | Score threshold (e.g. `2.0`). |
| `PORT` | **Set by Railway** — do not add it yourself. |

You can also set/edit these in the dashboard: **Project → service → Variables**.
Mark `GMAIL_APP_PASSWORD` as **sealed/secret** in the dashboard so it can't be read back.

### 4. Add a persistent volume for the SQLite DB

The app writes `data/dealflow.db` (and `reports/`). On Railway the build runs in
`/app`, so the data directory resolves to `/app/data`. Without a volume, that data
is wiped on every redeploy. Mount a volume there:

```bash
railway volume add --mount-path /app/data
```

The CLI will prompt for the service to attach it to, then you redeploy (next step)
for the mount to take effect. Verify with:

```bash
railway volume list
```

Notes:
- Mount path **must** be absolute and start with `/`. `/app/data` keeps the
  existing `<repo>/data/dealflow.db` path working unchanged.
- Reports under `reports/` are regenerated each run and are git-ignored; persisting
  them is optional. If you want them to survive redeploys too, the simplest path is
  to have the app write reports under the data dir as well (a code change — out of
  scope here). The volume above only persists `/app/data`.

### 5. Deploy

```bash
railway up
```

`railway up` uploads the repo, builds with Nixpacks (installs `requirements.txt`,
honors `runtime.txt` → Python 3.12), and starts the `web` process from the start
command. Stream logs while it boots:

```bash
railway logs
```

### 6. Get a public URL

The service has no public URL until you generate a domain:

```bash
railway domain
```

This generates a `*.up.railway.app` URL and prints it. (Same as the dashboard:
**service → Settings → Networking → Generate Domain**.)

### 7. (Optional) Custom domain

```bash
railway domain your-domain.com
```

Then add the CNAME record Railway shows you at your DNS provider (apex domains
need a provider that supports CNAME flattening, or use the ALIAS/ANAME record type).
Railway provisions TLS automatically once DNS resolves.

---

## Option B — Deploy from the Railway dashboard (GitHub)

1. Push this repo to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**, pick the repo.
3. Railway detects `railway.json` + `requirements.txt` + `Procfile` and builds
   with Nixpacks automatically. Every push to the connected branch redeploys.
4. **Variables** tab → add the env vars from step 3 above.
5. **Settings → Volumes** → add a volume mounted at `/app/data`.
6. **Settings → Networking → Generate Domain** for a public URL (or add a custom domain).

---

## Gotchas

- **Single worker is mandatory.** The `--workers 1` flag prevents duplicate
  background scrape threads. If you scale to multiple replicas or raise the worker
  count, the schedule runs N times. Keep one worker / one replica.
- **Env vars are required at runtime, not baked at build.** Set all five before the
  first request; missing Gmail creds will surface as send errors in `railway logs`.
- **Persistence needs the volume.** Without `/app/data` mounted, the SQLite DB resets
  on every deploy/restart. Add the volume before relying on stored history.
- **Free/trial limits.** Railway's trial credit is limited and apps may be paused
  when it runs out; a usage-based (Hobby) plan avoids sleeping. There is no built-in
  "scale to zero," so a long-idle service still consumes credit while running.
- **Cold start after a deploy/restart.** The first request after a redeploy waits for
  gunicorn to boot and the background thread to initialize; expect a brief delay.
- **Nixpacks is in maintenance mode.** It still works and is what `railway.json`
  pins here. If a future build breaks, switching `build.builder` to `RAILPACK`
  (Railway's current default) is the fallback — it also reads `requirements.txt`.
- **Python version granularity.** Nixpacks pins major.minor only (`python-3.12`),
  not a specific patch. For an exact patch you'd need a Dockerfile builder.
