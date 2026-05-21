from __future__ import annotations

from datetime import datetime, timezone

from .models import Opportunity


def format_report(opportunities: list[Opportunity]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("LAUNCH Deal Flow Brief")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("Mission: Identify investment opportunities from Sequoia, a16z, and Y Combinator signals.")
    lines.append("")
    if not opportunities:
        lines.append("No opportunities scored above threshold in this run.")
        return "\n".join(lines)

    lines.append("Top opportunities")
    lines.append("")
    for idx, opp in enumerate(opportunities, start=1):
        lines.append(f"{idx}. {opp.company}")
        lines.append(f"   Composite score: {opp.score}")
        lines.append(f"   Estimated deal stage: {opp.stage}")
        lines.append(f"   Category: {opp.category}")
        lines.append(f"   Signal source: {opp.trigger}")
        lines.append(f"   Why this matters: {opp.why_it_matters}")
        lines.append(f"   When system would have flagged it: {opp.historical_flag}")
        lines.append("   Supporting sources:")
        for source in opp.sources[:4]:
            lines.append(f"   - {source}")
        lines.append("")

    lines.append("Recommended LAUNCH next actions")
    lines.append("- Prioritize founder outreach for top-scoring pre-seed/seed companies.")
    lines.append("- Invite the strongest founders to LAUNCH for a podcast/demo conversation.")
    lines.append("- Add partner X/Twitter signals, Crunchbase, and Exa wrappers as the next data sources.")
    lines.append("- Maintain a persistent watchlist so repeated signals increase score over time.")
    return "\n".join(lines)
