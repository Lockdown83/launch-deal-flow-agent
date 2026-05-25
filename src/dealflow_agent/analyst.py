from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from .config import Settings
from .models import Opportunity

# NVIDIA NIM is OpenAI-compatible.
_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_CHAT_ENDPOINT = f"{_NIM_BASE}/chat/completions"
_MODELS_ENDPOINT = f"{_NIM_BASE}/models"

_VALID_VERDICTS = {"CHASE", "WATCH", "TRACK"}

# Nemotron reasoning models emit a long <think> trace by default (slow, can overrun the token
# budget before the answer). Prepending this makes them answer directly; applied only for nemotron
# models in `_chat`. The default model (meta/llama-3.3-70b-instruct) is a fast non-reasoning model.
_THINKING_OFF = "detailed thinking off"

# The Analyst writes a structured per-deal judgement. The math (scoring.py) already found the deal;
# the analyst's job is the WORDS and the VERDICT — grounded only in the signals we hand it.
_ANALYST_SYSTEM = (
    "You are a sharp deal-flow analyst at LAUNCH, Jason Calacanis's early-stage VC. "
    "You decide how hard a partner should lean into a startup based ONLY on the public signals "
    "provided. Ground EVERY claim in the actual signal — name what the product does, who is behind "
    "it, and the specific traction or fact in the signal. If a detail isn't in the signal, don't "
    "assert it; say what's unknown instead of inventing it. Be concrete and opinionated; cut "
    "adjectives, hedging, and filler. "
    "BANNED WORDS — never use any of these: revolutionize, revolutionary, cutting-edge, "
    "game-changer, transform, transformative, disrupt, disruptive, seamless, robust, leverage, "
    "synergy, next-generation, best-in-class, 'the future of', 'could be huge', promising, "
    "innovative, groundbreaking. Prefer concrete specifics (what it does, who built it, the real "
    "traction) over any adjective. "
    "You ALWAYS respond with a single minified JSON object and nothing else — no markdown, no code "
    "fences, no commentary before or after."
)

# The Editor reads the whole qualified slate and writes the brief's opening thesis.
_EDITOR_SYSTEM = (
    "You are the editor of LAUNCH's deal-flow brief. You write a tight, partner-facing "
    "'what matters this week' note: name the concrete through-line connecting the slate (the actual "
    "shared category/buyer/shift, not a vague theme), call out the single most urgent company with a "
    "real reason it's urgent (who's behind it, what the signal shows), and end on a specific next "
    "step. Ground every claim in the slate you're given. No hedging, no fluff, no preamble, no markdown. "
    "BANNED WORDS — never use any of these: revolutionize, revolutionary, cutting-edge, "
    "game-changer, transform, transformative, disrupt, disruptive, seamless, robust, leverage, "
    "synergy, next-generation, best-in-class, 'the future of', 'could be huge', promising, "
    "innovative, groundbreaking. "
    "2-3 sentences of plain text."
)


def _headers(settings: Settings) -> dict:
    return {
        "Authorization": f"Bearer {settings.nim_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "launchy-deal-flow-agent/1.0",
    }


def _chat(settings: Settings, system: str, user: str, *, max_tokens: int, temperature: float = 0.4) -> str:
    """One NIM chat-completion, with retry on transient 5xx / timeouts.

    Raises RuntimeError (with the API body) on a non-retryable HTTP error.
    """
    if "nemotron" in settings.nim_model.lower():  # reasoning models: answer directly, don't <think>
        system = f"{_THINKING_OFF}\n\n{system}"
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    last_exc: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(_CHAT_ENDPOINT, data=data, headers=_headers(settings), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read())
            return (body["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "ignore")
            # 429 (rate limit) + 5xx (e.g. NIM's intermittent "Already borrowed") are transient —
            # back off and retry (longer pause for 429). Other 4xx (bad model id etc.) is fatal.
            if (exc.code == 429 or exc.code >= 500) and attempt < 2:
                last_exc = RuntimeError(f"NIM API error {exc.code}: {text}")
                time.sleep((3.0 if exc.code == 429 else 1.5) * (attempt + 1))
                continue
            raise RuntimeError(f"NIM API error {exc.code}: {text}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_exc if last_exc else RuntimeError("NIM chat failed")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of model output, tolerating code fences or a reasoning preamble."""
    t = text.strip()
    if t.startswith("```"):  # strip ```json ... ``` fences
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t).rstrip("`").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # Fall back to the first balanced {...} block (handles a stray preamble before the JSON).
    start = t.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start : i + 1])
    raise ValueError("unbalanced JSON in model output")


def _analyze(settings: Settings, opp: Opportunity) -> dict:
    """One NIM call → structured judgement for a single deal."""
    sources = "\n".join(f"- {s}" for s in opp.sources[:5]) or "- (none)"
    user = (
        f"Company: {opp.company}\n"
        f"Inferred category: {opp.category}\n"
        f"Estimated stage: {opp.stage}\n"
        f"Convergence score: {opp.score} (higher = more independent public sources corroborate)\n"
        f"Most recent trigger: {opp.trigger}\n"
        f"Signals (source: headline (url)):\n{sources}\n\n"
        "Verdict guide — everything here already cleared our bar, so judge HOW HARD to lean in:\n"
        "  CHASE = move now; WATCH = warm, not yet; TRACK = on the radar.\n"
        "Rules: ground every field in the signals above — quote the specific source, headline, or "
        "fact. Don't invent traction, funding, or product details that aren't in the signal; if it's "
        "unknown, name the unknown. No adjectives-as-substance, no hedging, no banned words "
        "(revolutionize, cutting-edge, game-changer, transform, disrupt, seamless, robust, leverage, "
        "synergy, next-generation, best-in-class, 'the future of', 'could be huge', promising, "
        "innovative, groundbreaking).\n"
        "Return ONLY this JSON object (no other text):\n"
        "{"
        '"one_liner":"what the company actually does, <=12 words, concrete and specific, no hype",'
        '"why_now":"1 sentence: the timing thesis tied to the specific signal above (name the source/fact)",'
        '"bull_case":"1 sentence: the strongest concrete reason this could be a big outcome",'
        '"key_risk":"1 sentence: the single biggest specific risk or unknown",'
        '"verdict":"one of CHASE, WATCH, TRACK",'
        '"conviction_reason":"1 short sentence: which sources corroborate and why that is real signal, not noise"'
        "}"
    )
    data = _extract_json(_chat(settings, _ANALYST_SYSTEM, user, max_tokens=320))
    return data if isinstance(data, dict) else {}


