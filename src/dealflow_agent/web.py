from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone

from flask import Flask, redirect, request, url_for

from .analyst import answer_question, editor_note, enrich_rationale
from .config import get_settings
from .dashboard import render_dashboard
from .emailer import send_email
from .metrics import build_metrics
from .outbound import build_drafts
from .report import format_report
from .scoring import score_signals
from .sources import collect_all_signals
from .storage import save_run

app = Flask(__name__)

# How often the background loop re-runs the full pipeline (scrape -> score -> persist).
REFRESH_HOURS = float(os.getenv("REFRESH_HOURS", "6"))
# Light abuse guard for the public email form: cap global sends per rolling hour.
_MAX_SENDS_PER_HOUR = int(os.getenv("MAX_SENDS_PER_HOUR", "40"))
# Abuse guard for the public Ask LAUNCHY endpoint (caps NIM calls from the open form).
_MAX_ASKS_PER_HOUR = int(os.getenv("MAX_ASKS_PER_HOUR", "60"))

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Live in-memory snapshot of the latest run, refreshed by the background thread so
# page loads and email sends never block on the network.
_cache: dict = {
    "opps": [],
    "metrics": None,
    "drafts": [],
    "brief": "",
    "editor_note": "",
    "ready": False,
    "updated": None,
}
_lock = threading.Lock()
_send_times: deque[float] = deque()
_ask_times: deque[float] = deque()
_started = False
_start_lock = threading.Lock()


def _run_pipeline() -> None:
    """One full pass: collect -> score -> draft -> metrics -> persist; update the cache."""
    settings = get_settings()
    signals = collect_all_signals()
    opps = score_signals(signals, min_score=settings.min_score)
    # The brain (NVIDIA NIM): per-deal verdict + memo, then the slate-level editor note.
    # Both are graceful no-ops without a key.
    enrich_rationale(settings, opps)
    note = editor_note(settings, opps)
    drafts = build_drafts(opps)
    sources_monitored = len({s.source for s in signals})
    metrics = build_metrics(signals, opps, sources_monitored, len(drafts))
    try:
        save_run(signals, opps, sources_monitored)
    except Exception as exc:  # persistence is best-effort; never break the live view
        app.logger.warning("save_run failed: %s", exc)
    brief = format_report(opps, editor_note=note)
    with _lock:
        _cache.update(
            opps=opps,
            metrics=metrics,
            drafts=drafts,
            brief=brief,
            editor_note=note,
            ready=True,
            updated=datetime.now(timezone.utc),
        )
    app.logger.info("pipeline refreshed: %d signals, %d qualified", len(signals), len(opps))


def _refresh_loop() -> None:
    interval = max(600.0, REFRESH_HOURS * 3600.0)
    while True:
        try:
            _run_pipeline()
        except Exception as exc:
            app.logger.exception("pipeline run failed: %s", exc)
        time.sleep(interval)


def _ensure_background_started() -> None:
    """Start the single refresh thread once, on first import/request (gunicorn --workers 1)."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_refresh_loop, name="memosoni-refresh", daemon=True).start()


_ensure_background_started()


_WARMING_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="6">
<title>LAUNCHY — warming up</title>
<style>
  body { margin:0; background:#0a0a0f; color:#39FF14; height:100vh; display:flex;
    align-items:center; justify-content:center; text-align:center;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .box { max-width:520px; padding:0 24px; }
  h1 { letter-spacing:.08em; font-size:20px; }
  p { color:#8b90a0; line-height:1.7; }
  .blink { animation: b 1.2s steps(2) infinite; } @keyframes b { 50% { opacity:0; } }
</style></head>
<body><div class="box">
  <h1>&#9658; LAUNCHY BOOTING<span class="blink">_</span></h1>
  <p>First scan in progress — pulling live signals from Sequoia, a16z, YC, GitHub,
  SEC EDGAR &amp; Hacker News. This page refreshes automatically.</p>
</div></body></html>"""


def _rate_ok() -> bool:
    now = time.time()
    while _send_times and now - _send_times[0] > 3600:
        _send_times.popleft()
    if len(_send_times) >= _MAX_SENDS_PER_HOUR:
        return False
    _send_times.append(now)
    return True


def _ask_ok() -> bool:
    now = time.time()
    while _ask_times and now - _ask_times[0] > 3600:
        _ask_times.popleft()
    if len(_ask_times) >= _MAX_ASKS_PER_HOUR:
        return False
    _ask_times.append(now)
    return True


@app.get("/")
def index() -> str:
    _ensure_background_started()
    with _lock:
        ready = _cache["ready"]
        opps = list(_cache["opps"])
        metrics = _cache["metrics"]
        drafts = list(_cache["drafts"])
        note = _cache["editor_note"]
    if not ready or metrics is None:
        return _WARMING_PAGE
    sent = request.args.get("sent")
    notice, ok = "", True
    if sent == "1":
        notice, ok = "Sent — the brief is in your inbox (check spam just in case).", True
    elif sent == "err":
        notice, ok = "Could not send — check the address and try again.", False
    elif sent == "rate":
        notice, ok = "Whoa — too many requests right now. Try again in a bit.", False
    return render_dashboard(
        opps[:15], metrics, drafts, include_email_form=True, notice=notice, notice_ok=ok,
        editor_note=note,
    )


@app.post("/request-report")
def request_report():
    email = (request.form.get("email") or "").strip()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        return redirect(url_for("index", sent="err"))
    if not _rate_ok():
        return redirect(url_for("index", sent="rate"))
    with _lock:
        brief = _cache["brief"]
        ready = _cache["ready"]
    if not ready or not brief:
        return redirect(url_for("index", sent="err"))
    try:
        settings = get_settings()
        subject = f"LAUNCHY Deal Flow Brief — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        send_email(settings, subject=subject, body=brief, to=email)
    except Exception as exc:
        app.logger.exception("email send failed: %s", exc)
        return redirect(url_for("index", sent="err"))
    return redirect(url_for("index", sent="1"))


@app.post("/ask")
def ask():
    """Ask LAUNCHY: answer a free-form question grounded in the current deal board. Public + guarded."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or request.form.get("question") or "").strip()
    if not question:
        return {"answer": "Ask me something about this week's board."}
    if not _ask_ok():
        return {"answer": "Too many questions right now — give it a minute and try again."}
    with _lock:
        opps = list(_cache["opps"])
        note = _cache["editor_note"]
        ready = _cache["ready"]
    if not ready:
        return {"answer": "Still warming up — the first scan isn't done yet. Try again in a moment."}
    try:
        ans = answer_question(get_settings(), question, opps, editor_note=note)
    except Exception as exc:
        app.logger.exception("ask failed: %s", exc)
        ans = ""
    if not ans:
        ans = "Ask LAUNCHY is offline here (no model key configured) — it answers live on the deployed site."
    return {"answer": ans}


@app.get("/health")
def health():
    with _lock:
        updated = _cache["updated"]
        ready = _cache["ready"]
    return {"ok": True, "ready": ready, "updated": updated.isoformat() if updated else None}


if __name__ == "__main__":
    # Local dev only; production uses gunicorn (see Procfile). No reloader: it would
    # spawn a duplicate refresh thread.
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), debug=False, use_reloader=False)
