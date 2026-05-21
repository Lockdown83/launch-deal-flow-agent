from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from .config import Settings

_RESEND_ENDPOINT = "https://api.resend.com/emails"


def send_email(settings: Settings, subject: str, body: str, to: str | None = None) -> None:
    """Send an email, preferring the Resend HTTP API.

    Cloud hosts (Railway, Vercel, etc.) block outbound SMTP, so when a Resend API key is
    configured we send over HTTPS. Falls back to Gmail SMTP locally (where SMTP works) if
    no Resend key is set. `to` overrides the default recipient (used by the web form).
    """
    recipient = to or settings.email_to
    if settings.resend_api_key:
        _send_via_resend(settings, subject, body, recipient)
    else:
        _send_via_smtp(settings, subject, body, recipient)


def _send_via_resend(settings: Settings, subject: str, body: str, recipient: str) -> None:
    payload = json.dumps(
        {
            "from": settings.resend_from,
            "to": [recipient],
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _RESEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Cloudflare (in front of api.resend.com) blocks the default urllib UA.
            "User-Agent": "Mozilla/5.0 (compatible; LAUNCHY/1.0; +https://memosoni.com)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        # Surface Resend's error body (e.g. unverified domain, restricted recipient) so it
        # shows up in logs instead of a generic failure.
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"Resend API error {exc.code}: {detail}") from exc


def _send_via_smtp(settings: Settings, subject: str, body: str, recipient: str) -> None:
    """Gmail SMTP — used only for local runs; cloud hosts block these ports."""
    missing = []
    if not settings.gmail_user:
        missing.append("GMAIL_USER")
    if not settings.gmail_app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if not settings.email_from:
        missing.append("EMAIL_FROM")
    if missing:
        raise RuntimeError(
            "No RESEND_API_KEY set and missing Gmail SMTP config: "
            + ", ".join(missing)
            + ". Set RESEND_API_KEY (recommended) or fill in Gmail App Password settings."
        )

    gmail_user = settings.gmail_user
    gmail_app_password = settings.gmail_app_password
    assert gmail_user is not None
    assert gmail_app_password is not None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_app_password)
        smtp.send_message(msg)
