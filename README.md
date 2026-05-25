# LAUNCHY

**A deal-flow sourcing agent.** It watches the public breadcrumbs top venture firms leave behind, scores companies by how many independent sources converge on them, and writes a partner-facing brief on the strongest signals.

**Live:** [www.memosoni.com](https://www.memosoni.com)

Built as an evaluation artifact for a Researcher role at LAUNCH (Jason Calacanis's early-stage firm).

---

## What it does

Top firms telegraph their interest long before a TechCrunch headline: a Sequoia "partnering with" post, an a16z "investing in" page, a YC batch listing, a quiet SEC Form D filing weeks after a round closes, a repo gaining stars, a Hacker News thread. Individually these are noise. **Together they're a signal.**

LAUNCHY scrapes eight public sources every run, groups raw events by company, and ranks the result through a four-stage funnel — the spine of the whole product:

```
REACH      →   RESEARCH     →   QUALITY        →   ACTION
cast wider     know more        better founders    act on it
(sources,      (cross-type      (above threshold,  (outbound drafts,
 signals)       enrichment)       convergence)       queued for review)
```

Everything ladders up to one north-star metric: **net-new qualified deal flow**.

## How it works

One linear pipeline, run two ways — a CLI (`run_daily.py`) and the live web app (`web.py`, which re-runs the pipeline on a background timer):

```
sources.collect_all_signals()   →   scoring.score_signals()   →   analyst.enrich_rationale()
   eight public sources              convergence ranking            LLM verdict + memo (in place)
   → list[Signal]                    → list[Opportunity]            + analyst.editor_note()
                                                                              │
                          metrics.build_metrics()  +  outbound.build_drafts()
                                                                              │
                          report.format_report()   +  dashboard.render_dashboard()
                          storage.save_run()  (SQLite)
```

The design is deliberately **hybrid**:

- **The math finds the deal.** Scoring is deterministic and explainable: each company's score is the sum of its best per-signal-type weight (decayed by recency), plus a **cross-source convergence bonus** when 2+ independent sources name the same company, plus a small bonus for recurring categories. A company that shows up in firm news *and* a Form D *and* GitHub in the same window rises to the top by math alone — no model involved. Default surfacing threshold is `MIN_SCORE = 2.0`.
- **The AI explains and judges it.** The LLM layer never reorders the list. It writes the words and the lean-in verdict for deals the math already qualified.

## The brain

For the top deals, an LLM analyst (NVIDIA NIM, OpenAI-compatible API) writes a structured per-deal judgement grounded only in the scraped signals:

- `one_liner` — what the company does, concretely
- `why_now` — the timing thesis tied to the specific signal
- `key_risk` — the single biggest unknown
- `conviction_reason` — why this score is real signal, not noise
- **`verdict`** — how hard to lean in: **CHASE** (move now) / **WATCH** (warm, not yet) / **TRACK** (on the radar)

A second "editor" pass reads the whole qualified slate and writes the brief's **"what matters this week"** note — the through-line, the single most urgent company, and what to do.

Default model: `meta/llama-3.3-70b-instruct`. (The model id is configurable via `NIM_MODEL`; Nemotron reasoning models are detected and told to answer directly.)

**Honesty note: the LLM layer is entirely optional.** With no API key, `enrich_rationale()` and `editor_note()` are graceful no-ops — the pipeline falls back to deterministic templated rationale and runs end to end. Per-deal LLM failures are swallowed so a bad call never breaks a run. Nothing here hard-depends on the model.

## Design decisions (the thinking)

A few judgment calls shaped this build — they're the difference between a scraper and an agent a partner would actually trust:

- **Convergence over volume.** One source is noise; the *same* company surfacing across independent sources in the same window is signal. The agent rewards cross-source agreement, not raw count — which is why a quiet Form D + a GitHub spike + a funding headline can outrank a single loud announcement. That's the core bet.
- **The math finds the deal; the AI explains it.** Ranking is deterministic and reproducible, so *"why is this #1?"* always has a concrete answer a model can't distort. The LLM only writes the words and the lean-in verdict — it never reorders the board.
- **Precision over recall.** I filter aggressively — dropping VC funds, SPVs, ETFs, address-style SEC junk, generic-name false matches, and non-funding "raises." I'd rather surface 14 clean deals than 200 noisy ones; a partner's trust dies on the first junk row.
- **Free and dependency-light, on purpose.** Pure-stdlib core, no paid APIs — it proves the thesis works on public data alone, and it's honest about being a capability demo rather than a funded product.
- **Real data, always.** No mock numbers. The trend is rebuilt from real signal timestamps; empty states say so plainly. If a metric is on screen, it traces to something that actually happened.

## Data sources

Each source module exposes a `collect() -> list[Signal]` and is self-guarded — a network failure returns `[]` and never crashes the run.

| Source | Signal |
|---|---|
| **Sequoia** | Official RSS feed — "partnering with / investing in" announcements |
| **a16z** | Public news page — "Investing in …" headlines |
| **Y Combinator** | Blog RSS **and** the live company directory (recent batches, via YC's public Algolia index) |
| **GitHub** | Trending API — *emerging* AI / infra / dev-tool repos in a star band (established giants are filtered out; they aren't deal flow) |
| **SEC EDGAR** | Form D full-text search — private-placement filings, often weeks before any press release; aggressively filtered down to operating companies (funds, SPVs, and real-estate vehicles dropped) |
| **Hacker News** | Algolia API — founder/community validation, matched conservatively to avoid generic-name false positives |
| **TechCrunch + GDELT** | Funding-news flow — "X raises $Y" headlines parsed into companies (precision-filtered: VC funds, editorial filler, and non-funding "raises" dropped) |
| **SEC EDGAR (S-1 / Reg-CF)** | Full-text search beyond Form D — IPO-pipeline registrations + crowdfunding raises (ETFs / SPACs / vehicles filtered out) |

Before scoring, a cleanup pass strips legal suffixes (`…, Inc.`), de-shouts ALL-CAPS EDGAR names, and drops address/SPV-style junk so the brief reads like real companies. YC directory listings are demoted in weight so the ~200 live batch companies only surface as qualified deals when another source corroborates them.

## What I deliberately left out — and why

The brief asked what partners are "talking about on LinkedIn and X." I researched both and chose **not** to wire them — a deliberate call, not a gap:

- **LinkedIn.** The obvious tool (Proxycurl) was sued by LinkedIn and shut down in 2025. The official API can't read third-party profiles, and DIY scraping is a terms-of-service and legal minefield with a ~50-profiles/day ceiling. Not a foundation to build a credible agent on.
- **X / Twitter.** The API moved to metered pay-per-use in 2026, and the viable third-party route (TwitterAPI.io) is paid per 1,000 tweets. Workable — but paid, and this is a free capability demo.

So instead of brittle, paid, or ToS-risky social scraping, I covered the **firm-level** signals those partners ultimately act on — announcements, SEC filings, portfolio activity, and funding news — from free, durable sources. The convergence engine is where the edge is anyway.

It's a clean add later, too: partner-social would drop in as one more `source_x.py` (same `collect() -> list[Signal]` contract) pointed at ~15–25 vetted partner handles via a paid API, once there's budget. The architecture already supports it — a data-source toggle, not a redesign.

## Delivery

- **Live dashboard** — a self-contained, retro-arcade web UI (neon 8-bit theme). The HTML embeds its own base64 pixel font, inline-SVG charts, a CSS marquee ticker, and an inline-SVG favicon — **no external assets, no CDNs** (it renders offline). It surfaces the funnel, the score-distribution histogram, a real signal trend, the ranked deal board with verdicts, and the queued outbound drafts.
- **"Email me the brief"** — a form on the live site that sends the real, current brief to the address you type, on demand, via the **Resend** HTTP API. It's rate-limited and never auto-sends. (Email goes through Resend's HTTP API rather than SMTP because cloud hosts block outbound SMTP; a local Gmail-SMTP path exists as a fallback.)
- **"Ask LAUNCHY"** — a chat box on the dashboard for interrogating the board. The `POST /ask` route answers free-form questions ("What's the most urgent deal this week?", "Which deals are in fintech?") grounded **only** in the current run's deal board, via the same NIM brain. It's rate-limited, and degrades to a friendly offline message when no model key is configured.
- **Outbound queue** — for each top deal the agent drafts founder-outreach copy, shown on the dashboard for human review. Nothing is auto-sent.

Persistence is **SQLite** (`data/dealflow.db`).

## Run it locally

The agent core is **pure Python standard library** — `pyproject.toml` declares `dependencies = []`. Only the web layer adds anything (`flask`, `gunicorn`). Python 3.10+.

```bash
# Run the pipeline once: scrape → score → write report + dashboard to reports/ (no email)
make report
#  = PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email

make dashboard      # run the pipeline, then open reports/dashboard-latest.html
make serve          # serve reports/ at http://127.0.0.1:8765

# Run the live web app locally (same command production uses — note --pythonpath src):
pip install -r requirements.txt
gunicorn --pythonpath src dealflow_agent.web:app --bind 127.0.0.1:8080 --workers 1 --timeout 120
```

Run with `--workers 1` only: the web app starts a single background thread that re-runs the pipeline every `REFRESH_HOURS`; extra workers would each spawn a duplicate. `GET /` serves a "warming" page until the first scan completes, then the cached dashboard.

### Configuration

All config comes from environment variables (a local `.env` is auto-loaded). Everything has a sane default; nothing below is required to get a working run.

| Variable | Purpose |
|---|---|
| `MIN_SCORE` | Surfacing threshold (default `2.0`) |
| `REFRESH_HOURS` | How often the web app re-scrapes (default `6`) |
| `NVIDIA_API_KEY` *(or `NIM_API_KEY`)* | Activates the LLM analyst/editor; absent → templated fallback |
| `NIM_MODEL` | LLM model id (default `meta/llama-3.3-70b-instruct`) |
| `NIM_RATIONALE_LIMIT` | Cap on deals sent to the LLM per run (default `15`) |
| `RESEND_API_KEY`, `RESEND_FROM` | Outbound email via the Resend HTTP API |
| `EMAIL_TO` | Default recipient for the CLI/cron digest (the web form sends to the visitor's address) |
| `GITHUB_TOKEN` | Optional — raises GitHub API rate limits |
| `DEALFLOW_DB_PATH` | SQLite file path (default `data/dealflow.db`); point at a mounted volume to persist on Railway |

`.env` and `data/*.db` are gitignored. Never commit secrets.

## Deploy

Deployed on **Railway** via the same gunicorn command (`Procfile` / `railway.json`, NIXPACKS builder). **Pushing to `main` auto-deploys.** Runs as a single worker with one background scrape thread; environment variables (including `NVIDIA_API_KEY` and the Resend keys) are set in the Railway dashboard, not committed. By default the SQLite file sits on the container's ephemeral disk and resets on each deploy (the trend still rebuilds honestly from real signal timestamps). To persist run-over-run history, attach a Railway **Volume** and point `DEALFLOW_DB_PATH` at it — e.g. mount `/data` and set `DEALFLOW_DB_PATH=/data/dealflow.db`.

## A note on data integrity

Every number on the dashboard traces back to a real, scraped signal — there is no synthetic or seeded data. The signal **trend** is reconstructed honestly from each signal's actual `observed_at` timestamp (RSS pub dates, Form D file dates, GitHub push times), so the chart shows real history on day one rather than waiting for runs to accumulate. The "capital surfaced" figure sums real Form D `totalOfferingAmount` values pulled from filing XML, not numbers regex'd out of free text. Estimated stages are labelled as unconfirmed where the source doesn't state them.
