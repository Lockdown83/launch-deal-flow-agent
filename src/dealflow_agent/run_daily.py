from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .config import REPO_ROOT, get_settings
from .dashboard import render_dashboard
from .emailer import send_gmail
from .metrics import build_metrics
from .outbound import build_drafts
from .report import format_report
from .scoring import score_signals
from .sources import collect_all_signals
from .storage import save_run


def write_report(body: str) -> Path:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = reports_dir / f"deal-flow-brief-{stamp}.txt"
    path.write_text(body)
    return path


def write_dashboard(html: str) -> Path:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = reports_dir / f"dashboard-{stamp}.html"
    path.write_text(html)
    # Stable filename so the demo/Loom always opens the latest run.
    (reports_dir / "dashboard-latest.html").write_text(html)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LAUNCH deal-flow agent MVP.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--email", action="store_true", help="Email the generated brief using Gmail SMTP.")
    group.add_argument("--no-email", action="store_true", help="Generate report only; do not email.")
    args = parser.parse_args()

    settings = get_settings()
    signals = collect_all_signals()
    opportunities = score_signals(signals, min_score=settings.min_score)

    # Drafted, queued outreach (never auto-sent) — closes the Intake -> Qualify -> Act loop.
    drafts = build_drafts(opportunities)
    sources_monitored = len({s.source for s in signals})

    # Compute metrics BEFORE persisting, so "new this run" compares against prior history.
    # build_metrics merges the current run's signals into the trend itself.
    metrics = build_metrics(signals, opportunities, sources_monitored, len(drafts))
    run_stats = save_run(signals, opportunities, sources_monitored)

    body = format_report(opportunities)
    report_path = write_report(body)
    # Metrics count the full qualified funnel; the dashboard shows the curated top deals.
    dashboard_path = write_dashboard(render_dashboard(opportunities[:15], metrics, drafts))

    print(body)
    print(
        f"\nRun #{run_stats['run_id']}: {len(signals)} signals from {sources_monitored} sources, "
        f"{run_stats['new_signals']} new, {len(opportunities)} qualified, {len(drafts)} drafts queued."
    )
    print(f"Saved report: {report_path}")
    print(f"Saved dashboard: {dashboard_path}")

    if args.email:
        subject = f"LAUNCH Deal Flow Brief - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        send_gmail(settings, subject=subject, body=body)
        print(f"Emailed report to {settings.email_to}")
    else:
        print("Email not sent. Use --email after configuring .env Gmail settings.")


if __name__ == "__main__":
    main()
