"""Live Y Combinator company-directory source.

Pulls recent-batch YC companies straight from the public Algolia index that
backs https://www.ycombinator.com/companies and maps each into a `Signal`.
This replaces the hardcoded `YC_DIRECTORY_SEED_SIGNALS` list in `sources.py`
with real, live directory data.

HOW THE LIVE PATH WORKS
-----------------------
The companies page injects its search-only Algolia credentials into the page
HTML as a `window.AlgoliaOpts = {"app": ..., "key": ...}` blob (the JS bundle
just reads `window.AlgoliaOpts`). We:
  1. Fetch the companies page and parse `window.AlgoliaOpts` for the current
     app id + search-only API key (they can rotate, so we never hardcode them
     as the primary path).
  2. POST a query to the public DSN endpoint
     `https://<appid>-dsn.algolia.net/1/indexes/YCCompany_production/query`
     with `X-Algolia-Application-Id` / `X-Algolia-API-Key` headers, filtering
     to the latest batches via `facetFilters` on the `batch` field.

The index stores the batch as a full label, e.g. "Winter 2026" / "Spring 2026"
/ "Fall 2025" / "Summer 2025" (not the short "W26" form), so we filter on those.

ROBUSTNESS
----------
If the keys can't be discovered (rotation, layout change) or the query fails,
we fall back to an unauthenticated GET against the same companies page and
scrape the embedded company records. On any hard failure we return [].
Verified live on 2026-05-21 with app id 45BWZJ1SGC.

stdlib only (urllib + json); no third-party deps.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .models import Signal, now_utc

YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
YC_INDEX = "YCCompany_production"

# Latest batches we care about for pre/just-announced deal flow. The Algolia
# `batch` field uses full labels. Keep newest first. Update as YC adds batches.
RECENT_BATCHES = [
    "Winter 2026",
    "Spring 2026",
    "Fall 2025",
    "Summer 2025",
]

# How many companies to pull across the recent batches.
MAX_HITS = 200

_DESC_LIMIT = 400


def _fetch_bytes(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 25) -> bytes:
    """Fetch raw bytes with stdlib only, tolerating local macOS cert issues."""
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "launch-deal-flow-agent/0.1", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        is_cert = isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)
        if not is_cert:
            raise
        context = ssl._create_unverified_context()  # noqa: SLF001 - local cert fallback
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return response.read()


def _fetch_text(url: str, timeout: int = 25) -> str:
    return _fetch_bytes(url, timeout=timeout).decode("utf-8", "ignore")


def _discover_algolia_creds() -> tuple[str, str] | None:
    """Parse `window.AlgoliaOpts = {"app": ..., "key": ...}` from the live page."""
    try:
        html = _fetch_text(YC_COMPANIES_URL)
    except Exception:
        return None
    match = re.search(r"window\.AlgoliaOpts\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
    if not match:
        return None
    try:
        opts = json.loads(match.group(1))
    except Exception:
        return None
    app = opts.get("app")
    key = opts.get("key")
    if app and key:
        return str(app), str(key)
    return None


def _algolia_query(app: str, key: str, batches: list[str]) -> list[dict]:
    """POST one query to the YC Algolia index, filtered to the given batches."""
    url = f"https://{app.lower()}-dsn.algolia.net/1/indexes/{YC_INDEX}/query"
    # facetFilters with a nested OR list means "batch is any of these".
    body = json.dumps(
        {
            "query": "",
            "hitsPerPage": MAX_HITS,
            "facetFilters": [[f"batch:{b}" for b in batches]],
        }
    ).encode("utf-8")
    headers = {
        "X-Algolia-Application-Id": app,
        "X-Algolia-API-Key": key,
        "Content-Type": "application/json",
    }
    raw = _fetch_bytes(url, data=body, headers=headers)
    payload = json.loads(raw.decode("utf-8", "ignore"))
    hits = payload.get("hits")
    return hits if isinstance(hits, list) else []


def _short_batch(batch: str) -> str:
    """Turn 'Winter 2026' -> 'W26' for compact stage labels (best effort)."""
    parts = (batch or "").split()
    if len(parts) == 2 and parts[1].isdigit():
        season = {"winter": "W", "summer": "S", "spring": "X", "fall": "F"}.get(parts[0].lower())
        if season:
            return f"{season}{parts[1][-2:]}"
    return batch or "unknown batch"


def _category_for(tags: list[str], one_liner: str, industry: str, long_desc: str) -> str:
    """Infer a deal-flow category from YC tags + text."""
    tag_text = " ".join(tags).lower()
    text = f"{tag_text} {one_liner} {long_desc} {industry}".lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms)

    if has("agent", "agentic", "llm", "inference", "fine-tun", "rag", "vector", "evals", "eval ", "mcp", "orchestrat"):
        if has("infra", "infrastructure", "platform", "api", "sdk", "tooling", "observability", "monitor"):
            return "AI agent infrastructure"
        return "AI agent / applied AI"
    if has("payment", "fintech", "bank", "lending", "mortgage", "stablecoin", "onchain", "ledger", "invoice", "treasury"):
        return "Fintech infrastructure"
    if has("energy", "grid", "power", "solar", "battery", "carbon", "climate", "nuclear"):
        return "Energy / climate software"
    if has("health", "clinic", "patient", "medical", "biotech", "pharma", "diagnos"):
        return "Healthcare / bio"
    if has("defense", "drone", "military", "aerospace", "satellite"):
        return "Defense / aerospace"
    if has("legal", "compliance", "tax", "insurance", "actuarial", "underwrit", "construction", "logistics", "supply"):
        return "Vertical AI operator"
    if has("developer", "devtool", "code", "ci/cd", "testing", "qa", "security", "data ", "analytics"):
        return "AI / developer software tooling"
    if has("artificial intelligence", "machine learning", "generative ai", "computer vision"):
        return "Applied AI"
    if industry:
        return industry
    return "AI / software"


def _observed_at(hit: dict) -> datetime:
    """Use the company's launch timestamp when present; else a small recent offset."""
    launched = hit.get("launched_at")
    if isinstance(launched, (int, float)) and launched > 0:
        try:
            dt = datetime.fromtimestamp(float(launched), tz=timezone.utc)
            # Guard against absurd values; ignore if not plausibly recent-ish.
            if datetime(2005, 1, 1, tzinfo=timezone.utc) <= dt <= now_utc() + timedelta(days=400):
                return dt
        except (OverflowError, OSError, ValueError):
            pass
    return now_utc() - timedelta(days=3)


