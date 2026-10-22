import os
import tempfile
import unittest
from datetime import date

from reminder_bot import db, templates
from reminder_bot.importer import import_csv
from reminder_bot.notifier import NotificationError, Notifier
from reminder_bot.service import determine_stage, run_reminders

TODAY = date(2026, 10, 22)


class FakeNotifier(Notifier):
    channel = "fake"

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def can_notify(self, loan):
        return bool(loan["email"])

    def send(self, loan, subject, body):
        if self.fail:
            raise NotificationError("boom")
        self.sent.append((loan["loan_id"], subject))


def make_conn():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def add(conn, loan_id, due, email="a@example.com"):
    db.upsert_loan(conn, loan_id, "Test User", email, "", 1000.0, due)
    conn.commit()


class StageTests(unittest.TestCase):
    def test_stage_boundaries(self):
        d = lambda n: date.fromordinal(TODAY.toordinal() + n)
        self.assertIsNone(determine_stage(d(4), TODAY))
        self.assertEqual(determine_stage(d(3), TODAY), templates.UPCOMING)
        self.assertEqual(determine_stage(d(1), TODAY), templates.UPCOMING)
        self.assertEqual(determine_stage(d(0), TODAY), templates.DUE_TODAY)
        self.assertEqual(determine_stage(d(-1), TODAY), templates.OVERDUE_1)
        self.assertEqual(determine_stage(d(-6), TODAY), templates.OVERDUE_1)
        self.assertEqual(determine_stage(d(-7), TODAY), templates.OVERDUE_7)
        self.assertEqual(determine_stage(d(-60), TODAY), templates.OVERDUE_7)


class RunTests(unittest.TestCase):
    def run_bot(self, conn, notifier, today=TODAY, record=True):
        return run_reminders(conn, notifier, today, "Credex", "Rs.", record=record)

    def test_sends_once_per_stage(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 22))
        n = FakeNotifier()
        self.assertEqual(self.run_bot(conn, n).sent, 1)
        second = self.run_bot(conn, n)
        self.assertEqual(second.sent, 0)
        self.assertEqual(second.skipped_already_sent, 1)
        self.assertEqual(len(n.sent), 1)

    def test_escalates_to_next_stage(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 22))
        n = FakeNotifier()
        self.run_bot(conn, n)                                  # due_today
        self.run_bot(conn, n, today=date(2026, 10, 23))        # overdue_1
        self.assertEqual(len(n.sent), 2)

    def test_paid_loans_are_ignored(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 22))
        db.mark_paid(conn, "L1")
        n = FakeNotifier()
        self.assertEqual(self.run_bot(conn, n).sent, 0)
        self.assertEqual(n.sent, [])

    def test_not_due_yet_is_skipped(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 12, 1))
        s = self.run_bot(conn, FakeNotifier())
        self.assertEqual(s.sent, 0)
        self.assertEqual(s.skipped_not_due, 1)

    def test_missing_contact_is_skipped(self):
        conn = make_conn()
        db.upsert_loan(conn, "L1", "No Email", "", "+910000000000", 500.0, date(2026, 10, 22))
        conn.commit()
        s = self.run_bot(conn, FakeNotifier())
        self.assertEqual(s.skipped_no_contact, 1)

    def test_failed_send_is_retried_next_run(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 22))
        s = self.run_bot(conn, FakeNotifier(fail=True))
        self.assertEqual(s.failed, 1)
        good = FakeNotifier()
        self.assertEqual(self.run_bot(conn, good).sent, 1)

    def test_dry_run_records_nothing(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 22))
        self.run_bot(conn, FakeNotifier(), record=False)
        self.assertFalse(db.already_sent(conn, "L1", templates.DUE_TODAY))
        self.assertEqual(self.run_bot(conn, FakeNotifier()).sent, 1)


class ImportTests(unittest.TestCase):
    def write_csv(self, text):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_import_valid_and_invalid_rows(self):
        path = self.write_csv(
            "loan_id,borrower_name,email,phone,amount_due,due_date\n"
            "L1,Ann,ann@example.com,,100,2026-10-30\n"
            "L2,Bob,bad-email,,100,2026-10-30\n"
            "L3,Cat,cat@example.com,,-5,2026-10-30\n"
            "L4,Dan,dan@example.com,,100,30/10/2026\n"
        )
        conn = make_conn()
        result = import_csv(conn, path)
        self.assertEqual(result.imported, 1)
        self.assertEqual(len(result.errors), 3)

    def test_missing_column_raises(self):
        path = self.write_csv("loan_id,borrower_name\nL1,Ann\n")
        with self.assertRaises(ValueError):
            import_csv(make_conn(), path)

    def test_reimport_keeps_paid_status(self):
        path = self.write_csv(
            "loan_id,borrower_name,email,phone,amount_due,due_date\n"
            "L1,Ann,ann@example.com,,100,2026-10-30\n"
        )
        conn = make_conn()
        import_csv(conn, path)
        db.mark_paid(conn, "L1")
        import_csv(conn, path)
        status = conn.execute("SELECT status FROM loans WHERE loan_id='L1'").fetchone()[0]
        self.assertEqual(status, "paid")


class TemplateTests(unittest.TestCase):
    def test_every_stage_renders(self):
        conn = make_conn()
        add(conn, "L1", date(2026, 10, 20))
        loan = db.pending_loans(conn)[0]
        for stage in templates.STAGES:
            subject, body = templates.render(stage, loan, "Credex", "Rs.", TODAY)
            self.assertIn("L1", body)
            self.assertTrue(subject)


if __name__ == "__main__":
    unittest.main()
