"""Message templates, one per reminder stage."""

from datetime import date
from typing import Tuple

# Stage names, in escalation order.
UPCOMING = "upcoming"
DUE_TODAY = "due_today"
OVERDUE_1 = "overdue_1"
OVERDUE_7 = "overdue_7"

STAGES = [UPCOMING, DUE_TODAY, OVERDUE_1, OVERDUE_7]


def render(stage: str, loan, company: str, currency: str, today: date) -> Tuple[str, str]:
    """Return (subject, body) for the given stage and loan row."""
    due = date.fromisoformat(loan["due_date"])
    days = (due - today).days
    amount = f"{currency} {loan['amount_due']:,.2f}"
    name = loan["borrower_name"]
    lid = loan["loan_id"]
    due_txt = due.strftime("%d %b %Y")

    if stage == UPCOMING:
        subject = f"Reminder: payment of {amount} due in {days} day(s)"
        body = (
            f"Dear {name},\n\n"
            f"This is a friendly reminder that your loan repayment of {amount} "
            f"(Loan ID: {lid}) is due on {due_txt}, which is {days} day(s) away.\n\n"
            f"Paying on time keeps your account in good standing.\n"
        )
    elif stage == DUE_TODAY:
        subject = f"Payment of {amount} is due today"
        body = (
            f"Dear {name},\n\n"
            f"Your loan repayment of {amount} (Loan ID: {lid}) is due today, {due_txt}.\n\n"
            f"Please make your payment today to avoid late charges.\n"
        )
    elif stage == OVERDUE_1:
        late = -days
        subject = f"Payment overdue: {amount} (Loan ID {lid})"
        body = (
            f"Dear {name},\n\n"
            f"Our records show that your repayment of {amount} (Loan ID: {lid}), "
            f"due on {due_txt}, is now {late} day(s) overdue.\n\n"
            f"Please pay as soon as possible. If you have already paid, kindly ignore this message.\n"
        )
    elif stage == OVERDUE_7:
        late = -days
        subject = f"Final notice: {amount} overdue by {late} days (Loan ID {lid})"
        body = (
            f"Dear {name},\n\n"
            f"Your repayment of {amount} (Loan ID: {lid}), due on {due_txt}, is now "
            f"{late} days overdue. Late charges may apply and further delay can affect "
            f"your credit standing.\n\n"
            f"Please contact us immediately to settle the payment or discuss options.\n"
        )
    else:
        raise ValueError(f"Unknown stage: {stage}")

    body += f"\nRegards,\n{company}\n"
    return subject, body
