"""Core logic: decide which reminder (if any) each loan needs today, and send it."""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from . import db, templates
from .notifier import NotificationError, Notifier


def determine_stage(due: date, today: date) -> Optional[str]:
    """Map 'days until due' to a reminder stage.

    Using ranges (not exact days) means a missed run still catches up: if the bot
    was down on the due date, the loan gets the right message on the next run.
    """
    days = (due - today).days
    if days > 3:
        return None  # too early
    if days > 0:
        return templates.UPCOMING
    if days == 0:
        return templates.DUE_TODAY
    if days > -7:
        return templates.OVERDUE_1
    return templates.OVERDUE_7


@dataclass
class RunSummary:
    sent: int = 0
    skipped_already_sent: int = 0
    skipped_not_due: int = 0
    skipped_no_contact: int = 0
    failed: int = 0
    details: List[str] = field(default_factory=list)


def run_reminders(conn, notifier: Notifier, today: date, company: str, currency: str,
                  record: bool = True) -> RunSummary:
    """Process all pending loans. When record=False (dry run) nothing is logged,
    so a later real run still sends everything."""
    summary = RunSummary()
    for loan in db.pending_loans(conn):
        due = date.fromisoformat(loan["due_date"])
        stage = determine_stage(due, today)

        if stage is None:
            summary.skipped_not_due += 1
            continue
        if db.already_sent(conn, loan["loan_id"], stage):
            summary.skipped_already_sent += 1
            continue
        if not notifier.can_notify(loan):
            summary.skipped_no_contact += 1
            summary.details.append(f"{loan['loan_id']}: no usable contact for {notifier.channel}")
            continue

        subject, body = templates.render(stage, loan, company, currency, today)
        try:
            notifier.send(loan, subject, body)
        except NotificationError as exc:
            summary.failed += 1
            summary.details.append(f"{loan['loan_id']}: send failed ({exc})")
            if record:
                db.log_reminder(conn, loan["loan_id"], stage, notifier.channel, False, str(exc))
            continue

        summary.sent += 1
        summary.details.append(f"{loan['loan_id']}: {stage} sent via {notifier.channel}")
        if record:
            db.log_reminder(conn, loan["loan_id"], stage, notifier.channel, True)
    return summary
