# LAUNCHY

**A deal-flow sourcing agent.** It watches the public breadcrumbs top VC firms leave behind, scores companies by how many independent sources land on the same name, and writes a partner-facing brief on the strongest ones.

**Live:** [www.memosoni.com](https://www.memosoni.com)

Built as the evaluation project for a Researcher role at LAUNCH (Jason Calacanis's early-stage firm).

---

## What it does

Top firms leave tracks long before a TechCrunch headline. A Sequoia "partnering with" post. An a16z "investing in" page. A YC batch listing. A quiet SEC Form D weeks after a round closes. A repo picking up stars. A Hacker News thread. On their own, each one is noise. Stack a few on the same company in the same week and you've got a signal.

LAUNCHY pulls from eight public sources every run, groups the raw events by company, and ranks what's left through a four-stage funnel:

```
REACH      →   RESEARCH     →   QUALITY        →   ACTION
cast wider     know more        better founders    act on it
(sources,      (cross-type      (above threshold,  (outbound drafts,
 signals)       enrichment)       convergence)       queued for review)
```

It all ladders up to one number: net-new qualified deal flow.

## How it works

One pipeline, run two ways: a CLI (`run_daily.py`) and the live web app (`web.py`), which re-runs it on a background timer.

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

The split is on purpose: the math finds the deal, the AI explains it.

Scoring is deterministic and explainable. A company's score is the sum of its best per-signal-type weight (decayed by recency), plus a bonus when two or more independent sources name it, plus a small nudge for recurring categories. So a company that hits firm news, a Form D, and GitHub in the same window rises to the top on math alone, no model in the loop. The surfacing threshold is `MIN_SCORE = 2.0`.

The LLM never touches the ranking. It writes the words and the lean-in verdict for deals the math already qualified, and nothing else.

## The brain

For the top deals, an LLM analyst (NVIDIA NIM, OpenAI-compatible) writes a structured read, grounded only in the scraped signals:

- `one_liner` — what the company does, in plain terms
- `why_now` — the timing thesis, tied to the actual signal
- `key_risk` — the biggest unknown
- `conviction_reason` — why the score is real signal, not noise
- **`verdict`** — how hard to lean in: CHASE (move now), WATCH (warm, not yet), or TRACK (on the radar)

A second "editor" pass reads the whole slate and writes the brief's "what matters this week" note: the through-line, the single most urgent company, and what to do about it.

Default model is `meta/llama-3.3-70b-instruct` (set `NIM_MODEL` to change it; Nemotron reasoning models get told to answer directly).

The LLM layer is optional, on purpose. With no API key the analyst and editor calls quietly no-op, and the pipeline falls back to templated rationale. A bad model call gets swallowed so it can't take down a run. Nothing here depends on the model being up.

## Design decisions

The calls that separate this from a scraper:

- **Convergence over volume.** One source is noise. The same company showing up across independent sources in the same window is signal. The agent rewards agreement between sources, not raw count, which is why a quiet Form D plus a GitHub spike plus a funding headline can beat a single loud announcement. That's the whole bet.
- **The math ranks, the AI talks.** Because the ranking is deterministic, "why is this #1?" always has a real answer the model can't fudge. The LLM only writes copy.
- **Precision over recall.** I filter hard: VC funds, SPVs, ETFs, address-style SEC junk, generic-name false matches on Hacker News, and "raises his voice"-type non-funding hits all get dropped. Fourteen clean deals beat two hundred noisy ones. One junk row and a partner stops trusting the list.
- **Free and stdlib, on purpose.** No paid APIs, almost no dependencies. It's proof the idea works on public data, not a product with a budget behind it.
- **Real data only.** No mock numbers. The trend is rebuilt from real signal timestamps, and empty states say they're empty. Every number on screen traces back to something that happened.

## Data sources

Each source module exposes a `collect() -> list[Signal]` and guards itself, so a network failure returns `[]` and never crashes the run.

| Source | Signal |
|---|---|
| **Sequoia** | Official RSS feed: "partnering with / investing in" announcements |
| **a16z** | Public news page: "Investing in …" headlines |
| **Y Combinator** | Blog RSS, plus the live company directory (recent batches, via YC's public Algolia index) |
| **GitHub** | Trending API: emerging AI / infra / dev-tool repos in a star band (established giants are filtered out, since they aren't deal flow) |
| **SEC EDGAR** | Form D full-text search: private-placement filings, often weeks before any press release. Filtered down to operating companies (funds, SPVs, and real-estate vehicles dropped) |
| **Hacker News** | Algolia API: founder/community validation, matched conservatively so generic names don't collide |
| **TechCrunch + GDELT** | Funding-news flow: "X raises $Y" headlines parsed into companies, with VC funds, editorial filler, and non-funding "raises" filtered out |
| **SEC EDGAR (S-1 / Reg-CF)** | Full-text search beyond Form D: IPO-pipeline registrations and crowdfunding raises, with ETFs, SPACs, and shell vehicles dropped |

Before scoring, a cleanup pass strips legal suffixes ("…, Inc."), fixes ALL-CAPS EDGAR names, and drops address and SPV junk so the brief reads like real companies. YC directory listings carry a low weight, so the ~200 live batch companies only qualify when something else corroborates them.

## What I left out, and why

The brief asked what partners are saying on LinkedIn and X. I looked into both and skipped them on purpose:

- **LinkedIn.** Proxycurl, the tool everyone reached for, got sued by LinkedIn and shut down in 2025. The official API can't read other people's profiles, and rolling your own scraper means fighting terms-of-service, legal exposure, and a ceiling of roughly 50 profiles a day. Bad ground to build on.
- **X / Twitter.** The API went pay-per-use in 2026, and the one decent third-party option (TwitterAPI.io) bills per thousand tweets. Doable, but it costs money, and this is a free demo.

So instead of scraping social, I went after the firm-level signals those partners act on anyway: announcements, filings, portfolio moves, and funding news, all from free sources that won't vanish the next time a vendor gets sued.

Adding it later is easy. Partner-social slots in as one more `source_x.py` with the same `collect() -> list[Signal]` shape, pointed at 15-25 vetted handles through a paid API once there's budget. It's a data source, not a rewrite.

## Delivery

- **Live dashboard.** A self-contained, retro-arcade web UI. The HTML carries its own pixel font, inline-SVG charts, a CSS ticker, and an inline-SVG favicon, so there are no external assets or CDNs and it renders offline. It shows the funnel, the score histogram, a real signal trend, the ranked board with verdicts, and the queued outbound drafts.
- **Email me the brief.** A form on the live site that sends the current brief to whatever address you type, on demand, through the Resend HTTP API. Rate-limited, never auto-sent. (Resend over HTTP instead of SMTP, because cloud hosts block outbound SMTP. There's a Gmail-SMTP fallback for local runs.)
- **Ask LAUNCHY.** A chat box that answers questions about the current board ("what's the most urgent deal this week?", "which deals are in fintech?") through the same NIM brain, grounded only in that run's data. Rate-limited, and it says so plainly when there's no model key.
- **Outbound queue.** For each top deal the agent drafts founder outreach, shown for human review. Nothing sends itself.

Storage is SQLite (`data/dealflow.db`).

## Run it locally

The agent core is pure Python standard library. `pyproject.toml` declares `dependencies = []`, and only the web layer adds anything (`flask`, `gunicorn`). Python 3.10+.

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

Use `--workers 1` only. The web app starts a single background thread that re-runs the pipeline every `REFRESH_HOURS`, and extra workers would each spawn a duplicate. `GET /` serves a "warming" page until the first scan finishes, then the cached dashboard.

### Configuration

Config comes from environment variables (a local `.env` is auto-loaded). Everything has a sane default, and nothing below is required to get a working run.

| Variable | Purpose |
|---|---|
| `MIN_SCORE` | Surfacing threshold (default `2.0`) |
| `REFRESH_HOURS` | How often the web app re-scrapes (default `6`) |
| `NVIDIA_API_KEY` *(or `NIM_API_KEY`)* | Turns on the LLM analyst/editor; absent means templated fallback |
| `NIM_MODEL` | LLM model id (default `meta/llama-3.3-70b-instruct`) |
| `NIM_RATIONALE_LIMIT` | Cap on deals sent to the LLM per run (default `15`) |
| `RESEND_API_KEY`, `RESEND_FROM` | Outbound email via the Resend HTTP API |
| `EMAIL_TO` | Default recipient for the CLI/cron digest (the web form sends to the visitor's address) |
| `GITHUB_TOKEN` | Optional, raises GitHub API rate limits |
| `DEALFLOW_DB_PATH` | SQLite file path (default `data/dealflow.db`); point it at a mounted volume to persist on Railway |

`.env` and `data/*.db` are gitignored. Never commit secrets.

## Deploy

Runs on Railway with the same gunicorn command (`Procfile` / `railway.json`, NIXPACKS builder). Pushing to `main` auto-deploys. It runs as a single worker with one background scrape thread, and environment variables (including `NVIDIA_API_KEY` and the Resend keys) live in the Railway dashboard, not the repo. By default the SQLite file sits on the container's ephemeral disk and resets on each deploy, though the trend still rebuilds honestly from real signal timestamps. To keep run-over-run history, attach a Railway Volume and point `DEALFLOW_DB_PATH` at it (mount `/data`, set `DEALFLOW_DB_PATH=/data/dealflow.db`). See [DEPLOY.md](DEPLOY.md) for the full runbook.

## A note on data integrity

Every number on the dashboard traces back to a real scraped signal. There's no synthetic or seeded data. The trend is rebuilt from each signal's actual `observed_at` timestamp (RSS pub dates, Form D file dates, GitHub push times), so the chart shows real history on day one instead of waiting for runs to pile up. The "capital surfaced" figure adds up real Form D offering amounts pulled from the filing XML, not numbers scraped out of prose. Where a source doesn't state a stage, it's labelled unconfirmed.
