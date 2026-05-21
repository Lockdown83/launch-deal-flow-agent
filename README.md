# LAUNCH Deal Flow Agent

This project is part of my application to LAUNCH VC.

I am building an app/agent that tracks Sequoia, a16z, and Y Combinator to understand:

- What they are investing in
- What their partners are talking about on X/Twitter and LinkedIn
- What their portfolio startups are announcing, launching, hiring for, or discussing
- Which themes and companies may represent emerging investment opportunities

The goal is to demonstrate my ability to build an ops pipeline for startup sourcing using agentic engineering: automated signal collection, scoring, reporting, and outbound delivery.

## Product thesis

Top venture firms leave public breadcrumbs before, during, and after markets form. These signals show up across:

- firm investment announcements
- partner posts
- founder/community discussions
- YC company launches
- portfolio company momentum
- hiring, GitHub, product launches, and press

This agent turns those scattered signals into a structured deal-flow brief for LAUNCH.

## MVP capabilities

The current MVP can:

1. Collect public signals from Sequoia, a16z, YC, and Hacker News.
2. Extract companies and themes from those signals.
3. Score opportunities using a weighted signal model.
4. Generate a LAUNCH-style deal-flow brief.
5. Send the report through Gmail SMTP once `.env` is configured.
6. Keep the project Git-tracked so the build process can be reviewed and demoed.

## Current MVP sources

Implemented now:

- Sequoia RSS / official announcements
- a16z public news/content page
- YC blog RSS
- YC startup directory seed list from the first research scan
- Hacker News Algolia API for founder/community validation

Planned integrations:

- X/Twitter partner search
- LinkedIn partner activity where permitted
- Crunchbase wrapper
- Exa.ai wrapper
- portfolio hiring velocity
- GitHub activity
- Product Hunt / launch signals
- company blog and press-release monitoring

## Signal hierarchy

The agent is designed around this confidence hierarchy:

1. Partner signals within 48 hours
   - Sequoia: Roelof Botha, Pat Grady, Alfred Lin
   - a16z: Marc Andreessen, Ben Horowitz, Martin Casado
   - YC: Paul Graham, Garry Tan
2. Direct announcements
   - Crunchbase
   - firm announcements
   - press releases
3. Founder/community signals
   - Hacker News
   - GitHub
   - launch communities
4. Portfolio momentum
   - hiring
   - commits
   - launches
   - product updates

## Scoring model

Score = weight × recency + velocity bonus

Weights:

- Direct announcements: 3.0x
- Partner signals: 2.5x
- Founder/community signals: 1.8x
- Portfolio momentum: 1.0x

Recency:

- < 24h: 1.0
- 24-48h: 0.8
- > 48h: 0.5

Velocity bonus:

- Same company/category across 2+ sources: +0.5

Surface threshold:

- Composite score > 2.0

## Report output

For each opportunity, the report includes:

- Company/founder name
- Composite score
- Signal source
- Estimated deal stage
- Why this matters
- When the system would have flagged it
- Supporting source links
- Recommended LAUNCH action

## Setup

1. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

2. Install the local package in editable mode:

   ```bash
   python3 -m pip install -e .
   ```

3. Edit `.env` and add Gmail SMTP credentials.

   Gmail requires an App Password, not your normal Gmail password.

   Google account -> Security -> 2-Step Verification -> App passwords

   Required values:

   ```bash
   GMAIL_USER=your_gmail_address@gmail.com
   GMAIL_APP_PASSWORD=your_16_character_app_password
   EMAIL_TO=andrewdimaulozx@gmail.com
   EMAIL_FROM=your_gmail_address@gmail.com
   MIN_SCORE=2.0
   ```

## Commands

Run a research report locally without email:

```bash
make report
```

Send a Gmail test email with subject/body `test`:

```bash
make test-email
```

Run the full pipeline and email the brief:

```bash
make email
```

Equivalent Python commands:

```bash
PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email
PYTHONPATH=src python3 -m dealflow_agent.send_test_email
PYTHONPATH=src python3 -m dealflow_agent.run_daily --email
```

## Repo structure

```text
src/dealflow_agent/
  config.py           env/config loading
  emailer.py          Gmail SMTP provider
  models.py           signal/opportunity data models
  sources.py          public signal collection
  scoring.py          scoring model
  report.py           LAUNCH brief formatting
  run_daily.py        end-to-end pipeline
  send_test_email.py  sends `test` email

reports/
  generated deal-flow reports are written here but ignored by Git
```

## Demo narrative for LAUNCH

This repo demonstrates the MVP build path:

1. Start with email delivery validation.
2. Add public signal ingestion for Sequoia, a16z, and YC.
3. Normalize those raw signals into structured `Signal` objects.
4. Score opportunities using a repeatable sourcing model.
5. Produce a LAUNCH-formatted deal-flow brief.
6. Email the brief to the operator.
7. Expand the pipeline with X, LinkedIn, Crunchbase, Exa, hiring, GitHub, and portfolio momentum sources.

The broader idea is to build an automated sourcing operations pipeline: one that continuously monitors the market, highlights high-signal startups, and gives LAUNCH a repeatable way to discover founders and categories earlier.

## Current status

Built:

- Git-tracked Python MVP
- public-source signal collection
- opportunity scoring
- report generation
- Gmail SMTP integration scaffold
- README/demo context

Not yet built:

- authenticated X/Twitter search
- LinkedIn monitoring
- Crunchbase/Exa wrappers
- persistent database/watchlist
- scheduler
- dashboard

## Remote repo

GitHub:

https://github.com/Lockdown83/launch-deal-flow-agent
