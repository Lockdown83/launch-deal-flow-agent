"""SEC EDGAR Form D source — real pre-announcement fundraising signal.

A Form D is the notice an issuer files with the SEC when it sells securities
under a Regulation D exemption (i.e. a private placement). Startups file one
shortly after closing a priced round, usually weeks or months *before* any
press release. That makes it one of the highest-value free pre-announcement
fundraising signals available.

ENDPOINT (verified working, free, no key):
    EDGAR full-text search JSON API
    https://efts.sec.gov/LATEST/search-index?q=&forms=D&startdt=...&enddt=...
    Returns up to 100 hits/page with `display_names`, `ciks`, `file_date`,
    `adsh`. Pagination via `from`. SEC requires a descriptive User-Agent
    containing a contact email or it blocks the request.

We then fetch each filing's `primary_doc.xml` (cheap, rate-limited) to read the
`industryGroupType` (best filter signal — drops "Pooled Investment Fund") and
`totalOfferingAmount` (USD raise size).

NOISE / FILTERING CAVEAT:
    Form D is dominated by funds, SPVs, real-estate vehicles and holding
    entities. We filter aggressively:
      - drop filings whose `industryGroupType` is "Pooled Investment Fund"
      - drop entity names that read like funds/SPVs/LPs/real-estate
        ("Fund", "Capital", "Partners", "LP", "Trust", "Realty", "Holdings",
        "Acquisition", ...) — heuristic, so a handful of real operating
        companies with those words may be dropped, and a few vehicles may slip
        through. We bias toward precision (a clean, focused set) over recall.
    Result is a focused ~10-25 operating-company filings from the last ~35 days.

Never raises to the caller: any hard network failure returns [].
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .models import Signal

FTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
# SEC mandates a descriptive User-Agent with a contact email.
USER_AGENT = "launch-deal-flow-agent andrewdimaulozx@gmail.com"

LOOKBACK_DAYS = 35
MAX_FILINGS_SCANNED = 120  # cap full-text hits we examine
MAX_SIGNALS = 25
RATE_DELAY_S = 0.25  # ~4 req/sec, under SEC's 10/sec ceiling

# Entity-name tokens that strongly indicate a fund / SPV / real-estate / holding
# vehicle rather than an operating tech company. Matched as whole words.
_FUND_TOKENS = (
    "fund",
    "funds",
    "capital",
    "partners",
    "advisors",
    "advisers",
    "management",
    "ventures",
    "venture partners",
    "lp",
    "l.p.",
    "trust",
    "realty",
    "real estate",
    "properties",
    "holdings",
    "holding",
    "acquisition",
    "acquisitions",
    "spv",
    "opportunities",
    "investments",
    "investment",
    "equity",
    "growth fund",
    "credit",
    "development",
    "developers",
    "estates",
    "land",
    "leasing",
    "rental",
    "rentals",
    "residences",
    "residential",
    "series",  # SPV series LLCs ("... LLC - X Series")
    "dst",  # Delaware Statutory Trust — real-estate vehicle
    "lllp",
    "eb5",
    "eb-5",
)

# Substrings (not whole words) that unambiguously indicate a real-estate /
# investment vehicle regardless of token boundaries.
_FUND_SUBSTRINGS = ("reit", "subreit")

# industryGroupType values from the Form D XML that we always drop.
_DROP_INDUSTRY = {
    "pooled investment fund",
    "other investment fund",
    "residential",
    "commercial banking",
    "other real estate",
    "reits & finance",
}

# industryGroupType -> our coarse category. Default "AI / software".
_INDUSTRY_CATEGORY = {
    "other technology": "Technology / software",
    "computers": "Technology / software",
    "telecommunications": "Telecom / software",
    "biotechnology": "Biotech / life sciences",
    "pharmaceuticals": "Biotech / life sciences",
    "health insurance": "Healthcare",
    "hospital & physicians": "Healthcare",
    "other health care": "Healthcare",
    "commercial": "Commercial / industrial",
    "manufacturing": "Manufacturing / hardware",
    "energy conservation": "Energy",
    "oil & gas": "Energy",
    "other energy": "Energy",
    "agriculture": "Agriculture",
    "retailing": "Consumer / retail",
    "restaurants": "Consumer / retail",
    "travel": "Consumer / travel",
}


def _fetch(url: str, timeout: int = 25) -> bytes:
    """Fetch raw bytes with the required SEC User-Agent. Cert fallback for macOS."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        if not isinstance(exc, ssl.SSLCertVerificationError) and "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        ctx = ssl._create_unverified_context()  # noqa: SLF001 - local cert fallback only.
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()


def _clean_name(display_name: str) -> str:
    """'Mercury Technologies, Inc.  (CIK 0001719932)' -> 'Mercury Technologies, Inc.'."""
    name = re.sub(r"\s*\(CIK\s*\d+\)\s*$", "", display_name).strip()
    return re.sub(r"\s+", " ", name)


