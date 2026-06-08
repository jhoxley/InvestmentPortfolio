# Quickstart: Trade Cash Offset Entries

**Feature**: 004-trade-cash-offsets
**Date**: 2026-06-05

## Prerequisites

- Python 3.11+ installed
- Virtual environment activated: `.venv\Scripts\activate` (Windows)
- Dependencies installed: `pip install -r requirements.txt`
- A directory of HL CSV exports containing buy and/or sell events

## Running the Mode

This feature adds no new commands. Use `consolidate_journals` as normal:

```powershell
.venv\Scripts\python.exe pipeline.py consolidate_journals `
    data/journal.xlsx `
    data/hl_exports/ `
    HL `
    "ISA 2024"
```

## Verifying Offset Rows

After running, open `data/journal.xlsx` and filter the `action` column for `"trading"`.
Each offset row should have:

- `sub_account = "Cash"`
- `action = "trading"`
- `reference` ending in `"-offset"` (e.g. `"B12345-offset"`)
- `value` equal to the negated value of the corresponding trade
- `quantity` equal to the same negated value

The number of `"trading"` rows must equal the total number of `"buy"` + `"sell"` rows in
the journal.

## Ledger Integration

After consolidation, run `create_ledger` to compute running balances:

```powershell
.venv\Scripts\python.exe pipeline.py create_ledger `
    data/journal.xlsx `
    data/ledger.xlsx
```

In the ledger output, filter by `sub_account = "Cash"` to see the running cash balance.
The balance will now reflect investment purchases and sales (via the `"trading"` offset rows)
in addition to explicit deposits and withdrawals.

## Running Tests

```powershell
# All tests
python -m pytest tests/

# Offset generator unit tests only
python -m pytest tests/unit/consolidate_journals/test_offset_generator.py -v

# BDD scenarios (includes new offset scenarios)
python -m pytest tests/features/steps/consolidate_journals_steps.py -v

# Integration tests
python -m pytest tests/integration/test_consolidate_journals_e2e.py -v
```

## Quality Gates

```powershell
mypy --strict src/ pipeline.py
ruff check .
ruff format --check .
```
