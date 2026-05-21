# MEMOSONI / LAUNCH Deal Flow Agent Architecture

This document defines the scoped architecture for the demo build.

The goal is not to build a perfect autonomous VC analyst. The goal is to ship a polished, believable, working sourcing ops pipeline for LAUNCH:

1. A public website/dashboard that looks polished.
2. A real backend agent that scans sources throughout the day.
3. Persistent storage so signals accumulate and velocity can be measured.
4. A live email report flow that proves the pipeline works end-to-end.

## Demo promise

MEMOSONI watches Sequoia, a16z, and Y Combinator signals, turns them into structured deal-flow opportunities, ranks them by sourcing value, and emails a real-time LAUNCH brief.

## Scope guardrails

Ship this:

- polished dashboard
- real source scans from public web/API endpoints
- persistent SQLite database
- cron/scheduler loop
- Gmail report delivery
- seeded watchlist where public sources are incomplete
- honest labels for implemented vs planned integrations

Do not ship tomorrow:

- full LinkedIn scraping
- full X/Twitter API integration unless credentials are already ready
- autonomous founder outbound
- user accounts
- complex authentication
- full CRM
- perfect company enrichment
- paid-data integrations that require procurement

## System diagram

```text
                 ┌──────────────────────────┐
                 │ Public dashboard / site  │
                 │ Railway / Flask          │
                 └────────────┬─────────────┘
                              │
                              ▼
                 ┌──────────────────────────┐
                 │ Latest ranked pipeline   │
                 │ metrics + opportunities  │
                 └────────────┬─────────────┘
                              │ reads
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SQLite storage                          │
│                                                             │
│  sources     tracked source registry                        │
│  runs        scan run history                               │
│  signals     raw normalized source observations             │
│  companies   startup/company watchlist                      │
│  scores      opportunity score snapshots                    │
│  reports     generated report metadata                      │
│  emails      requested/sent report events                   │
└────────────────────────────┬────────────────────────────────┘
                             │ writes
                             ▼
                 ┌──────────────────────────┐
                 │ Cron / background agent  │
                 │ scan every N hours       │
                 └────────────┬─────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
       ▼                      ▼                      ▼
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ Sequoia     │        │ a16z        │        │ YC          │
│ official    │        │ official    │        │ blog + dir  │
│ RSS/news    │        │ news page   │        │ companies   │
└──────┬──────┘        └──────┬──────┘        └──────┬──────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ▼
                 ┌──────────────────────────┐
                 │ Normalize signals        │
                 │ company, source, date,   │
                 │ type, URL, confidence    │
                 └────────────┬─────────────┘
                              ▼
                 ┌──────────────────────────┐
                 │ Score + dedupe           │
                 │ recency, source weight,  │
                 │ velocity, repeat signals │
                 └────────────┬─────────────┘
                              ▼
                 ┌──────────────────────────┐
                 │ Report + email           │
                 │ Gmail SMTP               │
                 └──────────────────────────┘
```

## Frontend / visual scaffold

The dashboard should sell the work in 10 seconds.

### Above the fold

- Product name: MEMOSONI
- Subtitle: LAUNCH Deal Flow Agent
- One-line explanation:
  - "An always-on sourcing ops agent that turns Sequoia, a16z, YC, and founder-community signals into ranked deal-flow opportunities."
- Live status badge:
  - LIVE
  - Last scan timestamp
  - Sources monitored
- Email form:
  - "Send me the live report"

### Main sections

1. Funnel HUD
   - Reach: sources monitored, signals ingested
   - Research: companies tracked, enriched companies
   - Quality: qualified opportunities above threshold
   - Action: email/report/outbound drafts generated

2. Spotlight opportunity
   - top-ranked company
   - composite score
   - why it matters
   - triggering source links

3. Deal leaderboard
   - top 8-15 companies
   - score
   - category
   - source count
   - stage estimate

4. Source coverage
   - Sequoia official announcements
   - a16z news/investment posts
   - YC blog/company directory
   - Hacker News/community validation
   - Planned: X, LinkedIn, Crunchbase, Exa

5. Outbound queue
   - founder outreach drafts
   - clearly marked: pending human approval, not auto-sent

6. Proof / repo footer
   - GitHub repo link
   - last commit / build timestamp if easy
   - built for LAUNCH application/demo

## Backend module scaffold

Current package path:

```text
src/dealflow_agent/
```

Recommended final module shape:

```text
config.py          env vars and runtime config
models.py          Signal, Company, Opportunity, Run, Metrics
sources.py         common source utilities + source registry
source_sequoia.py  Sequoia scans
source_a16z.py     a16z scans
source_yc.py       YC scans
source_hn.py       Hacker News scans
source_github.py   optional GitHub momentum scans
source_edgar.py    optional funding/Form D scans
storage.py         SQLite persistence and queries
scoring.py         scoring model and velocity logic
metrics.py         dashboard funnel metrics
report.py          text report formatting
emailer.py         Gmail SMTP send
outbound.py        draft outreach copy, never auto-send
web.py             Flask app and email form
run_daily.py       CLI pipeline runner
```

