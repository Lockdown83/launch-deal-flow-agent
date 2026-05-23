from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Settings
from .models import Opportunity

# NVIDIA NIM is OpenAI-compatible.
_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_CHAT_ENDPOINT = f"{_NIM_BASE}/chat/completions"
_MODELS_ENDPOINT = f"{_NIM_BASE}/models"

_SYSTEM = (
    "You are a sharp deal-flow analyst at LAUNCH, Jason Calacanis's early-stage VC. "
    "You write terse, specific, high-signal rationales for partners deciding whether to chase a "
    "deal. No hedging, no fluff, no buzzword salad, no preamble, no markdown. Be concrete and "
    "opinionated, and ground every claim in the actual signal provided."
)


def _headers(settings: Settings) -> dict:
    return {
        "Authorization": f"Bearer {settings.nim_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "launchy-deal-flow-agent/1.0",
    }


def _reason(settings: Settings, opp: Opportunity) -> str:
    sources = "\n".join(f"- {s}" for s in opp.sources[:5])
    user = (
        f"Company: {opp.company}\n"
        f"Category: {opp.category}\n"
        f"Estimated stage: {opp.stage}\n"
        f"Conviction score: {opp.score}\n"
        f"Trigger: {opp.trigger}\n"
        f"Signals:\n{sources}\n\n"
        "In 2-3 sentences: why is this a deal-flow opportunity LAUNCH should care about RIGHT NOW, "
        "and what is the concrete next action? Lead with the 'why now', reference the actual signal, "
        "and end with the action."
    )
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "top_p": 0.9,
        "max_tokens": 240,
    }
    req = urllib.request.Request(
        _CHAT_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(settings),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # Surface the API body (e.g. unknown model id) so failures are debuggable in logs.
        raise RuntimeError(f"NIM API error {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
    return (data["choices"][0]["message"]["content"] or "").strip()


def enrich_rationale(settings: Settings, opportunities: list[Opportunity]) -> int:
    """Replace each top deal's templated `why_it_matters` with LLM-written reasoning.

    No-op (keeps the templates) when no NIM key is configured. Per-deal failures are swallowed
    so the pipeline never breaks. Returns the number of opportunities enriched.
    """
    if not settings.nim_api_key or not opportunities:
        return 0
    enriched = 0
    for opp in opportunities[: settings.nim_rationale_limit]:
        try:
            text = _reason(settings, opp)
        except Exception as exc:  # noqa: BLE001 - never break the run on a bad LLM call
            print(f"WARN: NIM rationale failed for {opp.company}: {exc}")
            continue
        if text:
            opp.why_it_matters = text
            enriched += 1
    return enriched


def list_models(settings: Settings) -> list[str]:
    """List available NIM model ids — used to confirm the correct Nemotron model string."""
    req = urllib.request.Request(_MODELS_ENDPOINT, headers=_headers(settings), method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return [m.get("id", "") for m in data.get("data", [])]
