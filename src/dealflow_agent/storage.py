from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import REPO_ROOT
from .models import Opportunity, Signal, TrendPoint, parse_rss_date

DB_PATH = REPO_ROOT / "data" / "dealflow.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT NOT NULL,
    source        TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    observed_at   TEXT NOT NULL,
    description   TEXT DEFAULT '',
    category      TEXT DEFAULT '',
    stage         TEXT DEFAULT '',
    metric_label  TEXT DEFAULT '',
    metric_value  REAL,
    first_seen    TEXT NOT NULL,
    run_id        INTEGER,
    UNIQUE(source, url, title)
);

CREATE TABLE IF NOT EXISTS runs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at             TEXT NOT NULL,
    sources_monitored  INTEGER DEFAULT 0,
    signals_collected  INTEGER DEFAULT 0,
    companies_tracked  INTEGER DEFAULT 0,
    qualified_deals    INTEGER DEFAULT 0,
    new_signals        INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_signals_observed ON signals(observed_at);
CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def save_run(
    signals: list[Signal],
    opportunities: list[Opportunity],
    sources_monitored: int,
) -> dict:
    """Persist a run: insert the run row, upsert signals, return run stats incl. new-signal count."""
    now = datetime.now(timezone.utc)
    companies = sorted({s.company for s in signals})
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (ran_at, sources_monitored, signals_collected, "
            "companies_tracked, qualified_deals) VALUES (?, ?, ?, ?, ?)",
            (_iso(now), sources_monitored, len(signals), len(companies), len(opportunities)),
        )
        run_id = cur.lastrowid
        new_signals = 0
        for s in signals:
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO signals (company, source, signal_type, title, url, "
                "observed_at, description, category, stage, metric_label, metric_value, "
                "first_seen, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.company, s.source, s.signal_type, s.title, s.url, _iso(s.observed_at),
                    s.description, s.category, s.stage, s.metric_label, s.metric_value,
                    _iso(now), run_id,
                ),
            )
            if conn.total_changes > before:
                new_signals += 1
        conn.execute("UPDATE runs SET new_signals = ? WHERE id = ?", (new_signals, run_id))
    return {"run_id": run_id, "new_signals": new_signals, "companies": len(companies)}


def all_signals() -> list[Signal]:
    """Every signal ever persisted — used for trend backfill across the full history."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM signals ORDER BY observed_at").fetchall()
    return [
        Signal(
            company=r["company"],
            source=r["source"],
            signal_type=r["signal_type"],
            title=r["title"],
            url=r["url"],
            observed_at=parse_rss_date(r["observed_at"]),
            description=r["description"] or "",
            category=r["category"] or "",
            stage=r["stage"] or "Unknown",
            metric_label=r["metric_label"] or "",
            metric_value=r["metric_value"],
        )
        for r in rows
    ]


def run_history(limit: int = 60) -> list[dict]:
    """Recent runs, oldest first — the live 'number go up' series from real executions."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY ran_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def daily_trend_from_signals(signals: list[Signal], qualified_companies: set[str]) -> list[TrendPoint]:
    """Backfill a real time series by bucketing signals on their actual observed_at date."""
    buckets: dict[str, dict] = {}
    for s in signals:
        day = s.observed_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        b = buckets.setdefault(day, {"signals": 0, "companies": set(), "qualified": set()})
        b["signals"] += 1
        b["companies"].add(s.company)
        if s.company in qualified_companies:
            b["qualified"].add(s.company)
    return [
        TrendPoint(
            date=day,
            signals=b["signals"],
            companies=len(b["companies"]),
            qualified=len(b["qualified"]),
        )
        for day, b in sorted(buckets.items())
    ]
