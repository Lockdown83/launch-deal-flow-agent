from __future__ import annotations

import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from urllib.parse import urlparse

from . import source_edgar, source_github, source_yc
from .models import Signal, now_utc, parse_rss_date

SEQUOIA_RSS = "https://www.sequoiacap.com/feed/"
YC_RSS = "https://www.ycombinator.com/blog/rss"
A16Z_NEWS = "https://a16z.com/news-content/"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"

def fetch_text(url: str, timeout: int = 25) -> str:
    """Fetch text with stdlib only. Falls back for local macOS cert issues."""
    headers = {"User-Agent": "launch-deal-flow-agent/0.1"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc) and not isinstance(exc, ssl.SSLCertVerificationError):
            raise
        context = ssl._create_unverified_context()  # noqa: SLF001 - MVP fallback for local cert setup.
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return response.read().decode("utf-8", "ignore")


def clean(value: str | None) -> str:
    text = value or ""
    text = text.replace("<![CDATA[", "").replace("]]>", "")
    text = re.sub(r"<.*?>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def tag(item: str, name: str) -> str:
    match = re.search(fr"<{name}[^>]*>([\s\S]*?)</{name}>", item)
    return clean(match.group(1)) if match else ""


def company_from_title(title: str) -> str | None:
    patterns = [
        r"Partnering with ([^:—-]+)",
        r"Investing in ([^:—-]+)",
        r"Congratulations to ([^:—-]+?)(?: on |$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1).strip()
    if "Standard Intelligence" in title:
        return "Standard Intelligence"
    if "Ineffable Intelligence" in title:
        return "Ineffable Intelligence"
    return None


def category_for(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    if any(term in text for term in ["agent", "context", "validation", "logs", "qa", "fine-tuning", "reasoning", "verification"]):
        return "AI agent infrastructure"
    if any(term in text for term in ["payment", "fintech", "stablecoin", "onchain", "mortgage"]):
        return "Fintech infrastructure"
    if any(term in text for term in ["energy", "grid", "power"]):
        return "Energy software"
    if any(term in text for term in ["video", "creative", "consumer"]):
        return "AI creative/consumer"
    if any(term in text for term in ["defense", "american dynamism", "dod"]):
        return "Defense / American Dynamism"
    return "AI / software"


def collect_sequoia() -> list[Signal]:
    data = fetch_text(SEQUOIA_RSS)
    signals: list[Signal] = []
    for item in re.findall(r"<item[\s\S]*?</item>", data)[:25]:
        title = tag(item, "title")
        company = company_from_title(title)
        if not company:
            continue
        description = tag(item, "description")
        signals.append(
            Signal(
                company=company,
                source="Sequoia official RSS",
                signal_type="direct_announcement",
                title=title,
                url=tag(item, "link"),
                observed_at=parse_rss_date(tag(item, "pubDate")),
                description=description,
                category=category_for(title, description),
                stage="Seed/early to growth; exact stage unconfirmed",
            )
        )
    return signals


def collect_yc_blog() -> list[Signal]:
    data = fetch_text(YC_RSS)
    signals: list[Signal] = []
    for item in re.findall(r"<item[\s\S]*?</item>", data)[:25]:
        title = tag(item, "title")
        company = company_from_title(title)
        if not company:
            continue
        description = tag(item, "description")
        signals.append(
            Signal(
                company=company,
                source="YC official blog RSS",
                signal_type="direct_announcement",
                title=title,
                url=tag(item, "link"),
                observed_at=parse_rss_date(tag(item, "pubDate")),
                description=description,
                category=category_for(title, description),
                stage="YC portfolio / growth; exact stage unconfirmed",
            )
        )
    return signals


def collect_a16z_news() -> list[Signal]:
    data = fetch_text(A16Z_NEWS)
    titles = []
    for match in re.finditer(r"Investing in [A-Z][A-Za-z0-9 .!&\-]+", data):
        title = clean(match.group(0))
        if title not in titles:
            titles.append(title)
    signals: list[Signal] = []
    for title in titles[:25]:
        company = company_from_title(title)
        if not company:
            continue
        signals.append(
            Signal(
                company=company,
                source="a16z public news page",
                signal_type="direct_announcement",
                title=title,
                url=A16Z_NEWS,
                observed_at=now_utc(),
                category=category_for(title),
                stage="Seed to growth; exact stage unconfirmed",
            )
        )
    return signals


# Over-generic single-word names that constantly collide with unrelated HN stories.
# A title keyword match on any of these is meaningless; only a domain match counts.
_HN_GENERIC_TOKENS = {
    "hyper", "modern", "glimpse", "canary", "standard", "ai", "app", "data",
    "cloud", "labs", "hilbert", "general", "core", "base", "stack", "flow",
    "node", "edge", "vector", "atlas", "nova", "echo", "pulse", "scale",
}
# A short single-word name needs real traction before a bare keyword match is trusted.
_HN_SINGLE_WORD_MIN_POINTS = 25
_HN_SHORT_NAME_LEN = 6


def _title_has_standalone_token(company: str, title: str) -> bool:
    """True only if the company name appears as a clear, whole-word token in the title.

    Uses word boundaries so 'Hyper' does not match 'hyperscale' or 'WAR.GOV/UFO'
    noise, and so a substring buried inside another word never counts.
    """
    return bool(re.search(rf"\b{re.escape(company.lower())}\b", title.lower()))


def _company_matches_hn_hit(company: str, title: str, url: str, points: int = 0) -> bool:
    """Decide whether an HN story is really about `company`.

    Conservative by design: better to miss a weak HN match than to attach a wrong one
    (the "Hyper" -> "Show HN: ... WAR.GOV/UFO files" failure mode). A match requires a
    clear standalone-token hit in the title OR a strong domain match, with extra
    guards for short/generic single-word names.
    """
    name = (company or "").strip()
    if not name:
        return False
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    domain = re.sub(r"[^a-z0-9]", "", urlparse(url).netloc.lower()) if url else ""

    # A strong domain match is the most trustworthy signal — accept it regardless of name.
    if normalized and len(normalized) >= 3 and normalized in domain:
        return True

    is_single_word = " " not in name
    if is_single_word:
        # Generic/over-common single words never qualify on a title keyword alone.
        if name.lower() in _HN_GENERIC_TOKENS:
            return False
        # Must appear as a standalone token, not a substring of another word.
        if not _title_has_standalone_token(name, title):
            return False
        # Title-only matches for single (often dictionary) words are unreliable — e.g. company
        # "Panacea" colliding with "...a panacea for snake bites". Trust a title hit only for a
        # product-launch post (Show HN / Launch HN), which actually names the company's product.
        tl = title.lower()
        if not (tl.startswith("show hn") or tl.startswith("launch hn")
                or "show hn:" in tl or "launch hn:" in tl):
            return False
        # Very short single-word names are too ambiguous; require real traction even for launches.
        if len(normalized) <= _HN_SHORT_NAME_LEN and points < _HN_SINGLE_WORD_MIN_POINTS:
            return False
        return True

    # Multi-word names are specific enough when the exact phrase appears in the title.
    return company.lower() in title.lower()


def collect_hn_for(companies: list[str]) -> list[Signal]:
    results: list[Signal] = []
    cutoff = now_utc() - timedelta(days=45)
    for company in companies:
        params = urllib.parse.urlencode({"query": company, "tags": "story", "hitsPerPage": 5})
        try:
            payload = json.loads(fetch_text(f"{HN_SEARCH}?{params}"))
        except Exception:
            continue
        added_for_company = 0
        for hit in payload.get("hits", []):
            title = hit.get("title") or ""
            created = hit.get("created_at")
            url = hit.get("url") or ""
            if not title or not created:
                continue
            observed_at = parse_rss_date(created)
            if observed_at < cutoff:
                continue
            points = hit.get("points") or 0
            if not _company_matches_hn_hit(company, title, url, int(points)):
                continue
            # Link to the HN discussion permalink, never the external article URL:
            # aggregator/roundup posts can point at an unrelated company and break trust.
            object_id = hit.get("objectID")
            hn_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else "https://news.ycombinator.com/"
            results.append(
                Signal(
                    company=company,
                    source="Hacker News Algolia",
                    signal_type="founder_community",
                    title=title,
                    url=hn_url,
                    observed_at=observed_at,
                    description=f"HN points: {points}",
                    category="Founder/community validation",
                    stage="Unconfirmed",
                    metric_label="HN points",
                    metric_value=float(points),
                )
            )
            added_for_company += 1
            if added_for_company >= 2:
                break
    return results


# For deal sourcing we want EMERGING repos gaining traction, not established giants
# (n8n / ollama / transformers aren't deal flow). Keep a sane star band and a cap.
GITHUB_STAR_FLOOR = 400.0
GITHUB_STAR_CEILING = 15000.0
GITHUB_CAP = 12
A16Z_CAP = 8
HN_ENRICH_CAP = 40


def _emerging_github(signals: list[Signal]) -> list[Signal]:
    kept = [
        s for s in signals
        if s.metric_value is None or GITHUB_STAR_FLOOR <= s.metric_value <= GITHUB_STAR_CEILING
    ]
    kept.sort(key=lambda s: s.metric_value or 0.0, reverse=True)
    return kept[:GITHUB_CAP]


_LEGAL_SUFFIX_RE = re.compile(
    r"[,\s]+(?:inc|incorporated|llc|l\.l\.c|corp|corporation|ltd|limited|lp|l\.p|llp|plc|gmbh)\.?$",
    re.IGNORECASE,
)
_JUNK_NAME_RE = re.compile(
    r"(?i)\b(realty|properties|property|investors|real estate|reit|apartments|residences|"
    r"estates|street|avenue|\bave\b|\broad\b|\bblvd\b|\bdrive\b|\bcourt\b|\blane\b)\b"
)


def clean_company_name(name: str) -> str:
    """Strip legal-entity suffixes and de-shout ALL-CAPS names so the brief reads clean."""
    n = (name or "").strip().strip(",").strip()
    prev = None
    while n and n != prev:  # strip stacked suffixes, e.g. "Foo Holdings, LLC"
        prev = n
        n = _LEGAL_SUFFIX_RE.sub("", n).strip().rstrip(",.").strip()
    if n and len(n) > 3 and n == n.upper():  # de-shout EDGAR all-caps -> Title Case
        n = n.title()
        n = re.sub(r"\b(Ai|Ml|Api|Hr|Ar|Vr|Iot|Saas)\b", lambda m: m.group(1).upper(), n)
    return n or (name or "").strip()


def _looks_like_junk(name: str) -> bool:
    """Real-estate / SPV / address-style entities that slip through (esp. SEC Form D)."""
    n = (name or "").strip()
    if not n or re.match(r"^\d", n):  # empty, or starts with a number (street addresses / SPVs)
        return True
    return bool(_JUNK_NAME_RE.search(n))


def collect_all_signals() -> list[Signal]:
    """Aggregate every source. Required by brief: Sequoia + a16z + YC.
    Added for breadth/depth: live YC directory, GitHub traction, SEC Form D, HN validation.
    """
    signals: list[Signal] = []

    # Brief-required firm sources.
    for collector in [collect_sequoia, collect_yc_blog, collect_a16z_news]:
        try:
            collected = collector()
            if collector is collect_a16z_news:
                collected = collected[:A16Z_CAP]
            signals.extend(collected)
        except Exception as exc:
            print(f"WARN: {collector.__name__} failed: {exc}")

    # New real sources (each is self-guarded and returns [] on failure).
    # YC directory presence alone is weak signal (every batch company is "in" YC).
    # Demote it to context-weight so a YC company only surfaces as a qualified deal
    # when it CONVERGES with another signal (HN/GitHub) or carries real traction.
    try:
        yc_live = source_yc.collect()
        for s in yc_live:
            s.signal_type = "portfolio_momentum"
        signals.extend(yc_live)
    except Exception as exc:
        print(f"WARN: source_yc failed: {exc}")
    try:
        signals.extend(_emerging_github(source_github.collect()))
    except Exception as exc:
        print(f"WARN: source_github failed: {exc}")
    try:
        signals.extend(source_edgar.collect())
    except Exception as exc:
        print(f"WARN: source_edgar failed: {exc}")

    # Clean names + drop real-estate/SPV junk (esp. from EDGAR) BEFORE enrichment, so the
    # brief reads clean and HN lookups search clean names.
    cleaned: list[Signal] = []
    for s in signals:
        if _looks_like_junk(s.company):
            continue
        s.company = clean_company_name(s.company)
        cleaned.append(s)
    signals = cleaned

    # HN validation: enrich only the named "deal" companies (skip the GitHub repo bulk,
    # which already carries its own traction metric), and cap the number of API calls.
    deal_companies = [
        s.company for s in signals if s.source != "GitHub trending API"
    ]
    seen: set[str] = set()
    ordered_unique = [c for c in deal_companies if not (c in seen or seen.add(c))]
    signals.extend(collect_hn_for(ordered_unique[:HN_ENRICH_CAP]))
    return signals
