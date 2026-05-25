from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .models import Opportunity, Signal

WEIGHTS = {
    "direct_announcement": 3.0,
    "partner_signal": 2.5,
    "founder_community": 1.8,
    "portfolio_momentum": 1.0,
}


def recency_multiplier(observed_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (now - observed_at).total_seconds() / 3600)
    if age_hours < 24:
        return 1.0
    if age_hours <= 48:
        return 0.8
    return 0.5


def why_it_matters(company: str, category: str) -> str:
    if "agent infrastructure" in category.lower():
        return (
            f"{company} sits in the AI-agent infrastructure layer: monitoring, verification, "
            "context, evals, or model-improvement tooling. This overlaps with repeated Sequoia/YC signals."
        )
    if "energy" in category.lower():
        return (
            f"{company} targets energy/grid workflows, a category pulled forward by AI data-center demand, "
            "electrification, and infrastructure constraints."
        )
    if "fintech" in category.lower():
        return (
            f"{company} maps to financial infrastructure, stablecoin/payment rails, or regulated workflow automation, "
            "an active area across a16z and YC."
        )
    if "vertical" in category.lower():
        return (
            f"{company} looks like a vertical AI operator, replacing service labor in a narrow, painful workflow."
        )
    return (
        f"{company} is associated with current Sequoia/a16z/YC public signals and should be investigated for "
        "early category formation or founder momentum."
    )


def score_signals(signals: list[Signal], min_score: float = 2.0) -> list[Opportunity]:
    by_company: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        by_company[signal.company].append(signal)

    opportunities: list[Opportunity] = []
    now = datetime.now(timezone.utc)

    for company, company_signals in by_company.items():
        score = 0.0
        sources = []
        categories = []
        best_by_type: dict[str, float] = {}
        for signal in company_signals:
            weight = WEIGHTS.get(signal.signal_type, 1.0)
            signal_score = weight * recency_multiplier(signal.observed_at, now)
            best_by_type[signal.signal_type] = max(best_by_type.get(signal.signal_type, 0.0), signal_score)
            sources.append(f"{signal.source}: {signal.title} ({signal.url})")
            if signal.category:
                categories.append(signal.category)

        score += sum(best_by_type.values())

        unique_source_names = {signal.source for signal in company_signals}
        if len(unique_source_names) >= 2:
            score += 0.5

        # Category velocity: agent infrastructure and vertical AI are recurring across the source set.
        category = categories[0] if categories else "Unknown"
        if any(term in category.lower() for term in ["agent", "energy", "fintech", "vertical"]):
            score += 0.5

        if score < min_score:
            continue

        latest = max(company_signals, key=lambda item: item.observed_at)
        historical_flag = latest.observed_at.strftime("%Y-%m-%d %H:%M UTC")
        # Trigger = the most AUTHORITATIVE signal, not the most recent. Rank by signal
        # weight (direct_announcement > partner_signal > founder_community >
        # portfolio_momentum), breaking ties by recency (newer wins). A weak, recent
        # HN post should never out-display a strong Sequoia/a16z/YC/EDGAR/GitHub signal.
        best = max(
            company_signals,
            key=lambda item: (WEIGHTS.get(item.signal_type, 1.0), item.observed_at),
        )
        opportunities.append(
            Opportunity(
                company=company,
                score=round(score, 2),
                stage=latest.stage,
                category=category,
                sources=sources,
                trigger=f"{best.source}: {best.title}",
                why_it_matters=why_it_matters(company, category),
                historical_flag=historical_flag,
            )
        )

    return sorted(opportunities, key=lambda item: item.score, reverse=True)
