from __future__ import annotations

from collections import Counter
from datetime import timedelta

from .models import FunnelMetrics, Opportunity, Signal, TrendPoint, now_utc
from .storage import all_signals, daily_trend_from_signals

# How many trailing days of trend to keep on the dashboard.
_TREND_DAYS = 30
# Window for the net-new-qualified north-star metric.
_NET_NEW_WINDOW_DAYS = 7

# Curated partner watchlist (REACH stage). These are the partners whose firms' public
# signals the agent monitors; partner social tracking (X/LinkedIn) is on the roadmap.
PARTNERS = [
    # Sequoia
    "Roelof Botha", "Pat Grady", "Alfred Lin", "Andrew Reed",
    # a16z
    "Marc Andreessen", "Ben Horowitz", "Martin Casado", "Sarah Wang",
    # Y Combinator
    "Paul Graham", "Garry Tan",
]

# Conviction-score histogram bins for the QUALITY stage: [2-2.5, 2.5-3, 3-3.5, 3.5-4, 4+].
_SCORE_BIN_EDGES = [2.0, 2.5, 3.0, 3.5, 4.0]


def _score_buckets(opportunities: list[Opportunity]) -> list[int]:
    """Histogram of conviction scores into fixed bins (last bin is open-ended 4+)."""
    buckets = [0] * (len(_SCORE_BIN_EDGES))  # 4 interior + 1 open-ended top
    for o in opportunities:
        placed = False
        for i in range(len(_SCORE_BIN_EDGES) - 1):
            if _SCORE_BIN_EDGES[i] <= o.score < _SCORE_BIN_EDGES[i + 1]:
                buckets[i] += 1
                placed = True
                break
        if not placed and o.score >= _SCORE_BIN_EDGES[-1]:
            buckets[-1] += 1
    return buckets


def _signal_key(s: Signal) -> tuple[str, str, str]:
    """Dedupe key mirroring the storage UNIQUE(source, url, title) constraint."""
    return (s.source, s.url, s.title)


def _load_history() -> list[Signal]:
    """Full persisted signal history; empty list if the DB is missing/unavailable."""
    try:
        return all_signals()
    except Exception:
        return []


def build_metrics(
    signals: list[Signal],
    opportunities: list[Opportunity],
    sources_monitored: int,
    outbound_count: int,
) -> FunnelMetrics:
    """Compute the deal-flow funnel metrics that drive the dashboard.

    Everything ladders to one north-star: net-new qualified deal flow.
    Robust to an empty/missing DB on first run.
    """
    qualified_companies = {o.company for o in opportunities}

    # --- Top-of-funnel counts (from the current run's signals) ---
    companies_tracked = len({s.company for s in signals})

    # Companies appearing in 2+ DISTINCT sources => rising conviction.
    sources_by_company: dict[str, set[str]] = {}
    types_by_company: dict[str, set[str]] = {}
    for s in signals:
        sources_by_company.setdefault(s.company, set()).add(s.source)
        types_by_company.setdefault(s.company, set()).add(s.signal_type)
    repeat_signal_companies = sum(1 for srcs in sources_by_company.values() if len(srcs) >= 2)

    # RESEARCH stage: companies confirmed across 2+ signal TYPES (e.g. firm announcement +
    # community/traction) are "enriched"; categories covered = distinct sectors seen.
    enriched_companies = sum(1 for types in types_by_company.values() if len(types) >= 2)
    categories_covered = len({s.category for s in signals if s.category})

    # Real capital surfaced: sum the Form D offering amounts (USD) the sourcing layer attached
    # as metric_value (metric_label "Form D offering (USD)"). Honest — not regex-scraped from text.
    capital_surfaced = sum(
        s.metric_value
        for s in signals
        if s.metric_value and "usd" in (s.metric_label or "").lower()
    )

    # --- Top category: prefer opportunities, fall back to signals ---
    opp_cats = Counter(o.category for o in opportunities if o.category)
    if opp_cats:
        top_category = opp_cats.most_common(1)[0][0]
    else:
        sig_cats = Counter(s.category for s in signals if s.category)
        top_category = sig_cats.most_common(1)[0][0] if sig_cats else ""

    # --- Trend backfill from full history, merged with current signals ---
    history = _load_history()
    if history:
        merged: dict[tuple[str, str, str], Signal] = {}
        for s in history:
            merged[_signal_key(s)] = s
        for s in signals:  # current run wins on collision (freshest)
            merged[_signal_key(s)] = s
        trend_signals = list(merged.values())
    else:
        # First run / empty DB: backfill from the current signals only.
        trend_signals = list(signals)

    full_trend = daily_trend_from_signals(trend_signals, qualified_companies)
    trend: list[TrendPoint] = full_trend[-_TREND_DAYS:] if len(full_trend) > _TREND_DAYS else full_trend

    # --- New companies this run: not present in prior persisted history ---
    if history:
        prior_companies = {s.company for s in history}
        current_companies = {s.company for s in signals}
        new_companies_this_run = len(current_companies - prior_companies)
    else:
        new_companies_this_run = companies_tracked

    # --- Net-new qualified in the last N days ---
    # A qualified company's LATEST observed signal must be within the window.
    cutoff = now_utc() - timedelta(days=_NET_NEW_WINDOW_DAYS)
    latest_by_company: dict[str, object] = {}
    for s in trend_signals:
        prev = latest_by_company.get(s.company)
        if prev is None or s.observed_at > prev:  # type: ignore[operator]
            latest_by_company[s.company] = s.observed_at
    net_new_qualified_7d = sum(
        1
        for company in qualified_companies
        if (latest := latest_by_company.get(company)) is not None and latest >= cutoff  # type: ignore[operator]
    )

    return FunnelMetrics(
        sources_monitored=sources_monitored,
        signals_ingested=len(signals),
        companies_tracked=companies_tracked,
        qualified_deals=len(opportunities),
        outbound_drafted=outbound_count,
        repeat_signal_companies=repeat_signal_companies,
        top_category=top_category,
        trend=trend,
        new_companies_this_run=new_companies_this_run,
        net_new_qualified_7d=net_new_qualified_7d,
        partners_tracked=len(PARTNERS),
        enriched_companies=enriched_companies,
        categories_covered=categories_covered,
        score_buckets=_score_buckets(opportunities),
        capital_surfaced=capital_surfaced,
    )
