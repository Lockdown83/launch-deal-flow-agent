from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .config import REPO_ROOT, get_settings
from .emailer import send_gmail
from .report import format_report
from .scoring import score_signals
from .sources import collect_all_signals


def write_report(body: str) -> Path:
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = reports_dir / f"deal-flow-brief-{stamp}.txt"
    path.write_text(body)
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
    body = format_report(opportunities)
    report_path = write_report(body)

    print(body)
    print(f"\nSaved report: {report_path}")

    if args.email:
        subject = f"LAUNCH Deal Flow Brief - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        send_gmail(settings, subject=subject, body=body)
        print(f"Emailed report to {settings.email_to}")
    else:
        print("Email not sent. Use --email after configuring .env Gmail settings.")


if __name__ == "__main__":
    main()
