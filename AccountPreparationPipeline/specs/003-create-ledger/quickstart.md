# Quickstart: Ledger Running Balance

**Feature**: 003-create-ledger
**Date**: 2026-06-03

## Prerequisites

- Python 3.11+ installed
- Virtual environment activated: `.venv\Scripts\activate` (Windows) or
  `source .venv/bin/activate` (Unix)
- Dependencies installed: `pip install -r requirements.txt`
- A consolidated journal XLSX produced by `consolidate_journals` (see feature 002)

## Running the Mode

### Generate a ledger from a journal

```bash
python pipeline.py create_ledger data/my_journal.xlsx data/my_ledger.xlsx
```

The output file is created (or overwritten) at the given path. The input file is never modified.

### Getting help

```bash
python pipeline.py create_ledger --help
```

## Expected Output

```
Ledger written: 492 rows processed → data/my_ledger.xlsx
```

The output XLSX contains one row per input row, sorted by account, sub_account, then date. The
`value` and `quantity` columns hold the running cumulative balance for each (account, sub_account)
position at each point in time.

## Running Tests

```bash
# All tests
python -m pytest tests/

# Specific to this feature
python -m pytest tests/unit/create_ledger/ tests/features/create_ledger.feature -v

# With coverage
python -m pytest tests/unit/create_ledger/ --cov=src/modes/create_ledger --cov-report=term-missing
```

## Quality Gates

```bash
mypy --strict src/
ruff check .
ruff format --check .
```

## Understanding the Ledger Output

### Investment positions (buy/sell actions)

For each investment position (non-Cash sub_account):

- **value column**: The running cumulative *cost* of the position. Buy and sell values are
  negated before summing — a buy of £1,000 contributes -£1,000 (cash outflow), a sale of
  £500 contributes -£500. A positive running value means you have spent more than you received
  (net cost); a negative value means proceeds exceed cost (net gain).

- **quantity column**: The running net unit holding. Buy quantities are positive; sell quantities
  are negated before summing. A running quantity of 50 means 50 units are currently held.

### Cash position

For Cash rows (sub_account == "Cash"):

- The input quantity is always blank; it is set equal to the input value before cumulation.
- Both **value** and **quantity** track the same running cash balance — the cumulative sum of
  all deposits, income receipts, and fee charges for that account.
