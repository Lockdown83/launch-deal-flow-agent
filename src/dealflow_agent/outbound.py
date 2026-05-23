from __future__ import annotations

from .models import Opportunity, OutboundDraft

# Templated outreach generation. NO LLM, NO network, NO API keys — stdlib only.
# CRITICAL: nothing here sends. Every draft is returned with status="queued" and a
# to_hint that makes clear a human still has to act. Sending is gated on approval.

TO_HINT = "Founder — via company site / LinkedIn (not auto-sent)"

# Opening lines, rotated so a batch of drafts doesn't read identically.
# Each takes the company name.
_OPENERS = (
    "I run point on sourcing at LAUNCH (Jason Calacanis / This Week in Startups), and {company} keeps coming up on our radar.",
    "Quick note from the LAUNCH team — {company} has been popping up in places we watch closely.",
    "I source for LAUNCH (TWiST / Jason Calacanis), and I've been tracking {company} for a little while now.",
    "We pay attention to early signals at LAUNCH, and {company} is one of the names I keep circling back to.",
    "Reaching out from LAUNCH (Jason Calacanis's firm) — {company} caught our attention before most of the noise hit.",
)

# Soft asks, rotated alongside openers.
_ASKS = (
    "Worth a quick call to hear how you're thinking about it? Happy to keep it low-key.",
    "Would love 20 minutes to learn more — and if it fits, get you in front of Jason on the pod.",
    "Open to a short chat? If the timing's right, there could be a spot for you on This Week in Startups.",
    "Mind if we grab time? Even a quick intro call would be useful on our end.",
    "Could we set up a brief call? No deck needed — just want to understand what you're building.",
)


def _focus_line(opp: Opportunity) -> str:
    """One sentence on what specifically caught our attention.

    Prefers the analyst's grounded read (why_now / one_liner) when the LLM has run; otherwise
    falls back to the templated category + trigger line.
    """
    why_now = (opp.why_now or "").strip()
    if why_now:
        if why_now[-1] not in ".!?":
            why_now += "."
        return f"What stood out: {why_now[0].lower() + why_now[1:]}"

    one_liner = (opp.one_liner or "").strip().rstrip(".")
    if one_liner:
        return (
            f"What stood out: you're building {one_liner[0].lower() + one_liner[1:]}, "
            "and it's exactly the kind of early signal we move on."
        )

    category = (opp.category or "").strip()
    trigger = (opp.trigger or "").strip()
    why = (opp.why_it_matters or "").strip()

    if category and category.lower() != "unknown":
        lead = f"What stood out: you're operating in {category.lower()}"
    else:
        lead = "What stood out: the early signal around what you're building"

    if trigger:
        return f"{lead}, and the {trigger} signal is exactly the kind of thing we move on early."
    if why:
        # Trim the why-it-matters to its first sentence so the note stays tight.
        first = why.split(". ")[0].rstrip(".")
        return f"{lead} — {first[0].lower() + first[1:]}."
    return f"{lead}, which lines up with patterns we're seeing repeat across the best early teams."


def _build_one(opp: Opportunity, index: int) -> OutboundDraft:
    opener = _OPENERS[index % len(_OPENERS)].format(company=opp.company)
    ask = _ASKS[index % len(_ASKS)]
    focus = _focus_line(opp)

    body = f"{opener} {focus} {ask}"

    return OutboundDraft(
        company=opp.company,
        to_hint=TO_HINT,
        subject=f"LAUNCH x {opp.company} — quick chat?",
        body=body,
        score=opp.score,
        status="queued",
    )


def build_drafts(opportunities: list[Opportunity], limit: int = 10) -> list[OutboundDraft]:
    """Turn the top score-sorted opportunities into queued outbound drafts.

    Drafts are templated and never sent — status is always "queued". A human
    reviews and approves before anything goes out.
    """
    drafts: list[OutboundDraft] = []
    for index, opp in enumerate(opportunities[: max(0, limit)]):
        drafts.append(_build_one(opp, index))
    return drafts
