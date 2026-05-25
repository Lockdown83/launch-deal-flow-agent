"""Free news-flow source — funding/launch headlines from TechCrunch RSS + GDELT.

Adds a continuous stream of "X raises $Y / X launches" signals on top of the firm / EDGAR /
GitHub / HN sources. Both feeds are free and keyless (stdlib urllib + json, no new deps).

The hard part is pulling the COMPANY out of a free-form headline. We match funding/launch verb
patterns and filter aggressively (precision over recall); whatever slips through is further cleaned
and junk-dropped by the global pass in sources.collect_all_signals(). Convergence does the rest —
a company in news + EDGAR + GitHub the same week is the "caught it early" story.

Never raises: returns [] on hard failure.
"""

from __future__ import annotations

import html as _html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .models import Signal, now_utc, parse_rss_date

_UA = "launch-deal-flow-agent andrewdimaulozx@gmail.com"

TECHCRUNCH_FEEDS = [
    "https://techcrunch.com/tag/funding/feed/",
    "https://techcrunch.com/category/startups/feed/",
]
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = (
    '(raises OR raised OR "Series A" OR "Series B" OR "seed round") '
    '(startup OR AI OR fintech OR "AI agent" OR defense OR robotics OR biotech)'
)
NEWS_CAP = 25

# Funding/launch verbs; the company is the leading proper-noun phrase before one of them.
# Funding-style verbs only — editorial verbs (unveils/announces/debuts) caught noise like
# "Pope Leo unveils his encyclical", so they're intentionally excluded.
_VERB = (
    r"(?:raises|raised|secures|secured|lands|landed|closes|closed|nabs|bags|snags|scores|"
    r"banks|hauls in|picks up|launches|launched)"
)
_HEADLINE_RE = re.compile(rf"^(?P<co>[A-Z][\w.&'-]*(?:\s+[A-Z0-9][\w.&'-]*){{0,3}})\s+{_VERB}\b")
_AMOUNT_RE = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s?(b|bn|billion|m|mm|million|k|thousand)\b", re.I)
# A funding cue must be present, else "raises" catches non-funding noise ("Xi raises his voice").
_MONEY_RE = re.compile(
    r"[$€£]|\b\d+(?:\.\d+)?\s?(?:m|mm|million|b|bn|billion|k)\b|"
    r"\bseries\s+[a-e]\b|\bseed\b|\bfunding\b|\braised\b|\bround\b|\bvaluation\b",
    re.I,
)

# Captured "company" strings that are really generic words, publishers, or megacaps (not deal flow).
_BAD = {
    "ai", "ml", "the", "this", "new", "report", "exclusive", "startup", "startups", "tech",
    "us", "uk", "eu", "how", "why", "what", "who", "vc", "ceo", "cfo", "ipo", "sec", "fbi",
    "google", "openai", "meta", "apple", "amazon", "microsoft", "nvidia", "tesla", "spacex",
    "techcrunch", "report says", "sources", "deal", "report:", "exclusive:",
}
# Leading editorial words to strip ("How Lucra raised…" -> "Lucra").
_LEAD_FILLER = {
    "how", "why", "meet", "this", "these", "inside", "after", "exclusive", "watch", "see",
    "with", "at", "report", "when", "where", "now",
}
# Whole-word tokens that mark a VC fund / investor rather than a portfolio company.
_FUND_TOKENS = {
    "capital", "fund", "funds", "ventures", "partners", "advisors", "advisers",
    "management", "equity", "holdings", "vc",
}
# Person-title leading words that mean the "company" is really a person (drop the whole match).
_TITLES = {
    "pope", "president", "king", "queen", "senator", "sen", "governor", "gov", "mayor",
    "dr", "prof", "rep", "secretary", "minister", "prince", "princess", "judge",
}


def _fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        if not isinstance(exc, ssl.SSLCertVerificationError) and "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        ctx = ssl._create_unverified_context()  # noqa: SLF001 - local cert fallback only.
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", "ignore")


