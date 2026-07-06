# Quickstart: Ledger Transaction ID

**Feature**: `007-ledger-transaction-id`
**Date**: 2026-06-10

## Setup

```powershell
cd C:\GitHub\JHoxley\InvestmentPortfolio\AccountPreparationPipeline
.venv\Scripts\Activate.ps1
```

---

## Scenario 1: First-Time Run — IDs Assigned from 00001-001

Given a journal with three rows:

| date | account | sub_account | action | reference | value | quantity |
|------|---------|-------------|--------|-----------|-------|----------|
| 2024-01-01 | ISA | Vanguard Fund | buy | B001 | -1000 | 10 |
| 2024-01-02 | ISA | Cash | trading | B001-offset | -1000 | — |
| 2024-01-03 | ISA | Vanguard Fund | sell | S001 | 400 | 4 |

Run:
```powershell
python pipeline.py create_ledger journal.xlsx ledger.xlsx
```

Expected `Transaction ID` column in `ledger.xlsx`:

| Transaction ID | sub_account | reference |
|----------------|-------------|-----------|
| 00001-001 | Vanguard Fund | B001 |
| 00002-001 | Cash | B001-offset |
| 00003-001 | Vanguard Fund | S001 |

*(Canonical sort: date ASC → account ASC → sub_account ASC → reference ASC)*

---

## Scenario 2: Invariant Holds for Same-Date Cash Offsets

Given a journal where two buys settle on the same date, each with a Cash offset:

| date | sub_account | reference | value |
|------|-------------|-----------|-------|
| 2024-03-15 | Vanguard Fund | B001 | -1000 |
| 2024-03-15 | Vanguard Fund | B002 | -500 |
| 2024-03-15 | Cash | B001-offset | -1000 |
| 2024-03-15 | Cash | B002-offset | -500 |

After `create_ledger`, sorted by Transaction ID ascending:

| Transaction ID | sub_account | reference | Transaction Value | Account Value |
|----------------|-------------|-----------|-------------------|---------------|
| 00001-001 | Cash | B001-offset | -1000 | -1000 |
| 00002-001 | Cash | B002-offset | -500 | -1500 |
| 00003-001 | Vanguard Fund | B001 | -1000 | -1000 |
| 00004-001 | Vanguard Fund | B002 | -500 | -1500 |

Invariant check (Cash group): `Account Value[row2] = -1000 + (-500) = -1500` ✓

*(Without Transaction ID, the Cash offset order was ambiguous — any interleaving could produce
a different Account Value mid-sequence.)*

---

## Scenario 3: Re-Run Preserves Existing IDs, Assigns Insertion IDs

**Step 1** — Initial run produces:

| Transaction ID | date | sub_account | reference |
|----------------|------|-------------|-----------|
| 00001-001 | 2024-01-01 | Cash | Deposit |
| 00002-001 | 2024-01-02 | Cash | B001-offset |
| 00003-001 | 2024-01-03 | Vanguard Fund | B001 |

**Step 2** — A new journal event is added that sorts between `00001-001` and `00002-001`:

```
date=2024-01-01, sub_account=Cash, reference=Fee
```

Re-run `create_ledger` against the same `ledger.xlsx`:

```powershell
python pipeline.py create_ledger journal.xlsx ledger.xlsx
```

Expected result:

| Transaction ID | date | sub_account | reference |
|----------------|------|-------------|-----------|
| 00001-001 | 2024-01-01 | Cash | Deposit |
| 00001-002 | 2024-01-01 | Cash | Fee |          ← new insertion
| 00002-001 | 2024-01-02 | Cash | B001-offset |
| 00003-001 | 2024-01-03 | Vanguard Fund | B001 |

All original IDs are unchanged. The new row receives prefix `00001` (predecessor's prefix) and
suffix `002` (first insertion after `00001-001`).

---

## Scenario 4: Idempotent Re-Run

Re-running `create_ledger` against an unchanged journal with the same `ledger.xlsx`:

```powershell
python pipeline.py create_ledger journal.xlsx ledger.xlsx
python pipeline.py create_ledger journal.xlsx ledger.xlsx  # second time
```

Both runs produce identical `Transaction ID` values — no mutation.

---

## Running Tests

```powershell
# All create_ledger tests
python -m pytest tests/unit/create_ledger/ tests/integration/ tests/features/ -v -k "ledger"

# Transaction ID unit tests only
python -m pytest tests/unit/create_ledger/test_transaction_id.py -v

# BDD scenarios
python -m pytest tests/features/create_ledger.feature -v

# Full suite
python -m pytest tests/ -v
```

---

## Quality Gates

```powershell
mypy --strict src/ pipeline.py
ruff check .
ruff format --check .
```

All three must exit 0 before considering the feature complete.
