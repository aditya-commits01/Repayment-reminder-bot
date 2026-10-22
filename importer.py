"""CSV import with row-level validation."""

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List

from . import db

REQUIRED_COLUMNS = ["loan_id", "borrower_name", "email", "phone", "amount_due", "due_date"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ImportResult:
    imported: int = 0
    errors: List[str] = field(default_factory=list)


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def import_csv(conn, path: str) -> ImportResult:
    """Import loans from a CSV file. Bad rows are skipped and reported, not fatal."""
    result = ImportResult()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")

        for line_no, row in enumerate(reader, start=2):  # line 1 is the header
            try:
                loan_id = (row["loan_id"] or "").strip()
                name = (row["borrower_name"] or "").strip()
                email = (row["email"] or "").strip()
                phone = (row["phone"] or "").strip()
                if not loan_id or not name:
                    raise ValueError("loan_id and borrower_name are required")
                if not email and not phone:
                    raise ValueError("at least one of email or phone is required")
                if email and not EMAIL_RE.match(email):
                    raise ValueError(f"invalid email '{email}'")
                amount = float(row["amount_due"])
                if amount <= 0:
                    raise ValueError("amount_due must be positive")
                due = parse_date(row["due_date"])
            except (ValueError, TypeError, AttributeError) as exc:
                result.errors.append(f"line {line_no}: {exc}")
                continue

            db.upsert_loan(conn, loan_id, name, email, phone, amount, due)
            result.imported += 1
    conn.commit()
    return result
