"""Command-line interface.

Usage:  python -m reminder_bot.cli <command> [options]
"""

import argparse
import sys
from datetime import date

from . import db
from .config import Config
from .importer import import_csv, parse_date
from .notifier import ConsoleNotifier, EmailNotifier
from .service import determine_stage, run_reminders


def cmd_init(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    print(f"Database ready at {cfg.db_path}")


def cmd_import(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    try:
        result = import_csv(conn, args.csv_file)
    except (OSError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print(f"Imported {result.imported} loan(s).")
    for err in result.errors:
        print(f"  skipped - {err}")
    return 0


def cmd_run(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    today = parse_date(args.today) if args.today else date.today()

    if args.send:
        if not cfg.email_configured:
            print("Cannot --send: set SMTP_HOST and FROM_EMAIL (see .env.example).", file=sys.stderr)
            return 1
        notifier = EmailNotifier(cfg.smtp_host, cfg.smtp_port, cfg.smtp_user,
                                 cfg.smtp_password, cfg.from_email, cfg.smtp_use_tls)
    else:
        notifier = ConsoleNotifier()
        print("Dry run: no emails will be sent. Use --send to deliver reminders.\n")

    summary = run_reminders(conn, notifier, today, cfg.company_name, cfg.currency_symbol,
                            record=args.send)
    print(f"\nSummary for {today}: sent={summary.sent}, already_sent={summary.skipped_already_sent}, "
          f"not_due_yet={summary.skipped_not_due}, no_contact={summary.skipped_no_contact}, "
          f"failed={summary.failed}")
    for line in summary.details:
        print(f"  {line}")
    return 1 if summary.failed else 0


def cmd_list(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    today = parse_date(args.today) if args.today else date.today()
    rows = db.all_loans(conn)
    if not rows:
        print("No loans. Import some with: import <file.csv>")
        return 0
    print(f"{'LOAN':<10}{'BORROWER':<22}{'AMOUNT':>12}  {'DUE':<12}{'STATUS':<9}NEXT STAGE")
    for r in rows:
        stage = determine_stage(date.fromisoformat(r["due_date"]), today) if r["status"] == "pending" else "-"
        print(f"{r['loan_id']:<10}{r['borrower_name']:<22}{r['amount_due']:>12,.2f}  "
              f"{r['due_date']:<12}{r['status']:<9}{stage or 'not yet due'}")
    return 0


def cmd_paid(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    if db.mark_paid(conn, args.loan_id):
        print(f"Loan {args.loan_id} marked as paid. No further reminders will be sent.")
        return 0
    print(f"Loan {args.loan_id} not found.", file=sys.stderr)
    return 1


def cmd_log(args, cfg):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    for r in db.recent_log(conn, args.limit):
        status = "ok" if r["success"] else f"FAILED ({r['error']})"
        print(f"{r['sent_at']}  {r['loan_id']:<10}{r['stage']:<11}{r['channel']:<8}{status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reminder_bot", description="Loan repayment reminder bot")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database").set_defaults(func=cmd_init)

    sp = sub.add_parser("import", help="import loans from a CSV file")
    sp.add_argument("csv_file")
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("run", help="process pending loans and send due reminders")
    sp.add_argument("--send", action="store_true", help="actually send emails (default is dry run)")
    sp.add_argument("--today", help="pretend today is YYYY-MM-DD (for testing)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("list", help="show all loans and their next reminder stage")
    sp.add_argument("--today", help="pretend today is YYYY-MM-DD")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("paid", help="mark a loan as paid (stops reminders)")
    sp.add_argument("loan_id")
    sp.set_defaults(func=cmd_paid)

    sp = sub.add_parser("log", help="show recent reminder history")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_log)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.from_env()
    try:
        return args.func(args, cfg) or 0
    except ValueError as exc:  # e.g. a malformed --today
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
