# LAUNCH Deal Flow Agent

MVP research agent for identifying investment opportunities from Sequoia, a16z, and Y Combinator signals.

Goal:
- Track public Sequoia, a16z, and YC signals.
- Score opportunities using the LAUNCH signal hierarchy.
- Generate a deal-flow brief.
- Send the brief via Gmail SMTP.
- Keep everything in a Git repo so the build can be demoed and referenced.

## Current MVP sources

Implemented now:
- Sequoia RSS / official announcements
- a16z public news/content page
- YC blog RSS
- YC company directory seed list from the first research scan
- Hacker News Algolia API for founder/community validation

Planned integrations:
- X/Twitter partner search
- Crunchbase wrapper
- Exa.ai wrapper
- LinkedIn/public partner activity where permitted
- portfolio hiring / GitHub / launch momentum

## Scoring model

Score = weight × recency + velocity bonus

Weights:
- Direct announcements: 3.0x
- Partner signals: 2.5x
- Founder/community signals: 1.8x

Recency:
- < 24h: 1.0
- 24-48h: 0.8
- > 48h: 0.5

Velocity bonus:
- Same company/category across 2+ sources: +0.5

Surface threshold:
- Composite score > 2.0

## Setup

1. Create env file:

   cp .env.example .env

2. Install the local package in editable mode:

   python3 -m pip install -e .

3. Edit `.env` and add Gmail SMTP credentials.

Important: Gmail requires an App Password, not your normal Gmail password.

Google account -> Security -> 2-Step Verification -> App passwords.

4. Run a research report locally:

   python3 -m dealflow_agent.run_daily --no-email

5. Send a Gmail test email:

   python3 -m dealflow_agent.send_test_email

6. Run and email the full brief:

   python3 -m dealflow_agent.run_daily --email

## Repo structure

src/dealflow_agent/
- config.py: env/config loading
- emailer.py: Gmail SMTP provider
- sources.py: public signal collection
- scoring.py: scoring model
- report.py: LAUNCH brief formatting
- run_daily.py: end-to-end pipeline
- send_test_email.py: sends `test` email

reports/
- generated deal-flow reports are written here but ignored by Git

## Demo narrative

This repo demonstrates the MVP build path:

1. Start with email delivery validation.
2. Add public signal ingestion for Sequoia/a16z/YC.
3. Score and rank opportunities.
4. Produce a LAUNCH-formatted brief.
5. Email the brief to the operator.
6. Expand with X, Crunchbase, Exa, hiring, GitHub, and portfolio momentum sources.
