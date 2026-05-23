from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


@dataclass
class Signal:
    company: str
    source: str
    signal_type: str
    title: str
    url: str
    observed_at: datetime
    description: str = ""
    category: str = ""
    stage: str = "Unknown"
    related_sources: list[str] = field(default_factory=list)
    # Optional quantitative payload for "number go up" signals.
    # e.g. metric_label="HN points" / "GitHub stars" / "Form D raise (USD)".
    metric_label: str = ""
    metric_value: float | None = None


@dataclass
class Opportunity:
    company: str
    score: float
    stage: str
    category: str
    sources: list[str]
    trigger: str
    why_it_matters: str
    historical_flag: str
    # --- LLM analyst "brain" output (NVIDIA NIM). All empty on the no-key / fallback path,
    # so every reader (report, dashboard, outbound) must degrade gracefully when blank. ---
    one_liner: str = ""          # what they do, in ~12 words
    verdict: str = ""            # lean-in call: CHASE | WATCH | TRACK (never PASS)
    why_now: str = ""            # the timing thesis, grounded in the actual signal
    key_risk: str = ""           # the single biggest risk / unknown
    conviction_reason: str = ""  # one sentence on why this score is real


@dataclass
class TrendPoint:
    """One day in the deal-flow funnel time series."""

    date: str  # YYYY-MM-DD
    signals: int = 0
    companies: int = 0
    qualified: int = 0


@dataclass
class FunnelMetrics:
    """Top-of-funnel metrics. Everything ladders to net-new qualified deal flow."""

    sources_monitored: int
    signals_ingested: int
    companies_tracked: int
    qualified_deals: int
    outbound_drafted: int
    repeat_signal_companies: int
    top_category: str
    trend: list[TrendPoint] = field(default_factory=list)
    new_companies_this_run: int = 0
    net_new_qualified_7d: int = 0
    # Funnel stage detail: REACH (partners), RESEARCH (enriched/categories), QUALITY (score dist).
    partners_tracked: int = 0
    enriched_companies: int = 0
    categories_covered: int = 0
    score_buckets: list[int] = field(default_factory=list)  # counts per conviction bin
    capital_surfaced: float = 0.0  # summed Form D offering amounts (USD) seen this run


@dataclass
class OutboundDraft:
    """A drafted, queued outreach. Never auto-sent — gated on human approval."""

    company: str
    to_hint: str  # where the founder would be reached, e.g. "via company site / LinkedIn"
    subject: str
    body: str
    score: float = 0.0
    status: str = "queued"  # always queued; sending is intentionally gated


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_rss_date(value: str | None) -> datetime:
    if not value:
        return now_utc()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return now_utc()
