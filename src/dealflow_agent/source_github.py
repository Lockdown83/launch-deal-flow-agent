from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .models import Signal, now_utc

GITHUB_SEARCH = "https://api.github.com/search/repositories"

# Run a few focused queries against trending AI / infra / dev-tools repos.
# Each query is (topic, label) — we look for recently-pushed repos with real traction.
_QUERIES = [
    "topic:ai",
    "topic:llm",
    "topic:agents",
    "topic:developer-tools",
]

# Per-query result cap. Unauthenticated search is ~10 req/min, so we keep this small.
_PER_PAGE = 25
_LOOKBACK_DAYS = 45
_MIN_STARS = 500

# Noise we don't want as VC traction signals: lists, courses, tutorials, configs.
_NOISE_TERMS = (
    "awesome",
    "awesome-list",
    "tutorial",
    "course",
    "courses",
    "roadmap",
    "cheatsheet",
    "cheat-sheet",
    "interview",
    "dotfiles",
    "bootcamp",
    "handbook",
    "guide",
    "examples",
    "100-days",
    "free-",
)


def _fetch_json(url: str, timeout: int = 25) -> dict:
    """Fetch JSON from the GitHub API with the required headers, stdlib only.

    Mirrors sources.fetch_text but sets the GitHub Accept + User-Agent headers
    and applies the same local-cert fallback used elsewhere in the project.
    """
    headers = {
        "User-Agent": "launch-deal-flow-agent/0.1",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc) and not isinstance(exc, ssl.SSLCertVerificationError):
            raise
        context = ssl._create_unverified_context()  # noqa: SLF001 - MVP fallback for local cert setup.
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))


def _parse_github_date(value: str | None) -> datetime:
    """Parse a GitHub ISO-8601 timestamp (e.g. '2026-05-01T12:00:00Z') as UTC."""
    if not value:
        return now_utc()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return now_utc()


def _is_noise(repo: dict) -> bool:
    name = (repo.get("name") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    description = (repo.get("description") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]
    haystack = f"{name} {full_name} {description} {' '.join(topics)}"
    return any(term in haystack for term in _NOISE_TERMS)


def _category_for(repo: dict) -> str:
    description = (repo.get("description") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]
    text = f"{description} {' '.join(topics)}"
    if any(t in text for t in ["agent", "agents", "autonomous", "orchestrat", "rag", "vector", "memory", "mcp"]):
        return "AI agent infrastructure"
    if any(t in text for t in ["llm", "gpt", "transformer", "inference", "fine-tun", "model", "diffusion", "embedding"]):
        return "AI / software"
    if any(t in text for t in ["cli", "developer-tools", "devtools", "sdk", "framework", "ide", "editor", "build", "deploy"]):
        return "Dev tools"
    if any(t in text for t in ["ai", "machine-learning", "deep-learning", "ml", "neural"]):
        return "AI / software"
    return "AI / software"


def _to_signal(repo: dict) -> Signal:
    full_name = repo.get("full_name") or repo.get("name") or "unknown/unknown"
    name = repo.get("name") or full_name
    description = (repo.get("description") or "").strip()
    short_desc = description[:200]
    stars = float(repo.get("stargazers_count") or 0)
    # Prefer pushed_at (recent activity) but fall back to created_at.
    observed_at = _parse_github_date(repo.get("pushed_at") or repo.get("created_at"))

    title = full_name
    if short_desc:
        title = f"{full_name}: {short_desc[:120]}"

    return Signal(
        company=name,
        source="GitHub trending API",
        signal_type="founder_community",
        title=title,
        url=repo.get("html_url") or f"https://github.com/{full_name}",
        observed_at=observed_at,
        description=short_desc,
        category=_category_for(repo),
        stage="Open-source traction; commercial stage unconfirmed",
        metric_label="GitHub stars",
        metric_value=stars,
    )


def collect() -> list[Signal]:
    """Pull recently-active, high-star AI / infra / dev-tools repos as Signals.

    Runs a few focused GitHub Search queries, merges and dedupes by repo
    full_name, filters obvious noise, and never raises — on rate-limit (403)
    or any other error it returns whatever was gathered so far.
    """
    cutoff = (now_utc() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    seen: dict[str, dict] = {}

    for topic in _QUERIES:
        query = f"{topic} stars:>{_MIN_STARS} pushed:>{cutoff}"
        params = urllib.parse.urlencode(
            {"q": query, "sort": "stars", "order": "desc", "per_page": _PER_PAGE}
        )
        url = f"{GITHUB_SEARCH}?{params}"
        try:
            payload = _fetch_json(url)
        except urllib.error.HTTPError as exc:
            # 403 == rate limited / abuse detection. Stop hitting the API and
            # return what we already have rather than crashing the pipeline.
            if exc.code in (403, 429):
                print(f"WARN: source_github rate-limited on '{topic}' ({exc.code}); returning partial results.")
                break
            print(f"WARN: source_github query '{topic}' failed: {exc}")
            continue
        except Exception as exc:
            print(f"WARN: source_github query '{topic}' failed: {exc}")
            continue

        for repo in payload.get("items", []):
            full_name = repo.get("full_name")
            if not full_name or full_name in seen:
                continue
            if _is_noise(repo):
                continue
            seen[full_name] = repo

    signals = [_to_signal(repo) for repo in seen.values()]
    # Most stars first — strongest traction at the top.
    signals.sort(key=lambda s: s.metric_value or 0.0, reverse=True)
    return signals


if __name__ == "__main__":
    results = collect()
    print(f"{len(results)} signals")
    for signal in results[:8]:
        print(signal.company, signal.metric_value, signal.url)
