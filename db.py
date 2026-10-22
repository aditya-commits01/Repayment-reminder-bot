"""SQLite persistence: loans and a reminder log used to prevent duplicate sends."""

import sqlite3
from datetime import date, datetime
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS loans (
    loan_id       TEXT PRIMARY KEY,
    borrower_name TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    amount_due    REAL NOT NULL,
    due_date      TEXT NOT NULL,              -- ISO date, YYYY-MM-DD
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid'))
);

CREATE TABLE IF NOT EXISTS reminder_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id   TEXT NOT NULL REFERENCES loans(loan_id),
    stage     TEXT NOT NULL,
    channel   TEXT NOT NULL,
    sent_at   TEXT NOT NULL,
    success   INTEGER NOT NULL,
    error     TEXT
);

-- A stage is only considered "done" once a successful send is recorded.
CREATE UNIQUE INDEX IF NOT EXISTS ux_reminder_success
    ON reminder_log (loan_id, stage) WHERE success = 1;
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_loan(
    conn: sqlite3.Connection,
    loan_id: str,
    borrower_name: str,
    email: str,
    phone: str,
    amount_due: float,
    due_date: date,
) -> None:
    """Insert a loan, or update its details while keeping its paid/pending status."""
    conn.execute(
        """
        INSERT INTO loans (loan_id, borrower_name, email, phone, amount_due, due_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(loan_id) DO UPDATE SET
            borrower_name = excluded.borrower_name,
            email         = excluded.email,
            phone         = excluded.phone,
            amount_due    = excluded.amount_due,
            due_date      = excluded.due_date
        """,
        (loan_id, borrower_name, email, phone, amount_due, due_date.isoformat()),
    )


def pending_loans(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM loans WHERE status = 'pending' ORDER BY due_date, loan_id"
    ).fetchall()


def all_loans(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM loans ORDER BY due_date, loan_id").fetchall()


def mark_paid(conn: sqlite3.Connection, loan_id: str) -> bool:
    cur = conn.execute("UPDATE loans SET status = 'paid' WHERE loan_id = ?", (loan_id,))
    conn.commit()
    return cur.rowcount > 0


def already_sent(conn: sqlite3.Connection, loan_id: str, stage: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM reminder_log WHERE loan_id = ? AND stage = ? AND success = 1",
        (loan_id, stage),
    ).fetchone()
    return row is not None


def log_reminder(
    conn: sqlite3.Connection,
    loan_id: str,
    stage: str,
    channel: str,
    success: bool,
    error: Optional[str] = None,
) -> None:
    conn.execute(
        "INSERT INTO reminder_log (loan_id, stage, channel, sent_at, success, error) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (loan_id, stage, channel, datetime.now().isoformat(timespec="seconds"), int(success), error),
    )
    conn.commit()


def recent_log(conn: sqlite3.Connection, limit: int = 20) -> Iterable[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reminder_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
