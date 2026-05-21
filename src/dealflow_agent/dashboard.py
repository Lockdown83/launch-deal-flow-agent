from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .models import FunnelMetrics, Opportunity, OutboundDraft, TrendPoint

_SOURCE_RE = re.compile(r"^(?P<label>.*) \((?P<url>https?://[^)]+)\)\s*$")

# ---------------------------------------------------------------------------
# Embedded pixel display font — "Press Start 2P" (SIL Open Font License 1.1).
# Base64-encoded latin-subset woff2 served by Google Fonts, inlined so the
# dashboard is fully self-contained and renders offline with NO external CDN.
# Used for headings, the HUD, labels, and big arcade numbers.
# ---------------------------------------------------------------------------
_PIXEL_FONT_B64 = "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"


def _split_source(raw: str) -> tuple[str, str | None]:
    """Parse a 'Source: Title (url)' string into (label, url)."""
    match = _SOURCE_RE.match(raw.strip())
    if match:
        return match.group("label").strip(), match.group("url").strip()
    return raw.strip(), None


def _score_tier(score: float) -> str:
    if score >= 4.0:
        return "high"
    if score >= 3.0:
        return "mid"
    return "base"


def _fund_value(metrics: FunnelMetrics) -> str:
    """Arcade 'FUND' readout — real capital surfaced (summed Form D offering amounts).

    Uses the actual amounts the sourcing layer attached to signals
    (`metrics.capital_surfaced`), not regex-scraped text. Falls back to a clearly
    labelled 'EST' off qualified deals only when no real dollar figures were seen.
    """
    if metrics.capital_surfaced > 0:
        return _format_money(metrics.capital_surfaced)
    return f"{_format_money(metrics.qualified_deals * 2_500_000.0)} EST"


