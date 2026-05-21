from __future__ import annotations

import argparse

from .config import get_settings
from .emailer import send_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a Gmail SMTP test email.")
    parser.add_argument("--body", default="test")
    parser.add_argument("--subject", default="test")
    args = parser.parse_args()

    settings = get_settings()
    send_email(settings, subject=args.subject, body=args.body)
    print(f"Sent test email to {settings.email_to}")


if __name__ == "__main__":
    main()