## Storage scaffold

Use SQLite for tomorrow. It is simple, local, demoable, and deployable with a Railway volume.

Database path:

```text
data/dealflow.db
```

Do not commit the database unless intentionally using a small demo seed DB. Prefer keeping DB ignored and generating it from scans.

### Tables

```sql
sources(
  id integer primary key,
  name text not null,
  firm text,
  source_type text,
  url text,
  enabled integer default 1,
  last_checked_at text
)

runs(
  id integer primary key,
  started_at text not null,
  finished_at text,
  status text,
  signals_found integer default 0,
  qualified_found integer default 0,
  error text
)

signals(
  id integer primary key,
  signal_key text unique,
  company text not null,
  source text not null,
  source_type text not null,
  title text,
  url text,
  observed_at text,
  description text,
  category text,
  stage text,
  raw_json text,
  first_seen_at text not null,
  last_seen_at text not null,
  seen_count integer default 1
)

companies(
  id integer primary key,
  name text unique not null,
  category text,
  stage text,
  website text,
  yc_batch text,
  first_seen_at text,
  last_seen_at text,
  signal_count integer default 0
)

scores(
  id integer primary key,
  run_id integer,
  company text not null,
  score real not null,
  trigger text,
  why_it_matters text,
  stage text,
  category text,
  source_count integer,
  created_at text not null
)

reports(
  id integer primary key,
  run_id integer,
  path text,
  generated_at text not null,
  emailed_to text
)

email_events(
  id integer primary key,
  email_to text not null,
  subject text,
  status text,
  created_at text not null,
  error text
)
```

## Cron / scheduling scaffold

For tomorrow, use one of two deployment-friendly options.

### Option A: app background loop

Already present in `web.py` style:

- Flask app starts
- daemon thread wakes every `REFRESH_HOURS`
- runs collection/scoring/storage
- dashboard reads latest cache/DB

Pros:
- simple
- good for demo
- no extra service

Cons:
- single-worker only
- not as robust as a real worker queue

Use for demo.

### Option B: Railway cron or Hermes cron

A separate scheduled runner calls:

```bash
python3 -m dealflow_agent.run_daily --email
```

Pros:
- cleaner production model
- easier to reason about scheduled jobs

Cons:
- more setup time
- requires job configuration

Use later if time remains.

## Data collection cadence

For demo:

- Full scan every 6 hours
- Manual scan on deploy/startup
- Email on request from website

For future:

- Partner/social scan every 1-2 hours
- Official announcements every 4-6 hours
- YC/company directory daily
- GitHub/hiring momentum daily
- Weekly summary report

## Real calls vs simulated/seeded data

The demo should make real network calls for:

- Sequoia official RSS/news
- a16z public news/content
- YC blog/company pages where accessible
- Hacker News Algolia
- GitHub API/public pages where rate limits permit
- SEC EDGAR public submissions/Form D if implemented

Acceptable seeded/demo data:

- known partner lists
- YC company seed list from a prior scan
- category mappings
- outreach draft templates

Label these honestly in README/dashboard as "seeded watchlist" or "planned integration".

## Scoring scaffold

Keep the existing model:

```text
score = source_weight * recency_multiplier + velocity_bonus
```

Weights:

- direct announcement: 3.0
- partner signal: 2.5
- founder/community signal: 1.8
- portfolio momentum: 1.0

Recency:

- <24h: 1.0
- 24-48h: 0.8
- >48h: 0.5

Velocity:

- same company/category across 2+ sources: +0.5
- repeat signal over time: +0.25 to +1.0 depending on count

Threshold:

- surface if score >= 2.0

## Tomorrow build checklist

### Must ship

- [ ] Website loads from public URL
- [ ] `/health` returns OK
- [ ] Dashboard has clear LAUNCH/MEMOSONI positioning
- [ ] At least three real source calls are running
- [ ] SQLite stores signals and run history
- [ ] Email form sends report to typed email
- [ ] README includes public URL and GitHub repo
- [ ] Secrets are not committed
- [ ] Repo is pushed

### Nice to have

- [ ] Last scan timestamp visible
- [ ] Source coverage panel
- [ ] Historical signal count / repeat signal badge
- [ ] Railway deploy docs tested
- [ ] One-click manual refresh route protected or omitted

### Do not do unless everything else is done

- [ ] X API integration
- [ ] LinkedIn integration
- [ ] Crunchbase integration
- [ ] authentication/login
- [ ] dashboard redesign from scratch

## Final submission framing

Use this language:

"I built MEMOSONI, a sourcing ops agent for LAUNCH. It monitors public signals from Sequoia, a16z, and Y Combinator, stores and scores emerging company signals, then generates a real-time deal-flow brief. The demo dashboard shows the live sourcing funnel, and users can email themselves the current report from the site."

## Success definition

The demo is successful if someone at LAUNCH can:

1. Open the link.
2. Understand what the agent does within 10 seconds.
3. See believable live deal-flow output.
4. Enter an email and receive a report.
5. Open the GitHub repo and see a real, organized build.