def _format_money(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def _composite_score(metrics: FunnelMetrics, opportunities: list[Opportunity]) -> int:
    """A points-style roll-up for the HUD SCORE — bigger funnel == higher score."""
    opp_points = int(round(sum(o.score for o in opportunities) * 100))
    funnel_points = (
        metrics.qualified_deals * 500
        + metrics.signals_ingested * 5
        + metrics.companies_tracked * 25
        + metrics.repeat_signal_companies * 250
        + metrics.net_new_qualified_7d * 750
    )
    return opp_points + funnel_points


def _current_level(metrics: FunnelMetrics) -> tuple[int, str]:
    """The HUD's current LVL — furthest funnel stage with activity this run."""
    if metrics.outbound_drafted > 0:
        return 4, "ACTION"
    if metrics.qualified_deals > 0:
        return 3, "QUALITY"
    if metrics.companies_tracked > 0:
        return 2, "RESEARCH"
    return 1, "REACH"


def _source_chips(sources: list[str]) -> str:
    chips: list[str] = []
    for raw in sources[:5]:
        label, url = _split_source(raw)
        text = html.escape(label)
        if url:
            chips.append(
                f'<a class="source-chip" href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noopener">{text}</a>'
            )
        else:
            chips.append(f'<span class="source-chip source-chip--dead">{text}</span>')
    return "\n".join(chips)


def _deal_card(idx: int, opp: Opportunity) -> str:
    tier = _score_tier(opp.score)
    flag = ""
    if opp.historical_flag:
        flag = (
            '<div class="deal-flag"><span class="kicker">Replay</span>'
            f"Would have flagged: {html.escape(opp.historical_flag)}</div>"
        )
    return f"""
    <article class="deal deal--{tier}">
      <div class="deal-rank">P{idx:02d}</div>
      <div class="deal-body">
        <div class="deal-kicker">&#9658; INCOMING DEAL</div>
        <header class="deal-head">
          <h2 class="deal-name">{html.escape(opp.company)}</h2>
          <span class="score score--{tier}">{opp.score:.1f}</span>
        </header>
        <div class="deal-statrow">
          <div class="dstat"><span class="dstat-key">ASK</span><span class="dstat-val">{opp.score:.1f}</span></div>
          <div class="dstat"><span class="dstat-key">VAL</span><span class="dstat-val dstat-val--cat">{html.escape(opp.category)}</span></div>
          <div class="dstat"><span class="dstat-key">RISK</span><span class="dstat-val">{html.escape(opp.stage)}</span></div>
        </div>
        <p class="deal-why">{html.escape(opp.why_it_matters)}</p>
        <div class="deal-trigger"><span class="kicker">Trigger</span>{html.escape(opp.trigger)}</div>
        <div class="deal-sources">
          <span class="kicker">Sources</span>
          <div class="source-chips">{_source_chips(opp.sources)}</div>
        </div>
        {flag}
      </div>
    </article>"""


def _draft_card(draft: OutboundDraft) -> str:
    tier = _score_tier(draft.score)
    score_badge = ""
    if draft.score:
        score_badge = f'<span class="score score--{tier}">{draft.score:.1f}</span>'
    return f"""
    <article class="draft">
      <header class="draft-head">
        <div class="draft-head-left">
          <span class="draft-coin">&#9679;</span>
          <h3 class="draft-company">{html.escape(draft.company)}</h3>
          {score_badge}
        </div>
        <span class="queued-badge">&#128274; QUEUED &middot; PENDING HUMAN APPROVAL (NOT SENT)</span>
      </header>
      <div class="draft-meta"><span class="kicker">To</span>{html.escape(draft.to_hint)}</div>
      <div class="draft-subject"><span class="kicker">Subject</span>{html.escape(draft.subject)}</div>
      <pre class="draft-body">{html.escape(draft.body)}</pre>
    </article>"""


def _spotlight_card(opp: Opportunity) -> str:
    """The #1 deal, blown up — the proof headline above the leaderboard."""
    tier = _score_tier(opp.score)
    return f"""
    <section class="spotlight spotlight--{tier}">
      <div class="spotlight-badge">&#9733; #1 SPOTLIGHT</div>
      <div class="spotlight-head">
        <h3 class="spotlight-name">{html.escape(opp.company)}</h3>
        <span class="score score--{tier}">{opp.score:.1f}</span>
      </div>
      <div class="spotlight-tags">
        <span class="tag tag--category">{html.escape(opp.category)}</span>
        <span class="tag">{html.escape(opp.stage)}</span>
      </div>
      <p class="spotlight-why">{html.escape(opp.why_it_matters)}</p>
      <div class="spotlight-meta"><span class="kicker">Trigger</span>{html.escape(opp.trigger)}</div>
      <div class="spotlight-sources"><span class="kicker">Sources</span>
        <div class="source-chips">{_source_chips(opp.sources)}</div>
      </div>
    </section>"""


def _leaderboard(opportunities: list[Opportunity], limit: int = 8) -> str:
    """Arcade HIGH-SCORES table — the top deals ranked, one glance."""
    rows = [
        '<div class="lb-row lb-head">'
        '<span class="lb-rank">#</span><span class="lb-co">Company</span>'
        '<span class="lb-score">Score</span><span class="lb-cat">Category</span>'
        '<span class="lb-src">Src</span></div>'
    ]
    for i, opp in enumerate(opportunities[:limit], start=1):
        tier = _score_tier(opp.score)
        rows.append(
            f'<div class="lb-row">'
            f'<span class="lb-rank">{i:02d}</span>'
            f'<span class="lb-co">{html.escape(opp.company)}</span>'
            f'<span class="lb-score lb-score--{tier}">{opp.score:.1f}</span>'
            f'<span class="lb-cat">{html.escape(opp.category)}</span>'
            f'<span class="lb-src">{len(opp.sources)}</span>'
            f"</div>"
        )
    return f'<div class="leaderboard">{"".join(rows)}</div>'


def _funnel_stat(value: str, label: str) -> str:
    return (
        f'<div class="fstat"><span class="fstat-value">{html.escape(value)}</span>'
        f'<span class="fstat-label">{html.escape(label)}</span></div>'
    )


def _score_dist_bar(buckets: list[int]) -> str:
    """A tiny CSS bar chart of the conviction-score distribution (QUALITY stage)."""
    labels = ["2.0", "2.5", "3.0", "3.5", "4+"]
    if not buckets or max(buckets) == 0:
        return '<div class="scoredist scoredist--empty">no scored deals yet</div>'
    mx = max(buckets)
    bars = []
    for i, count in enumerate(buckets):
        height = 6 + int(round(34 * count / mx)) if count else 3
        lab = labels[i] if i < len(labels) else ""
        bars.append(
            f'<div class="distbar" title="{count} deal(s) at {lab}">'
            f'<span class="distbar-fill" style="height:{height}px"></span>'
            f'<span class="distbar-lab">{lab}</span></div>'
        )
    return f'<div class="scoredist">{"".join(bars)}</div>'


def _stage(klass: str, level: int, name: str, question: str, body: str) -> str:
    return f"""
      <div class="stage stage--{klass}">
        <div class="stage-head">
          <span class="stage-chip">&#9656; LVL {level} &middot; {name}</span>
          <span class="stage-q">{html.escape(question)}</span>
        </div>
        <div class="stage-stats">{body}</div>
      </div>"""


def _funnel_section(metrics: FunnelMetrics) -> str:
    reach = "".join(
        _funnel_stat(*pair)
        for pair in (
            (str(metrics.sources_monitored), "Sources monitored"),
            (str(metrics.signals_ingested), "Signals ingested"),
            (str(metrics.partners_tracked), "Partners tracked"),
        )
    )
    research = "".join(
        _funnel_stat(*pair)
        for pair in (
            (str(metrics.companies_tracked), "In watchlist"),
            (str(metrics.enriched_companies), "Enriched (2+ sources)"),
            (str(metrics.categories_covered), "Categories covered"),
        )
    )
    quality = (
        _funnel_stat(str(metrics.qualified_deals), "Above threshold")
        + _funnel_stat(str(metrics.repeat_signal_companies), "Repeat-signal cos")
        + f'<div class="fstat fstat--dist"><span class="fstat-label">Score distribution</span>'
        + _score_dist_bar(metrics.score_buckets)
        + "</div>"
    )
    action = (
        _funnel_stat(str(metrics.outbound_drafted), "Drafts generated & queued")
        + f'<div class="fstat"><span class="fstat-value">{metrics.net_new_qualified_7d}</span>'
        + '<span class="fstat-label">Net-new qualified (7d)</span></div>'
    )
    return f"""
    <section class="funnel">
      {_stage("reach", 1, "REACH", "Are we casting wider?", reach)}
      {_stage("research", 2, "RESEARCH", "Do we know more?", research)}
      {_stage("quality", 3, "QUALITY", "Targeting better founders?", quality)}
      {_stage("action", 4, "ACTION", "Are we acting on it?", action)}
    </section>"""


def _sparkline(trend: list[TrendPoint]) -> str:
    """Build a neon-CRT inline-SVG chart of qualified-per-day over a faint grid.

    Pure Python string building; no JS, no external assets. Degrades gracefully
    for empty or single-point trends.
    """
    if not trend:
        return (
            '<div class="trend-empty">&#9658; NO SIGNAL YET &mdash; INSERT COIN. '
            "This is run one; the line starts climbing tomorrow.</div>"
        )

    # Canvas geometry
    width = 860
    height = 200
    pad_l = 16
    pad_r = 16
    pad_t = 18
    pad_b = 34
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    n = len(trend)
    sig_max = max((p.signals for p in trend), default=0)
    qual_max = max((p.qualified for p in trend), default=0)
    y_max = max(sig_max, qual_max, 1)

    def x_for(i: int) -> float:
        if n == 1:
            return pad_l + plot_w / 2
        return pad_l + (plot_w * i) / (n - 1)

    def y_for(v: float) -> float:
        return pad_t + plot_h - (plot_h * v) / y_max

    # Faint CRT grid lines (horizontal)
    grid: list[str] = []
    for g in range(5):
        gy = pad_t + (plot_h * g) / 4
        grid.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" '
            f'y2="{gy:.1f}" class="spark-grid"/>'
        )

    # Signals: soft bars (the "raw intake" volume)
    bar_slot = plot_w / max(n, 1)
    bar_w = max(4.0, min(38.0, bar_slot * 0.5))
    bars: list[str] = []
    for i, p in enumerate(trend):
        cx = x_for(i)
        bx = cx - bar_w / 2
        bh = (plot_h * p.signals) / y_max
        by = pad_t + plot_h - bh
        bars.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
            f'height="{bh:.1f}" rx="1" class="spark-bar"/>'
        )

    # Qualified: bright neon line + filled area + endpoint dot (the "number go up")
    line_pts = [(x_for(i), y_for(p.qualified)) for i, p in enumerate(trend)]
    line_d = " ".join(
        ("M" if i == 0 else "L") + f"{x:.1f} {y:.1f}" for i, (x, y) in enumerate(line_pts)
    )
    baseline = pad_t + plot_h
    if n == 1:
        x0, y0 = line_pts[0]
        area_d = f"M{x0 - 1:.1f} {baseline:.1f} L{x0 - 1:.1f} {y0:.1f} L{x0 + 1:.1f} {y0:.1f} L{x0 + 1:.1f} {baseline:.1f} Z"
    else:
        area_d = (
            f"M{line_pts[0][0]:.1f} {baseline:.1f} "
            + " ".join(f"L{x:.1f} {y:.1f}" for x, y in line_pts)
            + f" L{line_pts[-1][0]:.1f} {baseline:.1f} Z"
        )

    dots: list[str] = []
    last_i = n - 1
    for i, (x, y) in enumerate(line_pts):
        cls = "spark-dot spark-dot--last" if i == last_i else "spark-dot"
        r = 4.5 if i == last_i else 2.6
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" class="{cls}"/>')

    # X axis labels: first, middle-ish, last (avoid crowding)
    label_idx = sorted({0, n // 2, n - 1})
    labels: list[str] = []
    for i in label_idx:
        x = x_for(i)
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        labels.append(
            f'<text x="{x:.1f}" y="{height - 12}" class="spark-axis" '
            f'text-anchor="{anchor}">{html.escape(trend[i].date)}</text>'
        )

    last_qual = trend[-1].qualified
    end_label = ""
    if n >= 1:
        ex, ey = line_pts[-1]
        ey_text = max(ey - 10, pad_t + 10)
        end_label = (
            f'<text x="{ex:.1f}" y="{ey_text:.1f}" class="spark-endlabel" '
            f'text-anchor="end">{last_qual} QUAL</text>'
        )

    svg = f"""<svg viewBox="0 0 {width} {height}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Daily signals and qualified deals trend">
      <defs>
        <linearGradient id="sparkArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#39FF14" stop-opacity="0.30"/>
          <stop offset="100%" stop-color="#39FF14" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <g>{''.join(grid)}</g>
      <g>{''.join(bars)}</g>
      <path d="{area_d}" fill="url(#sparkArea)" stroke="none"/>
      <path d="{line_d}" class="spark-line" fill="none"/>
      <g>{''.join(dots)}</g>
      {end_label}
      <g>{''.join(labels)}</g>
    </svg>"""
    return f'<div class="trend-chart">{svg}</div>'


_CSS = """
@font-face {
  font-family: 'PressStart2P';
  src: url(data:font/woff2;base64,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) format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
:root {
  --bg: #0a0a0f;
  --panel: #11111a;
  --panel-2: #15151f;
  --line: #25253a;
  --text: #e9ebf0;
  --muted: #a6abbb;
  --green: #39FF14;
  --green-soft: #7CFF4F;
  --cyan: #3DD6FF;
  --pink: #FF3D9A;
  --amber: #FFE34D;
  --high: #FF3D9A;
  --mid: #3DD6FF;
  --base: #8b90a0;
  --pixel: 'PressStart2P', "Courier New", ui-monospace, monospace;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14.5px/1.65 var(--mono);
  -webkit-font-smoothing: antialiased;
  position: relative;
}
/* CRT scanline overlay + faint vignette — CSS only, no JS */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  background:
    repeating-linear-gradient(
      to bottom,
      rgba(0,0,0,0.0) 0px,
      rgba(0,0,0,0.0) 2px,
      rgba(0,0,0,0.10) 3px,
      rgba(0,0,0,0.10) 4px
    );
}
body::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9998;
  background: radial-gradient(120% 100% at 50% 0%, rgba(57,255,20,0.04) 0%, rgba(10,10,15,0) 45%),
              radial-gradient(140% 120% at 50% 50%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.32) 100%);
}
.wrap { max-width: 980px; margin: 0 auto; padding: 30px 26px 80px; position: relative; z-index: 1; }

/* GitHub repo link — fixed top-right corner */
.repo-link { position: fixed; top: 16px; right: 16px; z-index: 10000;
  display: inline-flex; align-items: center; gap: 8px; text-decoration: none;
  font-family: var(--mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--text); background: rgba(10,10,15,.82); border: 1px solid rgba(57,255,20,.5);
  border-radius: 12px; padding: 9px 13px; -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px);
  box-shadow: 0 0 18px rgba(57,255,20,.13); transition: border-color .15s ease, box-shadow .15s ease, color .15s ease; }
.repo-link:hover { border-color: var(--green); color: var(--green); box-shadow: 0 0 22px rgba(57,255,20,.3); }
.repo-link svg { display: block; flex: 0 0 auto; }
.repo-link-divider { color: rgba(57,255,20,.45); }
.repo-link-credit { color: var(--green-soft); letter-spacing: .06em; }
@media (max-width: 720px) { .repo-link-credit, .repo-link-divider { display: none; } }
@media (max-width: 560px) { .repo-link .repo-link-text { display: none; } .repo-link { padding: 9px; } }

/* NYSE-style scrolling ticker tape */
.ticker {
  position: relative; background: #050507;
  border: 1px solid rgba(57,255,20,.55); border-radius: 14px;
  box-shadow: 0 0 28px rgba(57,255,20,.16), inset 0 1px 0 rgba(57,255,20,.18);
  overflow: hidden; padding: 13px 0; white-space: nowrap; text-transform: uppercase;
}
/* fade the edges like a real ticker tape */
.ticker::before, .ticker::after { content: ""; position: absolute; top: 0; bottom: 0; width: 56px; z-index: 2; pointer-events: none; }
.ticker::before { left: 0; background: linear-gradient(90deg, #050507, rgba(5,5,7,0)); }
.ticker::after { right: 0; background: linear-gradient(270deg, #050507, rgba(5,5,7,0)); }
.ticker-track { display: inline-block; white-space: nowrap; animation: ticker-scroll 48s linear infinite; will-change: transform; }
.ticker:hover .ticker-track { animation-play-state: paused; }
@keyframes ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.tick { display: inline-flex; align-items: baseline; gap: 8px; padding: 0 2px; }
.tick-k { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; color: var(--muted); }
.tick-sym { font-family: var(--mono); font-size: 12px; letter-spacing: .04em; color: var(--text); }
.tick-v { font-family: var(--pixel); font-size: 12px; font-variant-numeric: tabular-nums; }
.tick-v.amber { color: var(--amber); } .tick-v.pink { color: var(--pink); }
.tick-v.green { color: var(--green); } .tick-v.cyan { color: var(--cyan); } .tick-v.base { color: var(--muted); }
.tick-sep { color: #2a3650; margin: 0 18px; }
@media (prefers-reduced-motion: reduce) { .ticker-track { animation: none; } }

/* Title block */
.brand { font-family: var(--mono); font-size: 11px; letter-spacing: .18em; text-transform: uppercase;
  color: var(--pink); margin: 28px 0 0; }
h1.wordmark {
  font-family: var(--pixel);
  font-size: 38px; line-height: 1.15; margin: 16px 0 14px; letter-spacing: .02em;
  text-transform: uppercase;
  background: linear-gradient(90deg, var(--green) 0%, var(--cyan) 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 16px rgba(57,255,20,.35));
}
.mission { color: var(--muted); max-width: 660px; margin: 0; font-size: 14px; }
.generated { color: #7c8294; font-size: 12px; margin-top: 12px; font-family: var(--mono);
  letter-spacing: .04em; }

/* Section labels — bracketed neon chips */
.section-label {
  display: inline-block;
  font-family: var(--pixel); font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--green); margin: 48px 0 18px;
  border: 1px solid rgba(57,255,20,.5); border-radius: 10px; padding: 9px 14px;
  box-shadow: 0 0 18px rgba(57,255,20,.13); background: rgba(57,255,20,.05);
}
.section-sub { display: block; color: var(--pink); font-family: var(--mono); font-size: 12px;
  letter-spacing: .08em; margin: -8px 0 18px; text-transform: uppercase; }

/* North-star HIGH SCORE hero */
.hero {
  margin: 24px 0 8px;
  background: linear-gradient(135deg, #120016 0%, var(--panel) 65%);
  border: 1px solid rgba(255,61,154,.5);
  border-radius: 18px;
  padding: 32px 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  box-shadow: 0 0 36px rgba(255,61,154,.16), inset 0 1px 0 rgba(255,61,154,.22);
  position: relative;
}
.hero-left { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
.hero-number {
  font-family: var(--pixel); font-size: 64px; line-height: 1; letter-spacing: .01em;
  color: var(--amber); font-variant-numeric: tabular-nums;
  text-shadow: 0 0 18px rgba(255,227,77,.6), 0 0 38px rgba(255,227,77,.3);
}
.hero-meta { display: flex; flex-direction: column; gap: 8px; }
.hero-label { font-family: var(--mono); font-size: 13px; color: var(--text); letter-spacing: .04em;
  text-transform: uppercase; max-width: 320px; line-height: 1.5; }
.hero-sub { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--pink); }
.delta-chip {
  display: inline-flex; align-items: center; gap: 10px;
  background: #04130a; border: 1px solid rgba(57,255,20,.55);
  color: var(--green); font-family: var(--pixel); font-size: 14px;
  padding: 14px 18px; border-radius: 12px; font-variant-numeric: tabular-nums;
  box-shadow: 0 0 22px rgba(57,255,20,.2); text-shadow: 0 0 8px rgba(57,255,20,.5);
}
.delta-chip .arrow { font-size: 12px; }
.delta-chip .delta-sub { font-family: var(--mono); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--green-soft); }

/* Funnel — neon stage boxes */
.funnel { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 8px 0 0; }
.stage { background:
    linear-gradient(180deg, rgba(255,255,255,.03) 0%, rgba(255,255,255,0) 30%), var(--panel);
  border: 1px solid var(--line); border-radius: 16px; padding: 20px 18px; min-width: 0;
  position: relative; }
.stage--reach { border-color: rgba(61,214,255,.55); box-shadow: 0 0 26px rgba(61,214,255,.12), inset 0 1px 0 rgba(61,214,255,.18); }
.stage--research { border-color: rgba(255,227,77,.5); box-shadow: 0 0 26px rgba(255,227,77,.1), inset 0 1px 0 rgba(255,227,77,.16); }
.stage--quality { border-color: rgba(255,61,154,.5); box-shadow: 0 0 26px rgba(255,61,154,.1), inset 0 1px 0 rgba(255,61,154,.16); }
.stage--action { border-color: rgba(57,255,20,.5); box-shadow: 0 0 26px rgba(57,255,20,.1), inset 0 1px 0 rgba(57,255,20,.16); }
.stage-head { margin-bottom: 18px; }
.stage-chip { display: block; font-family: var(--pixel); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }
.stage--reach .stage-chip { color: var(--cyan); }
.stage--research .stage-chip { color: var(--amber); }
.stage--quality .stage-chip { color: var(--pink); }
.stage--action .stage-chip { color: var(--green); }
.stage-q { display: block; font-family: var(--mono); font-size: 12.5px; color: var(--text);
  margin-top: 9px; font-style: italic; opacity: .92; }
.stage-stats { display: flex; flex-direction: column; gap: 16px; }
.fstat { display: flex; flex-direction: column; }
.fstat-value { font-family: var(--pixel); font-size: 19px; letter-spacing: .01em; font-variant-numeric: tabular-nums; color: var(--text); }
.fstat-label { font-family: var(--mono); font-size: 12px; color: var(--muted); margin-top: 7px; }
.fstat--dist .fstat-label { margin-bottom: 8px; }
/* Score-distribution mini bar chart (QUALITY stage) */
.scoredist { display: flex; align-items: flex-end; gap: 7px; height: 48px; }
.scoredist--empty { height: auto; font-family: var(--mono); font-size: 12px; color: var(--muted); }
.distbar { display: flex; flex-direction: column; align-items: center; gap: 5px; }
.distbar-fill { width: 14px; border-radius: 4px 4px 1px 1px;
  background: linear-gradient(180deg, var(--pink), rgba(255,61,154,.35)); display: block; }
.distbar-lab { font-family: var(--mono); font-size: 10px; color: var(--muted); }

/* Trend chart */
.trend-card { background: var(--panel); border: 1px solid rgba(57,255,20,.4); border-radius: 16px;
  padding: 20px 22px 12px; box-shadow: 0 0 26px rgba(57,255,20,.1), inset 0 1px 0 rgba(57,255,20,.14); }
.trend-legend { display: flex; gap: 18px; margin-bottom: 8px; }
.legend-item { display: inline-flex; align-items: center; gap: 7px; color: var(--muted);
  font-family: var(--mono); font-size: 11px; letter-spacing: .04em; text-transform: uppercase; }
.legend-swatch { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
.legend-swatch--bar { background: #2a3650; }
.legend-swatch--line { background: var(--green); box-shadow: 0 0 6px rgba(57,255,20,.7); }
.trend-chart { width: 100%; }
.trend-empty { color: var(--green); padding: 22px 4px; font-size: 13px; font-family: var(--mono);
  letter-spacing: .02em; line-height: 1.7; }
.spark-grid { stroke: #1d2030; stroke-width: 1; }
.spark-bar { fill: #2a3650; }
.spark-line { stroke: var(--green); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round;
  filter: drop-shadow(0 0 4px rgba(57,255,20,.8)); }
.spark-dot { fill: var(--green); }
.spark-dot--last { fill: var(--amber); stroke: var(--green); stroke-width: 3; }
.spark-axis { fill: var(--muted); font-size: 11px; font-family: ui-monospace, Menlo, monospace; }
.spark-endlabel { fill: var(--green); font-size: 11px; font-family: ui-monospace, Menlo, monospace; }

/* INCOMING DEAL cards */
.deal { display: flex; gap: 18px; background: var(--panel); border: 2px solid var(--line);
  border-radius: 10px; padding: 20px 22px; margin-bottom: 16px; transition: box-shadow .15s ease; }
.deal--high { border-color: var(--pink); box-shadow: 0 0 14px rgba(255,61,154,.22); }
.deal--mid { border-color: var(--cyan); box-shadow: 0 0 14px rgba(61,214,255,.18); }
.deal--base { border-color: var(--line); }
.deal-rank { font-family: var(--pixel); font-size: 11px; color: var(--amber); padding-top: 4px;
  min-width: 38px; font-variant-numeric: tabular-nums; text-shadow: 0 0 6px rgba(255,227,77,.5); }
.deal-body { flex: 1; min-width: 0; }
.deal-kicker { font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--pink); margin-bottom: 12px; }
.deal-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.deal-name { font-family: var(--pixel); font-size: 16px; margin: 0; color: #fff; letter-spacing: .01em;
  line-height: 1.4; }
.score { font-family: var(--pixel); font-size: 11px; padding: 7px 11px; border-radius: 9px;
  font-variant-numeric: tabular-nums; flex: 0 0 auto; }
.score--high { background: rgba(255,61,154,.14); color: var(--pink); border: 1px solid var(--pink); box-shadow: 0 0 8px rgba(255,61,154,.4); }
.score--mid { background: rgba(61,214,255,.12); color: var(--cyan); border: 1px solid var(--cyan); box-shadow: 0 0 8px rgba(61,214,255,.35); }
.score--base { background: rgba(139,144,160,.14); color: var(--base); border: 1px solid #3a3f50; }
.deal-statrow { display: flex; gap: 10px; margin: 14px 0; flex-wrap: wrap; }
.dstat { display: flex; flex-direction: column; gap: 5px; background: #050507; border: 1px solid var(--line);
  border-radius: 10px; padding: 9px 13px; min-width: 78px; }
.dstat-key { font-family: var(--mono); font-size: 11px; letter-spacing: .06em; color: var(--muted); text-transform: uppercase; }
.dstat-val { font-family: var(--mono); font-size: 13px; color: var(--green); font-variant-numeric: tabular-nums; }
.dstat-val--cat { color: var(--cyan); }
.deal-why { margin: 0 0 14px; color: #d4d8e2; font-size: 13.5px; line-height: 1.6; }
.kicker { display: inline-block; font-family: var(--mono); font-size: 11px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--pink); margin-right: 10px; }
.deal-trigger { font-size: 13px; color: #b9bdc9; margin-bottom: 12px; }
.deal-sources { margin-bottom: 12px; }
.source-chips { display: inline-flex; flex-wrap: wrap; gap: 8px; vertical-align: top; }
.source-chip { font-size: 12px; color: var(--cyan); text-decoration: none; background: #050507;
  border: 1px solid var(--line); padding: 5px 11px; border-radius: 9px; max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-chip:hover { border-color: var(--cyan); box-shadow: 0 0 8px rgba(61,214,255,.3); }
.source-chip--dead { color: var(--muted); }
.deal-flag { font-size: 12px; color: var(--muted); margin-top: 8px; }

/* Spotlight (#1 deal) + arcade HIGH-SCORES leaderboard */
.spotlight { position: relative; border-radius: 18px; padding: 24px 26px; margin-bottom: 18px;
  background: linear-gradient(180deg, rgba(255,61,154,.06) 0%, rgba(255,61,154,0) 42%), var(--panel);
  border: 1px solid rgba(255,61,154,.5);
  box-shadow: 0 0 30px rgba(255,61,154,.14), inset 0 1px 0 rgba(255,61,154,.2); }
.spotlight--mid { border-color: rgba(61,214,255,.5);
  background: linear-gradient(180deg, rgba(61,214,255,.06) 0%, rgba(61,214,255,0) 42%), var(--panel);
  box-shadow: 0 0 30px rgba(61,214,255,.12), inset 0 1px 0 rgba(61,214,255,.2); }
.spotlight--base { border-color: var(--line); background: var(--panel); box-shadow: none; }
.spotlight-badge { font-family: var(--pixel); font-size: 10px; letter-spacing: .06em; color: var(--amber); text-transform: uppercase; }
.spotlight-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin: 16px 0 4px; }
.spotlight-name { font-family: var(--pixel); font-size: 22px; margin: 0; color: #fff; line-height: 1.35; }
.spotlight-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
.spotlight-why { margin: 0 0 14px; color: #d4d8e2; font-size: 14px; line-height: 1.62; }
.spotlight-meta { font-size: 13px; color: #b9bdc9; margin-bottom: 14px; }
.leaderboard { border: 1px solid var(--line); border-radius: 16px; overflow: hidden; background: var(--panel); }
.lb-row { display: grid; grid-template-columns: 44px 1fr auto 1.1fr 46px; gap: 14px; align-items: center;
  padding: 13px 18px; border-top: 1px solid rgba(255,255,255,.05); }
.lb-row:first-child { border-top: none; }
.lb-head { background: #050507; }
.lb-head span { font-family: var(--mono); font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.lb-row:not(.lb-head):nth-child(even) { background: rgba(255,255,255,.02); }
.lb-rank { font-family: var(--pixel); font-size: 12px; color: var(--amber); font-variant-numeric: tabular-nums; }
.lb-co { font-family: var(--mono); font-size: 14px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lb-score { font-family: var(--pixel); font-size: 13px; font-variant-numeric: tabular-nums; }
.lb-score--high { color: var(--pink); }
.lb-score--mid { color: var(--cyan); }
.lb-score--base { color: var(--muted); }
.lb-cat { font-family: var(--mono); font-size: 12.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lb-src { font-family: var(--mono); font-size: 13px; color: var(--cyan); text-align: right; }

/* Outbound queue — QUEUED arcade cards */
.draft { background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--amber);
  border-radius: 16px; padding: 18px 22px; margin-bottom: 14px; box-shadow: 0 0 18px rgba(255,227,77,.07); }
.draft-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.draft-head-left { display: flex; align-items: center; gap: 12px; }
.draft-coin { color: var(--amber); font-size: 14px; text-shadow: 0 0 8px rgba(255,227,77,.7); }
.draft-company { font-family: var(--pixel); font-size: 14px; margin: 0; color: #fff; letter-spacing: .01em; }
.queued-badge { font-family: var(--mono); font-size: 11px; letter-spacing: .04em; text-transform: uppercase;
  color: var(--amber); background: rgba(255,227,77,.1); border: 1px solid var(--amber);
  padding: 6px 11px; border-radius: 6px; line-height: 1.5; }
.draft-meta, .draft-subject { font-size: 13px; color: #b9bdc9; margin-top: 14px; }
.draft-subject { color: var(--text); font-weight: 600; }
.draft-body { margin: 14px 0 0; padding: 14px 16px; background: #050507; border: 1px solid var(--line);
  border-radius: 8px; color: #cfd3de; font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap; overflow-wrap: anywhere; }
.empty-note { color: var(--green); font-family: var(--mono); font-size: 13px; letter-spacing: .02em;
  line-height: 1.7; padding: 18px 0; }

footer { color: var(--muted); font-size: 12px; margin-top: 48px; text-align: center;
  font-family: var(--mono); letter-spacing: .02em; line-height: 1.8; }

/* LIVE badge + 'get this brief' interactive CTA (web mode only) */
.live-badge { display: inline-flex; align-items: center; gap: 7px; margin-left: 12px;
  font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--green); vertical-align: middle; }
.live-badge::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--green);
  box-shadow: 0 0 8px var(--green); animation: livepulse 1.6s ease-in-out infinite; }
@keyframes livepulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
.cta { margin: 24px 0 8px; border-radius: 18px; padding: 26px 28px;
  background: linear-gradient(180deg, rgba(57,255,20,.07) 0%, rgba(57,255,20,0) 45%), var(--panel);
  border: 1px solid rgba(57,255,20,.5);
  box-shadow: 0 0 30px rgba(57,255,20,.13), inset 0 1px 0 rgba(57,255,20,.2); }
.cta-title { display: block; font-family: var(--pixel); font-size: 14px; color: var(--green); letter-spacing: .03em; line-height: 1.4; }
.cta-sub { display: block; font-family: var(--mono); font-size: 13px; color: var(--muted); margin-top: 11px; }
.cta-form { display: flex; gap: 12px; margin-top: 18px; flex-wrap: wrap; }
.cta-input { flex: 1; min-width: 220px; font-family: var(--mono); font-size: 15px; color: var(--text);
  background: #050507; border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; outline: none; }
.cta-input:focus { border-color: var(--green); box-shadow: 0 0 0 3px rgba(57,255,20,.12); }
.cta-input::placeholder { color: #5a5f70; }
.cta-btn { font-family: var(--pixel); font-size: 12px; letter-spacing: .04em; cursor: pointer;
  color: #04130a; background: var(--green); border: none; border-radius: 12px; padding: 14px 22px;
  text-transform: uppercase; box-shadow: 0 0 22px rgba(57,255,20,.35); transition: transform .1s ease; }
.cta-btn:hover { transform: translateY(-1px); }
.cta-notice { margin-top: 16px; font-family: var(--mono); font-size: 13px; padding: 12px 16px; border-radius: 12px; }
.cta-notice--ok { color: var(--green); background: rgba(57,255,20,.08); border: 1px solid rgba(57,255,20,.4); }
.cta-notice--err { color: var(--pink); background: rgba(255,61,154,.08); border: 1px solid rgba(255,61,154,.4); }

@media (max-width: 860px) {
  .funnel { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
  .funnel { grid-template-columns: 1fr; }
  .hero-number { font-size: 46px; }
  h1.wordmark { font-size: 26px; }
  .hud { font-size: 9px; }
  .lb-row { grid-template-columns: 34px 1fr auto 42px; }
  .lb-cat { display: none; }
}
"""


def render_dashboard(
    opportunities: list[Opportunity],
    metrics: FunnelMetrics,
    drafts: list[OutboundDraft],
    *,
    include_email_form: bool = False,
    notice: str = "",
    notice_ok: bool = True,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # HUD bar — real metrics mapped to arcade readouts
    score = _composite_score(metrics, opportunities)
    lvl_no, lvl_name = _current_level(metrics)
    fund = _fund_value(metrics)
    # NYSE-style ticker tape: funnel metrics + top deals as ticker "symbols"
    _tier_cls = {"high": "pink", "mid": "cyan", "base": "base"}
    cells = [
        f'<span class="tick"><span class="tick-k">SCORE</span><span class="tick-v amber">{score:,}</span></span>',
        f'<span class="tick"><span class="tick-k">LVL {lvl_no}</span><span class="tick-v pink">{html.escape(lvl_name)}</span></span>',
        f'<span class="tick"><span class="tick-k">FUND</span><span class="tick-v green">{html.escape(fund)}</span></span>',
        f'<span class="tick"><span class="tick-k">SIGNALS</span><span class="tick-v">{metrics.signals_ingested:,}</span></span>',
        f'<span class="tick"><span class="tick-k">TRACKED</span><span class="tick-v">{metrics.companies_tracked:,}</span></span>',
        f'<span class="tick"><span class="tick-k">QUALIFIED</span><span class="tick-v cyan">{metrics.qualified_deals}</span></span>',
    ]
    netnew = str(metrics.net_new_qualified_7d)
    if metrics.new_companies_this_run:
        netnew += f" &#9650;+{metrics.new_companies_this_run}"
    cells.append(f'<span class="tick"><span class="tick-k">NET-NEW 7D</span><span class="tick-v green">{netnew}</span></span>')
    cells.append(f'<span class="tick"><span class="tick-k">REPEAT</span><span class="tick-v">{metrics.repeat_signal_companies}</span></span>')
    if metrics.top_category:
        cells.append(f'<span class="tick"><span class="tick-k">SECTOR</span><span class="tick-v base">{html.escape(metrics.top_category.upper())}</span></span>')
    for opp in opportunities[:6]:
        cls = _tier_cls.get(_score_tier(opp.score), "base")
        arrow = " &#9650;" if opp.score >= 3.0 else ""
        cells.append(
            f'<span class="tick"><span class="tick-sym">{html.escape(opp.company.upper())}</span>'
            f'<span class="tick-v {cls}">{opp.score:.1f}{arrow}</span></span>'
        )
    _half = '<span class="tick-sep">&#9670;</span>'.join(cells) + '<span class="tick-sep">&#9670;</span>'
    # Track is duplicated so the -50% scroll loops seamlessly.
    hud = f'<div class="ticker"><div class="ticker-track">{_half}{_half}</div></div>'

    # North-star HIGH SCORE hero
    delta = metrics.new_companies_this_run
    delta_chip = (
        f'<div class="delta-chip"><span class="arrow">&#9650;</span>'
        f'<span>+{delta}</span>'
        f'<span class="delta-sub">this run</span></div>'
        if delta
        else (
            '<div class="delta-chip"><span>&#8226; 0</span>'
            '<span class="delta-sub">this run</span></div>'
        )
    )
    hero = f"""
    <section class="hero">
      <div class="hero-left">
        <span class="hero-number">{metrics.net_new_qualified_7d}</span>
        <div class="hero-meta">
          <span class="hero-label">HIGH SCORE &mdash; net-new qualified deals (7d)</span>
          <span class="hero-sub">&#9658; North-star metric</span>
        </div>
      </div>
      {delta_chip}
    </section>"""

    # Trend
    trend_block = f"""
    <p class="section-label">&#9658; FUNNEL TREND</p>
    <span class="section-sub">signals ingested vs qualified / day</span>
    <section class="trend-card">
      <div class="trend-legend">
        <span class="legend-item"><span class="legend-swatch legend-swatch--bar"></span>Signals / day</span>
        <span class="legend-item"><span class="legend-swatch legend-swatch--line"></span>Qualified / day</span>
      </div>
      {_sparkline(metrics.trend)}
    </section>"""

    # Deals surfaced — #1 spotlight + arcade high-scores leaderboard
    if opportunities:
        deals_block = _spotlight_card(opportunities[0]) + _leaderboard(opportunities)
    else:
        deals_block = (
            '<p class="empty-note">&#9658; NO DEALS SURFACED THIS RUN &mdash; INSERT COIN.<br>'
            "Nothing scored above threshold yet.</p>"
        )

    # Outbound queue — condensed to the top few as proof of the ACTION stage
    if drafts:
        draft_cards = "\n".join(_draft_card(d) for d in drafts[:5])
    else:
        draft_cards = (
            '<p class="empty-note">&#9658; QUEUE EMPTY &mdash; INSERT COIN.<br>'
            "No outbound drafted this run.</p>"
        )

    # Web-mode interactive pieces: LIVE badge + 'email me the brief' CTA
    live_badge = '<span class="live-badge">LIVE</span>' if include_email_form else ""
    cta_block = ""
    if include_email_form:
        notice_html = ""
        if notice:
            kind = "ok" if notice_ok else "err"
            notice_html = f'<div class="cta-notice cta-notice--{kind}">{html.escape(notice)}</div>'
        cta_block = f"""
    <section class="cta">
      <span class="cta-title">&#9658; GET THIS BRIEF IN YOUR INBOX</span>
      <span class="cta-sub">The agent emails you this live deal-flow report &mdash; real email, one click.</span>
      {notice_html}
      <form class="cta-form" method="post" action="/request-report">
        <input class="cta-input" type="email" name="email" placeholder="you@firm.com" required aria-label="your email">
        <button class="cta-btn" type="submit">&#9654; SEND ME THE REPORT</button>
      </form>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LAUNCHY &mdash; your VC deal-flow agent &mdash; {now}</title>
<style>{_CSS}</style>
</head>
<body>
  <a class="repo-link" href="https://github.com/Lockdown83/launch-deal-flow-agent" target="_blank" rel="noopener" aria-label="View source on GitHub">
    <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 012-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
    <span class="repo-link-text">Source</span>
    <span class="repo-link-divider" aria-hidden="true">/</span>
    <span class="repo-link-credit">Designed by Andrew in California</span>
  </a>
  <main class="wrap">
    {hud}
    <p class="brand">YOUR VC DEAL-FLOW AGENT{live_badge}</p>
    <h1 class="wordmark">LAUNCHY</h1>
    <p class="mission">An always-on agent that turns Sequoia, a16z, Y Combinator, and Hacker News
      signals into net-new qualified deal flow &mdash; reach, research, quality, action.</p>
    <p class="generated">GENERATED {now}</p>

    {hero}
    {cta_block}

    <p class="section-label">&#9658; THE FUNNEL: REACH &rarr; RESEARCH &rarr; QUALITY &rarr; ACTION</p>
    <span class="section-sub">four stages, one north star &mdash; every level answers a question</span>
    {_funnel_section(metrics)}

    {trend_block}

    <p class="section-label">&#9658; DEALS SURFACED &mdash; HIGH SCORES</p>
    <span class="section-sub">the output of the funnel, ranked by conviction</span>
    {deals_block}

    <p class="section-label">&#9658; OUTBOUND QUEUE &mdash; PENDING HUMAN APPROVAL</p>
    <span class="section-sub">drafted, locked, never auto-sent</span>
    {draft_cards}

    <footer>LAUNCHY &middot; YOUR VC DEAL-FLOW AGENT &middot; {now}<br>OUTBOUND IS DRAFTED, NEVER AUTO-SENT. &#9658; INSERT COIN TO CONTINUE</footer>
  </main>
</body>
</html>"""