def _looks_like_fund(name: str) -> bool:
    raw = name.lower()
    if any(sub in raw for sub in _FUND_SUBSTRINGS):
        return True
    lowered = re.sub(r"[^a-z0-9.& ]", " ", f" {raw} ")
    lowered = re.sub(r"\s+", " ", lowered)
    for token in _FUND_TOKENS:
        if f" {token} " in lowered:
            return True
    return False


def _index_url(cik: str, adsh: str) -> str:
    """Human-readable filing index page on sec.gov."""
    cik_int = str(int(cik))  # strip leading zeros
    nodash = adsh.replace("-", "")
    return f"{ARCHIVES}/{cik_int}/{nodash}/{adsh}-index.htm"


def _primary_doc_url(cik: str, adsh: str) -> str:
    cik_int = str(int(cik))
    nodash = adsh.replace("-", "")
    return f"{ARCHIVES}/{cik_int}/{nodash}/primary_doc.xml"


def _xml_value(xml: str, tag: str) -> str | None:
    m = re.search(fr"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_file_date(value: str) -> datetime:
    """'2026-05-20' -> tz-aware UTC datetime; fallback to now."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _search_hits() -> list[dict]:
    """Page through Form D full-text hits for the lookback window."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=LOOKBACK_DAYS)
    hits: list[dict] = []
    offset = 0
    while len(hits) < MAX_FILINGS_SCANNED:
        params = (
            f"q=&forms=D&startdt={start.isoformat()}&enddt={end.isoformat()}&from={offset}"
        )
        try:
            raw = _fetch(f"{FTS_URL}?{params}")
            payload = json.loads(raw)
        except Exception:
            break
        page = payload.get("hits", {}).get("hits", [])
        if not page:
            break
        hits.extend(page)
        offset += len(page)
        total = payload.get("hits", {}).get("total", {}).get("value", 0)
        if offset >= total or len(page) < 100:
            break
        time.sleep(RATE_DELAY_S)
    return hits[:MAX_FILINGS_SCANNED]


def _build_signal(source_hit: dict) -> Signal | None:
    src = source_hit.get("_source", {})
    display_names = src.get("display_names") or []
    ciks = src.get("ciks") or []
    adsh = src.get("adsh")
    file_date = src.get("file_date")
    if not display_names or not ciks or not adsh:
        return None

    company = _clean_name(display_names[0])
    if not company or _looks_like_fund(company):
        return None

    cik = ciks[0]
    observed_at = _parse_file_date(file_date)

    # Enrich from primary_doc.xml: industry + offering amount. Best-effort.
    category = "AI / software"
    metric_label = ""
    metric_value: float | None = None
    industry = ""
    try:
        xml = _fetch(_primary_doc_url(cik, adsh)).decode("utf-8", "ignore")
        industry = (_xml_value(xml, "industryGroupType") or "").strip()
        if industry.lower() in _DROP_INDUSTRY:
            return None
        if industry:
            category = _INDUSTRY_CATEGORY.get(industry.lower(), category)
        amount = _xml_value(xml, "totalOfferingAmount")
        if amount and amount.replace(".", "", 1).isdigit():
            value = float(amount)
            # Skip indefinite/zero offerings and obvious mega-vehicle noise is handled
            # by the fund filter; here we just attach a real number when present.
            if value > 0:
                metric_label = "Form D offering (USD)"
                metric_value = value
    except Exception:
        # Enrichment failed — keep the filing on the cheap metadata we already have.
        pass
    finally:
        time.sleep(RATE_DELAY_S)

    desc_bits = [f"Form D filed {file_date}"]
    if industry:
        desc_bits.append(f"industry: {industry}")
    if metric_value is not None:
        desc_bits.append(f"offering: ${metric_value:,.0f}")

    return Signal(
        company=company,
        source="SEC EDGAR Form D",
        signal_type="direct_announcement",
        title=f"{company} filed SEC Form D (exempt offering)",
        url=_index_url(cik, adsh),
        observed_at=observed_at,
        description="; ".join(desc_bits),
        category=category,
        stage="Recently filed Form D (private raise)",
        metric_label=metric_label,
        metric_value=metric_value,
    )


def collect() -> list[Signal]:
    """Return recent operating-company SEC Form D filings as Signals.

    Never raises: returns [] on hard failure.
    """
    try:
        hits = _search_hits()
    except Exception:
        return []

    signals: list[Signal] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        if len(signals) >= MAX_SIGNALS:
            break
        try:
            signal = _build_signal(hit)
        except Exception:
            continue
        if signal is None:
            continue
        key = (signal.company.lower(), signal.observed_at.date().isoformat())
        if key in seen:
            continue
        seen.add(key)
        signals.append(signal)
    return signals


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    results = collect()
    print(f"{len(results)} Form D signals")
    for s in results[:10]:
        amount = f" ${s.metric_value:,.0f}" if s.metric_value else ""
        print(f"- {s.company} | {s.observed_at.date()} | {s.category}{amount}")
        print(f"  {s.url}")
