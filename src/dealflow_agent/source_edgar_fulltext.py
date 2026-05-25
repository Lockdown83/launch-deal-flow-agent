"""SEC EDGAR full-text source — extends Form D with the IPO pipeline + crowdfunding raises.

Uses the same free EFTS endpoint as source_edgar (Form D), but filters to:
  - S-1 / S-1/A / 424B4  -> a company registering / pricing an IPO (late-stage "going public")
  - C / C-U              -> a Reg-CF crowdfunding raise (early-stage "raising now")

Reuses source_edgar's fetch (with the SEC-mandated User-Agent), name cleaner, fund filter, and
filing-index URL helper. Filer names are structured, so extraction is clean. Never raises: [].
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

from .models import Signal
from .source_edgar import (
    FTS_URL,
    _clean_name,
    _fetch,
    _index_url,
    _looks_like_fund,
    _parse_file_date,
)

FORMS = "S-1,S-1/A,424B4,C,C-U"
LOOKBACK_DAYS = 30
MAX_SCAN = 120
MAX_SIGNALS = 18
RATE_DELAY_S = 0.25

# ETFs / SPACs / blank-check / index vehicles dominate S-1 volume but aren't deal flow.
_VEHICLE_TOKENS = ("etf", "staked", "index fund", "spac", "acquisition corp", "blank check",
                   "trust", "etn", "shares trust")


def _is_vehicle(name: str) -> bool:
    low = name.lower()
    return any(tok in low for tok in _VEHICLE_TOKENS)


# form -> (title verb phrase, stage)
_FORM_DESC = {
    "S-1": ("filed an S-1 (IPO registration)", "Registered to IPO (S-1)"),
    "S-1/A": ("amended its S-1 (IPO registration)", "Registered to IPO (S-1/A)"),
    "424B4": ("priced its IPO (424B4 prospectus)", "Priced IPO (424B4)"),
    "C": ("filed a Form C (Reg-CF crowdfunding raise)", "Reg-CF raise (Form C)"),
    "C-U": ("updated a Form C (Reg-CF raise)", "Reg-CF raise (Form C-U)"),
}


def _search_hits() -> list[dict]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=LOOKBACK_DAYS)
    hits: list[dict] = []
    offset = 0
    while len(hits) < MAX_SCAN:
        params = f"q=&forms={FORMS}&startdt={start.isoformat()}&enddt={end.isoformat()}&from={offset}"
        try:
            payload = json.loads(_fetch(f"{FTS_URL}?{params}"))
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
    return hits[:MAX_SCAN]


def _build(hit: dict) -> Signal | None:
    src = hit.get("_source", {})
    names = src.get("display_names") or []
    ciks = src.get("ciks") or []
    adsh = src.get("adsh")
    file_date = src.get("file_date")
    if not names or not ciks or not adsh:
        return None
    company = _clean_name(names[0])
    company = re.sub(r"\s*\([^)]*\)\s*$", "", company).strip()  # drop trailing "(VIVK)" / "(CIK …)"
    if not company or _looks_like_fund(company) or _is_vehicle(company):
        return None
    form = (src.get("file_type") or src.get("root_form") or "").upper()
    verb, stage = _FORM_DESC.get(form, ("filed with the SEC", "SEC filing"))
    return Signal(
        company=company,
        source="SEC EDGAR full-text",
        signal_type="regulatory_filing",
        title=f"{company} {verb}",
        url=_index_url(ciks[0], adsh),
        observed_at=_parse_file_date(file_date),
        description=f"{form} filed {file_date}",
        category="Capital markets",
        stage=stage,
    )


def collect() -> list[Signal]:
    """Recent S-1 / Reg-CF filings as Signals. Never raises; [] on failure."""
    try:
        hits = _search_hits()
    except Exception:
        return []
    out: list[Signal] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        if len(out) >= MAX_SIGNALS:
            break
        try:
            signal = _build(hit)
        except Exception:
            continue
        if signal is None:
            continue
        key = (signal.company.lower(), signal.observed_at.date().isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append(signal)
    return out


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    r = collect()
    print(f"{len(r)} EDGAR full-text signals")
    for s in r[:12]:
        print(f"- {s.company} | {s.stage} | {s.observed_at.date()}")