def _signal_from_hit(hit: dict) -> Signal | None:
    name = (hit.get("name") or "").strip()
    if not name:
        return None

    one_liner = (hit.get("one_liner") or "").strip()
    long_desc = (hit.get("long_description") or "").strip()
    batch = (hit.get("batch") or "").strip()
    slug = (hit.get("slug") or "").strip()
    website = (hit.get("website") or "").strip()
    tags = [t for t in (hit.get("tags") or []) if isinstance(t, str)]
    industry = (hit.get("industry") or "").strip()

    url = f"{YC_COMPANIES_URL}/{slug}" if slug else (website or YC_COMPANIES_URL)

    description = (long_desc or one_liner)[:_DESC_LIMIT]
    title = f"{name}: {one_liner}" if one_liner else name

    metric_label = ""
    metric_value: float | None = None
    team_size = hit.get("team_size")
    if isinstance(team_size, (int, float)) and team_size > 0:
        metric_label = "YC team size"
        metric_value = float(team_size)

    return Signal(
        company=name,
        source="YC company directory (live)",
        signal_type="direct_announcement",
        title=title,
        url=url,
        observed_at=_observed_at(hit),
        description=description,
        category=_category_for(tags, one_liner, industry, long_desc),
        stage=f"YC {_short_batch(batch)} / early" if batch else "YC / early",
        metric_label=metric_label,
        metric_value=metric_value,
    )


def _collect_via_algolia() -> list[Signal]:
    creds = _discover_algolia_creds()
    if not creds:
        return []
    app, key = creds
    hits = _algolia_query(app, key, RECENT_BATCHES)
    signals: list[Signal] = []
    for hit in hits:
        try:
            signal = _signal_from_hit(hit)
        except Exception:
            continue
        if signal:
            signals.append(signal)
    return signals


def _collect_via_scrape() -> list[Signal]:
    """Fallback: scrape any embedded company JSON from the companies page HTML.

    Only used if the Algolia keys can't be discovered or the query fails. The
    page does not reliably embed full company records, so this may return [].
    """
    try:
        html = _fetch_text(YC_COMPANIES_URL)
    except Exception:
        return []
    signals: list[Signal] = []
    seen: set[str] = set()
    # Look for compact company-like objects ({"name": ..., "slug": ..., "batch": ...}).
    for match in re.finditer(r"\{[^{}]*\"slug\"[^{}]*\"batch\"[^{}]*\}", html):
        try:
            hit = json.loads(match.group(0))
        except Exception:
            continue
        if (hit.get("batch") or "").strip() not in RECENT_BATCHES:
            continue
        name = hit.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        signal = _signal_from_hit(hit)
        if signal:
            signals.append(signal)
    return signals


def collect() -> list[Signal]:
    """Return recent-batch YC companies as Signals. Never raises; [] on failure."""
    try:
        signals = _collect_via_algolia()
        if signals:
            return signals
    except Exception as exc:  # pragma: no cover - defensive
        print(f"WARN: source_yc Algolia path failed: {exc}")
    try:
        return _collect_via_scrape()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"WARN: source_yc scrape fallback failed: {exc}")
        return []
