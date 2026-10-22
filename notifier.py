"""Notification channels. Subclass Notifier to add SMS, WhatsApp, Slack, etc."""

import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage


class NotificationError(Exception):
    """Raised when a notification could not be delivered."""


class Notifier(ABC):
    channel = "unknown"

    @abstractmethod
    def can_notify(self, loan) -> bool:
        """Whether this channel has the contact detail it needs for this loan."""

    @abstractmethod
    def send(self, loan, subject: str, body: str) -> None:
        """Deliver the message or raise NotificationError."""


class ConsoleNotifier(Notifier):
    """Dry-run channel: prints messages instead of sending them.

    Mirrors EmailNotifier's rules (email address required) so a dry run shows
    exactly what a real run would do.
    """

    channel = "console"

    def can_notify(self, loan) -> bool:
        return bool(loan["email"])

    def send(self, loan, subject: str, body: str) -> None:
        print(f"--- [DRY RUN] to {loan['borrower_name']} <{loan['email']}> ---")
        print(f"Subject: {subject}\n")
        print(body)


class EmailNotifier(Notifier):
    """Sends reminders over SMTP."""

    channel = "email"

    def __init__(self, host, port, user, password, from_email, use_tls=True):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def can_notify(self, loan) -> bool:
        return bool(loan["email"])

    def send(self, loan, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_email
        msg["To"] = loan["email"]
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotificationError(str(exc)) from exc