def _clean(text: str | None) -> str:
    t = _html.unescape(text or "").replace("<![CDATA[", "").replace("]]>", "")
    t = re.sub(r"<.*?>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_company(title: str) -> str | None:
    """Pull the company out of a funding/launch headline. Best-effort, precision-biased."""
    m = _HEADLINE_RE.match(title)
    if not m:
        return None
    if not _MONEY_RE.search(title):  # require a real funding cue, not just the verb
        return None
    co = m.group("co").strip().rstrip(",.").strip()
    # "Sam Altman-backed Coco Robotics" -> "Coco Robotics"
    mb = re.search(r"(?:-backed|-led|-funded|-incubated|-owned)\s+(.+)$", co, re.I)
    if mb:
        co = mb.group(1).strip()
    # Strip leading editorial filler ("How Lucra" -> "Lucra")
    toks = co.split()
    while toks and toks[0].lower() in _LEAD_FILLER:
        toks.pop(0)
    co = " ".join(toks).strip()
    low = co.lower()
    if not co or low in _BAD or len(co) < 2 or len(co) > 40:
        return None
    if co.split()[0].lower() in _TITLES:  # "Pope Leo", "President X" — a person, not a company
        return None
    if all(tok.lower() in _BAD for tok in co.split()):
        return None
    if " " not in co and co.isupper() and len(co) <= 3:  # solo acronym (AI, ML, IPO)
        return None
    # Drop VC funds / investors (whole-word match) — they're not deal flow.
    words = set(re.sub(r"[^a-z0-9 ]", " ", low).split())
    if words & _FUND_TOKENS:
        return None
    return co


def _category(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("fintech", "payment", "bank", "stablecoin")):
        return "Fintech"
    if any(w in t for w in ("defense", "defence", "dod")):
        return "Defense"
    if any(w in t for w in ("health", "bio", "pharma", "clinical")):
        return "Healthcare / bio"
    if any(w in t for w in ("energy", "grid", "battery", "nuclear")):
        return "Energy"
    return "AI / software"


def _amount(title: str) -> float | None:
    m = _AMOUNT_RE.search(title)
    if not m:
        return None
    mult = {
        "b": 1e9, "bn": 1e9, "billion": 1e9, "m": 1e6, "mm": 1e6, "million": 1e6,
        "k": 1e3, "thousand": 1e3,
    }.get(m.group(2).lower(), 1.0)
    return float(m.group(1)) * mult


def _from_techcrunch() -> list[Signal]:
    out: list[Signal] = []
    for feed in TECHCRUNCH_FEEDS:
        try:
            data = _fetch(feed)
        except Exception:
            continue
        for item in re.findall(r"<item[\s\S]*?</item>", data)[:40]:
            tm = re.search(r"<title>([\s\S]*?)</title>", item)
            if not tm:
                continue
            title = _clean(tm.group(1))
            co = _extract_company(title)
            if not co:
                continue
            lm = re.search(r"<link>([\s\S]*?)</link>", item)
            pm = re.search(r"<pubDate>([\s\S]*?)</pubDate>", item)
            amt = _amount(title)
            out.append(
                Signal(
                    company=co, source="TechCrunch funding", signal_type="news_event",
                    title=title, url=_clean(lm.group(1)) if lm else feed,
                    observed_at=parse_rss_date(_clean(pm.group(1))) if pm else now_utc(),
                    description="TechCrunch funding/startup news", category=_category(title),
                    stage="News-reported", metric_label=("Reported raise (USD)" if amt else ""),
                    metric_value=amt,
                )
            )
    return out


def _from_gdelt() -> list[Signal]:
    params = urllib.parse.urlencode(
        {"query": GDELT_QUERY, "mode": "artlist", "format": "json",
         "sort": "datedesc", "timespan": "2days", "maxrecords": "75"}
    )
    try:
        payload = json.loads(_fetch(f"{GDELT_URL}?{params}"))
    except Exception:
        return []
    out: list[Signal] = []
    for art in payload.get("articles", []):
        title = _clean(art.get("title"))
        co = _extract_company(title)
        if not co:
            continue
        try:
            obs = datetime.strptime(art.get("seendate") or "", "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            obs = now_utc()
        amt = _amount(title)
        out.append(
            Signal(
                company=co, source="GDELT news", signal_type="news_event",
                title=title, url=art.get("url") or "", observed_at=obs,
                description=f"via {art.get('domain', 'news')}", category=_category(title),
                stage="News-reported", metric_label=("Reported raise (USD)" if amt else ""),
                metric_value=amt,
            )
        )
    return out


def collect() -> list[Signal]:
    """Funding/launch news as Signals (TechCrunch + GDELT). Never raises; [] on failure."""
    try:
        signals = _from_techcrunch() + _from_gdelt()
    except Exception:
        return []
    out: list[Signal] = []
    seen: set[str] = set()
    for s in signals:
        key = re.sub(r"[^a-z0-9]", "", (s.company + s.title).lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= NEWS_CAP:
            break
    return out


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    r = collect()
    print(f"{len(r)} news signals")
    for s in r[:12]:
        amt = f" ${s.metric_value:,.0f}" if s.metric_value else ""
        print(f"- [{s.source}] {s.company}{amt} | {s.title[:70]}")
