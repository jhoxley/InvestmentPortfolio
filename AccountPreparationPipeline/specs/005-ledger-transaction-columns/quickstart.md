# Quickstart: Ledger Transaction Columns

**Feature**: 005-ledger-transaction-columns
**Date**: 2026-06-08

## Prerequisites

- Python 3.11+, virtual environment activated
- `consolidate_journals` run to produce an input journal XLSX

## Running

```powershell
.venv\Scripts\python.exe pipeline.py create_ledger `
    data/journal.xlsx `
    data/ledger.xlsx
```

## Verifying the new columns

Open `data/ledger.xlsx`. You should see nine columns. For any row `i` within a position, verify:

```
Account Value[i] - Account Value[i-1] == Transaction Value[i]
```

(For the first row of each position, `Account Value[i-1]` = 0.)

## Running Tests

```powershell
# Unit tests for the updated engine
python -m pytest tests/unit/create_ledger/test_engine.py -v

# BDD scenarios
python -m pytest tests/features/steps/create_ledger_steps.py -v

# Integration tests (includes invariant check)
python -m pytest tests/integration/test_create_ledger_e2e.py -v
```

## Quality Gates

```powershell
mypy --strict src/ pipeline.py
ruff check .
ruff format --check .
```
