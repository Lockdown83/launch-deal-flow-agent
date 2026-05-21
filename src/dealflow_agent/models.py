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
