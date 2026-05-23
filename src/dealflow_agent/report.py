from __future__ import annotations

from datetime import datetime, timezone

from .models import Opportunity


def _deal_block(idx: int, opp: Opportunity) -> list[str]:
    """One opportunity, rendered as a scannable analyst memo. Degrades when LLM fields are blank."""
    verdict = f"[{opp.verdict}] " if opp.verdict else ""
    head = f"{verdict}{idx}. {opp.company}  ·  score {opp.score}  ·  {opp.category}"
    lines = [head]

    if opp.one_liner:
        lines.append(f"   What they do: {opp.one_liner}")
    if opp.why_now:
        lines.append(f"   Why now: {opp.why_now}")
    else:
        # Fallback path (no LLM): the templated rationale carries the "why".
        lines.append(f"   Why this matters: {opp.why_it_matters}")
    if opp.key_risk:
        lines.append(f"   Key risk: {opp.key_risk}")
    if opp.conviction_reason:
        lines.append(f"   Conviction: {opp.conviction_reason}")

    lines.append(f"   Signal: {opp.trigger}")
    lines.append(f"   First seen: {opp.historical_flag}")
    if opp.sources:
        lines.append("   Supporting sources:")
        for source in opp.sources[:4]:
            lines.append(f"   - {source}")
    lines.append("")
    return lines


def _next_actions(opportunities: list[Opportunity]) -> list[str]:
    """A sharp, slate-aware closer. Leads with the CHASE names when the analyst has weighed in."""
    chase = [o.company for o in opportunities if o.verdict == "CHASE"]
    watch = [o.company for o in opportunities if o.verdict == "WATCH"]
    lines = ["How to work this list"]
    if chase:
        lines.append(f"- Chase first: {', '.join(chase[:5])} — reach the founder this week.")
    if watch:
        lines.append(f"- Keep warm: {', '.join(watch[:5])} — re-check on the next signal.")
    if not chase and not watch:
        lines.append("- Prioritize founder outreach for the top-scoring pre-seed/seed companies.")
        lines.append("- Invite the strongest founders to LAUNCH for a podcast/demo conversation.")
    lines.append("- Outbound drafts are queued for review on the dashboard — nothing is auto-sent.")
    return lines


def format_report(opportunities: list[Opportunity], editor_note: str = "") -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = ["LAUNCH Deal Flow Brief", f"Generated: {now}", ""]

    if editor_note.strip():
        lines.append("WHAT MATTERS THIS WEEK")
        lines.append(editor_note.strip())
        lines.append("")
    else:
        lines.append(
            "Mission: Identify investment opportunities from Sequoia, a16z, and Y Combinator signals."
        )
        lines.append("")

    if not opportunities:
        lines.append("No opportunities scored above threshold in this run.")
        return "\n".join(lines)

    lines.append("TOP OPPORTUNITIES")
    lines.append("")
    for idx, opp in enumerate(opportunities, start=1):
        lines.extend(_deal_block(idx, opp))

    lines.extend(_next_actions(opportunities))
    return "\n".join(lines)
