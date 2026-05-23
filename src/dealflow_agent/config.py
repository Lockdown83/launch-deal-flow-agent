from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """Tiny .env loader to avoid adding dependencies for the MVP."""
    env_path = path or REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    gmail_user: str | None
    gmail_app_password: str | None
    email_to: str
    email_from: str | None
    min_score: float
    # Resend HTTP email API (works on cloud hosts that block SMTP). Preferred when set.
    resend_api_key: str | None
    resend_from: str
    # NVIDIA NIM (OpenAI-compatible) for LLM-written per-deal rationale. Optional — falls
    # back to templated rationale when no key is set.
    nim_api_key: str | None
    nim_model: str
    nim_rationale_limit: int


def get_settings() -> Settings:
    load_dotenv()
    gmail_user = os.getenv("GMAIL_USER")
    email_from = os.getenv("EMAIL_FROM") or gmail_user
    return Settings(
        gmail_user=gmail_user,
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD"),
        email_to=os.getenv("EMAIL_TO", "andrewdimaulozx@gmail.com"),
        email_from=email_from,
        min_score=float(os.getenv("MIN_SCORE", "2.0")),
        resend_api_key=os.getenv("RESEND_API_KEY"),
        resend_from=os.getenv("RESEND_FROM", "onboarding@resend.dev"),
        nim_api_key=os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY"),
        nim_model=os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1"),
        nim_rationale_limit=int(os.getenv("NIM_RATIONALE_LIMIT", "15")),
    )