def _clean(value, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def enrich_rationale(settings: Settings, opportunities: list[Opportunity]) -> int:
    """Replace each top deal's templated rationale with the LLM analyst's structured judgement.

    No-op (keeps the templated `why_it_matters`) when no NIM key is configured. Per-deal failures
    are swallowed so the pipeline never breaks. Mutates the Opportunity objects in place and returns
    the number enriched.
    """
    if not settings.nim_api_key or not opportunities:
        return 0
    enriched = 0
    for opp in opportunities[: settings.nim_rationale_limit]:
        try:
            data = _analyze(settings, opp)
        except Exception as exc:  # noqa: BLE001 - never break the run on a bad LLM call
            print(f"WARN: NIM analysis failed for {opp.company}: {exc}")
            continue
        verdict = _clean(data.get("verdict"), 12).upper()
        opp.verdict = verdict if verdict in _VALID_VERDICTS else "WATCH"
        opp.one_liner = _clean(data.get("one_liner"), 140)
        opp.why_now = _clean(data.get("why_now"))
        opp.key_risk = _clean(data.get("key_risk"))
        opp.conviction_reason = _clean(data.get("conviction_reason"))
        # Keep the legacy/fallback field populated so report + outbound show LLM content too.
        synthesized = _clean(data.get("bull_case")) or opp.why_now
        if synthesized:
            opp.why_it_matters = synthesized
        enriched += 1
    return enriched


def editor_note(settings: Settings, opportunities: list[Opportunity]) -> str:
    """One NIM call → the brief's 'what matters this week' thesis over the whole slate.

    Returns "" when no key is set or on any failure (the brief simply omits the note).
    """
    if not settings.nim_api_key or not opportunities:
        return ""
    top = opportunities[:12]
    slate = "\n".join(
        f"- {o.company} | {o.category} | verdict={o.verdict or 'n/a'} | "
        f"{o.one_liner or o.why_it_matters[:80]}"
        for o in top
    )
    user = (
        f"This week's qualified deal slate ({len(opportunities)} total, top {len(top)} shown):\n"
        f"{slate}\n\n"
        "Write the 2-3 sentence 'what matters this week' note for a LAUNCH partner. Lead with the "
        "concrete through-line actually connecting these companies (the shared category/buyer/shift, "
        "named specifically — not a vague theme). Name the single most urgent company and the real "
        "reason it's urgent. End on a specific next step. Ground it all in the slate above; no hype, "
        "no banned words."
    )
    try:
        return _chat(settings, _EDITOR_SYSTEM, user, max_tokens=220, temperature=0.5)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: NIM editor note failed: {exc}")
        return ""


_ASK_SYSTEM = (
    "You are LAUNCHY, LAUNCH's deal-flow agent. Answer the user's question using ONLY the deal data "
    "provided below. Be concise and specific, name companies, and cite the verdict or signal when it "
    "helps. Ground every claim in the data — don't invent facts. If the answer isn't in the data, say "
    "so plainly. No hype or filler, no banned words (revolutionize, cutting-edge, game-changer, "
    "transform, disrupt, seamless, robust, leverage, synergy, next-generation, best-in-class, 'the "
    "future of', promising). No markdown, no preamble."
)


def answer_question(
    settings: Settings, question: str, opportunities: list[Opportunity], editor_note: str = ""
) -> str:
    """Answer a free-form question grounded in the current deal board (the 'Ask LAUNCHY' feature).

    Returns "" when no key is set, the question is empty, or the call fails — the caller turns that
    into a friendly offline message.
    """
    if not settings.nim_api_key:
        return ""
    q = (question or "").strip()[:500]
    if not q:
        return ""
    top = opportunities[:15]
    board = "\n".join(
        f"- {o.company} | {o.category} | verdict={o.verdict or 'n/a'} | score={o.score} | "
        f"{o.one_liner or o.why_it_matters[:80]} | why_now: {o.why_now or 'n/a'} | "
        f"risk: {o.key_risk or 'n/a'}"
        for o in top
    )
    context = (f"This week's editor note: {editor_note}\n\n" if editor_note else "")
    user = (
        f"{context}This week's qualified deal board (top {len(top)} of {len(opportunities)}):\n"
        f"{board}\n\nQuestion: {q}\n\nAnswer in 1-4 sentences."
    )
    try:
        return _chat(settings, _ASK_SYSTEM, user, max_tokens=320, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: NIM ask failed: {exc}")
        return ""


def list_models(settings: Settings) -> list[str]:
    """List available NIM model ids — used to confirm the correct Nemotron model string."""
    req = urllib.request.Request(_MODELS_ENDPOINT, headers=_headers(settings), method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return [m.get("id", "") for m in data.get("data", [])]
