# Repayment Reminder Bot

A small, dependency-free Python tool that sends staged loan-repayment reminders by email. Load your borrowers from a CSV, run the bot once a day, and each borrower gets the right message at the right time, exactly once.

Built as a project idea for a lending / credit company (e.g. Credex), but it works for any business that collects scheduled payments.

## Features

- **CSV import** with row-level validation (bad rows are reported and skipped, never fatal)
- **Four reminder stages**: upcoming, due today, overdue, final notice
- **No duplicates**: every stage is sent at most once per loan, tracked in a reminder log
- **Catch-up safe**: if the bot misses a day, the next run still sends the correct stage
- **Dry run by default**: `run` only prints messages until you pass `--send`
- **Retry on failure**: failed sends are logged and retried on the next run
- **Mark as paid** to stop reminders immediately
- **Pluggable channels**: add SMS/WhatsApp by writing one small class
- Python standard library only (Python 3.8+), SQLite storage, unit tests included

## Project structure

```
repayment-reminder-bot/
├── reminder_bot/
│   ├── cli.py          # command-line interface
│   ├── config.py       # settings from environment / .env
│   ├── db.py           # SQLite schema and queries
│   ├── importer.py     # CSV import + validation
│   ├── notifier.py     # Notifier base class, console (dry-run) and SMTP email
│   ├── service.py      # stage logic and the main run loop
│   └── templates.py    # message text for each stage
├── sample_data/borrowers.csv
├── tests/test_bot.py
├── .env.example
└── requirements.txt
```

## Quick start

```bash
# 1. Import the sample borrowers
python -m reminder_bot.cli import sample_data/borrowers.csv

# 2. See who needs which reminder (pretend today is 2026-10-22)
python -m reminder_bot.cli list --today 2026-10-22

# 3. Dry run: prints the messages, sends nothing, records nothing
python -m reminder_bot.cli run --today 2026-10-22
```

Omit `--today` to use the real current date.

## Commands

| Command | What it does |
|---|---|
| `import <file.csv>` | Add or update loans from a CSV file (creates the database if needed) |
| `list [--today DATE]` | Show all loans, their status, and the next reminder stage |
| `run [--send] [--today DATE]` | Process pending loans. Dry run unless `--send` is given |
| `paid <loan_id>` | Mark a loan as paid so no more reminders go out |
| `log [--limit N]` | Show recent reminder history, including failures |
| `init` | Create an empty database |

## CSV format

```csv
loan_id,borrower_name,email,phone,amount_due,due_date
L1001,Aarav Sharma,aarav.sharma@example.com,+919800000001,12500.00,2026-10-25
```

- All six columns must be present in the header.
- `due_date` must be `YYYY-MM-DD`; `amount_due` must be a positive number.
- Each row needs a `loan_id`, a `borrower_name`, and an email or phone.
- Re-importing a file **updates** existing loans (matched on `loan_id`) and keeps their paid/pending status, so you can safely re-import an updated export every day.

## Reminder stages

Based on days until the due date, evaluated each time the bot runs:

| Stage | When | Tone |
|---|---|---|
| `upcoming` | 1 to 3 days before due | Friendly reminder |
| `due_today` | On the due date | Pay today |
| `overdue_1` | 1 to 6 days late | Overdue notice |
| `overdue_7` | 7 or more days late | Final notice |

Loans more than 3 days from their due date are skipped. Each stage is sent once; after `overdue_7` the bot stops, and further follow-up (calls, collections) is up to your team.

To change the timing or wording, edit `determine_stage()` in `reminder_bot/service.py` and the texts in `reminder_bot/templates.py`.

## Sending real emails

1. Copy the config template and fill it in:

   ```bash
   cp .env.example .env
   ```

   Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `FROM_EMAIL`. For Gmail, use `smtp.gmail.com`, port `587`, and an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.

2. Do a dry run first, then send:

   ```bash
   python -m reminder_bot.cli run          # preview
   python -m reminder_bot.cli run --send   # deliver
   ```

Never commit `.env`; it is already in `.gitignore`.

Borrowers with no email address are skipped and reported in the run summary (the phone column is stored for when you add an SMS channel).

## Running it automatically every day

**Linux / macOS (cron)**, every day at 9:00 AM:

```cron
0 9 * * * cd /path/to/repayment-reminder-bot && /usr/bin/python3 -m reminder_bot.cli run --send >> bot.log 2>&1
```

**Windows (Task Scheduler)**: create a daily task that runs

```
python -m reminder_bot.cli run --send
```

with "Start in" set to the project folder.

The exit code is `1` if any send failed, which makes it easy to alert on from a scheduler or CI job. Safe to run more than once a day: already-sent stages are skipped.

## Adding another channel (SMS, WhatsApp, ...)

Subclass `Notifier` in `reminder_bot/notifier.py`:

```python
class SmsNotifier(Notifier):
    channel = "sms"

    def can_notify(self, loan) -> bool:
        return bool(loan["phone"])

    def send(self, loan, subject, body):
        try:
            my_sms_provider.send(to=loan["phone"], text=f"{subject}\n{body}")
        except Exception as exc:
            raise NotificationError(str(exc)) from exc
```

Then pick it in `cmd_run` in `cli.py`. Note that a stage is currently marked "sent" per loan regardless of channel, so run one channel per deployment, or extend the log's unique index to include `channel` if you want both.

## Running the tests

```bash
python -m unittest -v
```

The tests cover stage boundaries, one-send-per-stage, escalation, paid loans, missing contacts, failure retry, dry-run behavior, CSV validation, and re-import.

## Design notes

- **Why ranges instead of exact days?** If a cron job fails for a day, an exact-day rule would silently skip a reminder forever. Ranges plus the sent-log make the bot self-healing.
- **Why does a dry run record nothing?** So previewing never uses up a reminder; the real run afterwards still sends everything.
- **Why SQLite?** Zero setup, single file, and plenty for tens of thousands of loans. Swap `db.py` for Postgres if you outgrow it.

## Ideas for extending it

- SMS / WhatsApp channel (Twilio, Meta Cloud API)
- Per-borrower language or template overrides
- Payment-link in the message, and auto-marking loans paid from a payment webhook
- Small Flask/FastAPI dashboard showing reminder history
- Respecting quiet hours and local holidays

## Disclaimer

This is a learning/demo project. Before using it with real borrowers, check the collection-communication rules that apply to you (message timing, wording, consent, and data-protection law in your country) and review the message templates with your compliance team.
