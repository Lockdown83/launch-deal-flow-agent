from __future__ import annotations

import html
import re
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


# ---------------------------------------------------------------------------
# HTML brief — the clean, email-client-safe version reviewers receive in their inbox.
# Inline styles + table layout (email clients ignore <style>/external CSS). Light/prestige
# look, NOT the arcade theme (which doesn't render well in mail). Degrades gracefully when
# the LLM fields are empty.
# ---------------------------------------------------------------------------

_SRC_RE = re.compile(r"^(?P<label>.*) \((?P<url>https?://[^)]+)\)\s*$")

# verdict -> (text color, background tint) — muted, professional pills for email.
_VERDICT_PILL = {
    "CHASE": ("#0b6b34", "#e3f4ea"),
    "WATCH": ("#9a6700", "#fdf3da"),
    "TRACK": ("#0b5cad", "#e6f0fb"),
}


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _parse_source(raw: str) -> tuple[str, str | None]:
    match = _SRC_RE.match(raw.strip())
    if match:
        return match.group("label").strip(), match.group("url").strip()
    return raw.strip(), None


def _verdict_pill_html(verdict: str) -> str:
    v = (verdict or "").strip().upper()
    if v not in _VERDICT_PILL:
        return ""
    fg, bg = _VERDICT_PILL[v]
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:11px;background:{bg};'
        f'color:{fg};font-size:11px;font-weight:700;letter-spacing:.5px;">{v}</span>'
    )


def _deal_html(idx: int, opp: Opportunity) -> str:
    def row(label: str, value: str) -> str:
        if not value:
            return ""
        return (
            '<tr><td style="padding:2px 0;color:#6b7280;font-size:12px;width:86px;'
            'vertical-align:top;font-weight:600;">' + _esc(label) + '</td>'
            '<td style="padding:2px 0;color:#1f2937;font-size:14px;line-height:1.5;">'
            + _esc(value) + '</td></tr>'
        )

    body = ""
    if opp.one_liner:
        body += row("What", opp.one_liner)
    if opp.why_now:
        body += row("Why now", opp.why_now)
    elif not opp.one_liner:
        body += row("Why", opp.why_it_matters)  # fallback (no-LLM path)
    if opp.key_risk:
        body += row("Key risk", opp.key_risk)
    if opp.conviction_reason:
        body += row("Conviction", opp.conviction_reason)
    if opp.trigger:
        body += row("Signal", opp.trigger)

    chips = []
    for raw in opp.sources[:4]:
        label, url = _parse_source(raw)
        if url:
            chips.append(
                f'<a href="{_esc(url)}" style="color:#0b5cad;text-decoration:none;">{_esc(label)}</a>'
            )
        else:
            chips.append(f'<span style="color:#6b7280;">{_esc(label)}</span>')
    src_html = ' &nbsp;·&nbsp; '.join(chips)

    sub = _esc(opp.category)
    if opp.stage and opp.stage != "Unknown":
        sub += " · " + _esc(opp.stage)
    pill = _verdict_pill_html(opp.verdict)

    return (
        '<tr><td style="padding:16px 0;border-top:1px solid #eceef1;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:16px;font-weight:700;color:#111827;">{idx}. {_esc(opp.company)}'
        f'{(" &nbsp;" + pill) if pill else ""}</td>'
        f'<td align="right" style="font-size:15px;font-weight:700;color:#111827;'
        f'font-family:ui-monospace,Menlo,monospace;">{opp.score:.1f}</td></tr></table>'
        f'<div style="font-size:12px;color:#6b7280;padding:2px 0 6px;">{sub}</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0">{body}</table>'
        f'<div style="margin-top:8px;font-size:12px;">{src_html}</div>'
        '</td></tr>'
    )


def format_report_html(opportunities: list[Opportunity], editor_note: str = "") -> str:
    """Clean, inline-styled HTML brief for email delivery (the version reviewers read)."""
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    deals = "".join(_deal_html(i, o) for i, o in enumerate(opportunities[:12], start=1)) or (
        '<tr><td style="padding:16px 0;color:#6b7280;font-size:14px;">'
        'No opportunities cleared the threshold this run.</td></tr>'
    )
    editor_block = ""
    if editor_note.strip():
        editor_block = (
            '<tr><td style="padding:14px 16px;background:#fff7ed;border:1px solid #fed7aa;'
            'border-radius:10px;"><div style="font-size:11px;font-weight:700;letter-spacing:1px;'
            'color:#c2410c;text-transform:uppercase;">What matters this week</div>'
            '<div style="font-size:14px;color:#3a2a1a;line-height:1.55;margin-top:6px;">'
            + _esc(editor_note) + '</div></td></tr><tr><td style="height:10px;"></td></tr>'
        )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f4f5f7;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 12px;">'
        '<tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;'
        'border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;\">"
        '<tr><td style="background:#0a0a0f;padding:20px 24px;">'
        '<span style="color:#E8923C;font-size:18px;font-weight:800;letter-spacing:1px;">LAUNCHY</span>'
        '<span style="color:#9ca3af;font-size:13px;"> &nbsp;&#9658;&nbsp; Deal Flow Brief</span>'
        f'<div style="color:#6b7280;font-size:12px;margin-top:4px;">{now} &nbsp;·&nbsp; '
        '<a href="https://www.memosoni.com" style="color:#9ca3af;">www.memosoni.com</a></div></td></tr>'
        '<tr><td style="padding:20px 24px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0">{editor_block}</table>'
        '<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:#9ca3af;'
        'text-transform:uppercase;margin:2px 0 0;">Top opportunities</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0">{deals}</table></td></tr>'
        '<tr><td style="padding:16px 24px;background:#fafafa;border-top:1px solid #eceef1;'
        'color:#9ca3af;font-size:11px;line-height:1.5;">'
        'Generated by LAUNCHY from live public signals — Sequoia, a16z, YC, GitHub, SEC EDGAR, '
        'Hacker News. Companies are ranked by cross-source convergence; the verdict and notes are '
        'written by an LLM analyst. Outbound drafts are queued for human review — nothing is auto-sent.'
        '</td></tr></table></td></tr></table></body></html>'
    )
