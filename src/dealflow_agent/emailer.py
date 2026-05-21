from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings


def send_gmail(settings: Settings, subject: str, body: str) -> None:
    """Send an email via Gmail SMTP using an App Password."""
    missing = []
    if not settings.gmail_user:
        missing.append("GMAIL_USER")
    if not settings.gmail_app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if not settings.email_from:
        missing.append("EMAIL_FROM")
    if missing:
        raise RuntimeError(
            "Missing Gmail config: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in Gmail App Password settings."
        )

    gmail_user = settings.gmail_user
    gmail_app_password = settings.gmail_app_password
    email_from = settings.email_from
    assert gmail_user is not None
    assert gmail_app_password is not None
    assert email_from is not None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = settings.email_to
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_app_password)
        smtp.send_message(msg)
