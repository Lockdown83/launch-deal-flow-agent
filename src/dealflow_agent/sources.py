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

from .models import Signal, now_utc, parse_rss_date

SEQUOIA_RSS = "https://www.sequoiacap.com/feed/"
YC_RSS = "https://www.ycombinator.com/blog/rss"
A16Z_NEWS = "https://a16z.com/news-content/"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"

YC_DIRECTORY_SEED_SIGNALS = [
    ("Moda", "The monitoring layer your AI agents need.", "AI agent infrastructure"),
    ("Rubric AI", "Reasoning and verification infra for AI.", "AI agent infrastructure"),
    ("Carrot Labs", "Continuous Fine-Tuning for AI Models.", "AI agent infrastructure"),
    ("Wayco", "AI operator for medlegal cases.", "Vertical AI operator"),
    ("Copperlane", "Agentic Mortgage Origination.", "Vertical fintech AI"),
    ("Condor Energy", "Software for enterprise energy procurement.", "Energy software"),
    ("Squid", "AI agents for power grid planning.", "Energy software"),
    ("Canary", "The first AI QA engineer that understands your code.", "AI software tooling"),
    ("Maven", "Payments Infrastructure for Voice Agents.", "Fintech infrastructure"),
    ("Fixture", "An AI-first CRM built for Startups.", "AI-native SaaS"),
]


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


def collect_yc_directory_seed() -> list[Signal]:
    observed_at = now_utc() - timedelta(days=3)
    return [
        Signal(
            company=company,
            source="YC startup directory seed scan",
            signal_type="direct_announcement",
            title=f"{company}: {description}",
            url="https://www.ycombinator.com/companies",
            observed_at=observed_at,
            description=description,
            category=category,
            stage="YC W26 / pre-seed",
        )
        for company, description, category in YC_DIRECTORY_SEED_SIGNALS
    ]


def _company_matches_hn_hit(company: str, title: str, url: str) -> bool:
    """Avoid false positives for generic names like Canary, Hilbert, or Glimpse."""
    normalized = re.sub(r"[^a-z0-9]", "", company.lower())
    domain = re.sub(r"[^a-z0-9]", "", urlparse(url).netloc.lower()) if url else ""
    title_lower = title.lower()

    if normalized and normalized in domain:
        return True

    # Multi-word names are usually specific enough when the exact phrase appears in the title.
    if " " in company and company.lower() in title_lower:
        return True

    # Single-word company names are too ambiguous for HN keyword matching.
    # Only count them when the company appears in the linked domain.
    return False


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
            if not _company_matches_hn_hit(company, title, url):
                continue
            results.append(
                Signal(
                    company=company,
                    source="Hacker News Algolia",
                    signal_type="founder_community",
                    title=title,
                    url=url or "https://news.ycombinator.com/",
                    observed_at=observed_at,
                    description=f"HN points: {hit.get('points') or 0}",
                    category="Founder/community validation",
                    stage="Unconfirmed",
                )
            )
            added_for_company += 1
            if added_for_company >= 2:
                break
    return results


def collect_all_signals() -> list[Signal]:
    signals: list[Signal] = []
    for collector in [collect_sequoia, collect_yc_blog, collect_a16z_news, collect_yc_directory_seed]:
        try:
            signals.extend(collector())
        except Exception as exc:
            print(f"WARN: {collector.__name__} failed: {exc}")
    companies = sorted({signal.company for signal in signals})
    signals.extend(collect_hn_for(companies))
    return signals
