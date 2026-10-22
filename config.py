"""Configuration loaded from environment variables (optionally via a .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (existing vars win)."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    db_path: str = "reminders.db"
    company_name: str = "Credex"
    currency_symbol: str = "Rs."
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    from_email: str = ""

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.from_email)

    @classmethod
    def from_env(cls) -> "Config":
        load_env()
        return cls(
            db_path=os.getenv("DB_PATH", "reminders.db"),
            company_name=os.getenv("COMPANY_NAME", "Credex"),
            currency_symbol=os.getenv("CURRENCY_SYMBOL", "Rs."),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
            from_email=os.getenv("FROM_EMAIL", ""),
        )
