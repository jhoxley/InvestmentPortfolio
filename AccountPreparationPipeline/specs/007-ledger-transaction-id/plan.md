# Implementation Plan: Ledger Transaction ID

**Branch**: `007-ledger-transaction-id` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/007-ledger-transaction-id/spec.md`

## Summary

Add a `Transaction ID` column (`NNNNN-NNN` format) to the `create_ledger` output ledger. The
column is the first in the XLSX (column A), carries text-formatted zero-padded identifiers, and
is assigned in canonical sort order `(date, account, sub_account, reference)`. This ordering ensures the
per-position ledger invariant holds when rows are sorted by Transaction ID — including same-date
Cash offset rows that were previously ambiguous. On re-runs, existing IDs are preserved by reading
the prior output file; new rows between existing rows receive suffix-incremented IDs
(`-002`, `-003`, …); new rows appended after existing rows receive the next sequential 5-digit
prefix with suffix `-001`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pandas 2.x, openpyxl (XLSX I/O)
**Storage**: XLSX files (input journal, output ledger)
**Testing**: pytest + pytest-bdd (`tests/unit/`, `tests/features/`, `tests/integration/`)
**Target Platform**: Local Windows CLI (`pipeline.py`)
**Project Type**: CLI pipeline tool
**Performance Goals**: No throughput requirement — retail-scale data (<<10 000 rows)
**Constraints**: `mypy --strict` zero errors; `ruff check` + `ruff format --check` zero violations
**Scale/Scope**: Single XLSX ledger per run; <=99 999 rows (5-digit prefix capacity)

## Constitution Check

- [x] Virtual environment (`.venv`) is initialised; dependencies declared in `requirements.txt` /
  `requirements-dev.txt`; tool config in `pyproject.toml`
- [x] No magic numbers or strings — `LEDGER_COL_TRANSACTION_ID`, `TRANSACTION_ID_SORT_COLS`,
  `TRANSACTION_ID_FORMAT` extracted to `constants.py`
- [x] SOLID principles applied — `TransactionIDAssigner` has single responsibility (ID assignment
  only); `LedgerEngine` delegates ID assignment to it; `CreateLedgerMode` handles I/O
- [x] All code fully type-annotated; `mypy --strict` planned as a quality gate
- [x] `ruff check` + `ruff format --check` planned as a quality gate
- [x] BDD Gherkin scenarios planned in `tests/features/create_ledger.feature`; `pytest` unit
  tests planned in `tests/unit/create_ledger/`
- [x] Structured logging with timestamps and correlation IDs included in implementation scope

## Project Structure

### Documentation (this feature)

```text
specs/007-ledger-transaction-id/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
src/modes/create_ledger/
├── constants.py          # MODIFIED — add LEDGER_COL_TRANSACTION_ID, TRANSACTION_ID_SORT_COLS
├── engine.py             # MODIFIED — new sort key; call TransactionIDAssigner; accept prior_ids
├── mode.py               # MODIFIED — read prior ledger; pass prior_ids to engine
└── transaction_id.py     # NEW — TransactionIDAssigner class

tests/
├── features/
│   ├── create_ledger.feature              # MODIFIED — add US1, US2, US3 BDD scenarios
│   └── steps/create_ledger_steps.py       # MODIFIED — add step definitions
├── unit/create_ledger/
│   ├── test_engine.py                     # MODIFIED — update for new column + sort order
│   └── test_transaction_id.py             # NEW — unit tests for TransactionIDAssigner
└── integration/
    └── test_create_ledger_e2e.py          # MODIFIED — add Transaction ID integration tests
```

**Structure Decision**: Single-project layout (existing). New logic isolated to
`transaction_id.py` (SRP). Mode and engine extended minimally.

## Phase 0: Research

See [research.md](research.md) for full findings. Key decisions:

1. **Sort key change**: Replace `(account, sub_account, date)` with `(date, account, sub_account, reference)`
   in `LedgerEngine`. The `groupby` cumsum is unaffected by global row order — correctness preserved.

2. **Prior ledger I/O in mode**: `CreateLedgerMode.execute()` checks if `output_path` exists and
   reads `(date, sub_account, reference) -> Transaction ID` mapping before invoking the engine.
   Engine remains pure (no file I/O).

3. **LEDGER_COLUMNS index arithmetic**: Adding `Transaction ID` at list index 0 shifts all
   downstream `LEDGER_COLUMNS.index(col_name) + 1` values by +1, which self-consistently
   tracks Excel column positions. No code change needed in the formatting loop.

4. **Text storage**: `str` dtype in DataFrame + `number_format = '@'` for the Transaction ID
   column in mode.py.

5. **Row order change**: Output rows now interleave positions by date instead of grouping by
   position. Integration tests that rely on implicit row order need updating.

## Phase 1: Design

See [data-model.md](data-model.md) and [contracts/cli-contract.md](contracts/cli-contract.md).

### TransactionIDAssigner (new class)

**File**: `src/modes/create_ledger/transaction_id.py`

```python
class TransactionIDAssigner:
    def assign(
        self,
        df: pd.DataFrame,          # already sorted by (date, sub_account, reference)
        prior_ids: dict[tuple[str, str, str, str], str],
    ) -> pd.Series:                # Series[str] of Transaction IDs, same index as df
        ...
```

**First-time** (`prior_ids == {}`): `f"{i+1:05d}-001"` for row at 0-based index `i`.

**Re-run**: Walk sorted rows; for rows with keys in `prior_ids`, use prior ID; for new rows,
inherit predecessor's 5-digit prefix and increment max suffix for that prefix; for new rows
appended after all prior rows, assign next sequential prefix with `-001`.

### LedgerEngine changes

- Accept `prior_ids: dict[tuple[str, str, str, str], str] = {}` parameter in `run()`
- Change sort to `["date", "account", "sub_account", "reference"]`
- After cumsum computation, call `TransactionIDAssigner().assign(df, prior_ids)`
- Prepend `Transaction ID` column before returning `df[LEDGER_COLUMNS]`

### CreateLedgerMode changes

- After input validation, if `output_path.exists()`: read it and build `prior_ids` dict
- Handle unreadable prior ledger gracefully: log WARNING, use `prior_ids = {}`
- Pass `prior_ids` to `LedgerEngine().run(df, prior_ids=prior_ids)`
- In the formatting loop: add Transaction ID column formatting with `number_format = '@'`

### Constants changes

```python
LEDGER_COL_TRANSACTION_ID: str = "Transaction ID"
TRANSACTION_ID_SORT_COLS: list[str] = ["date", "account", "sub_account", "reference"]

LEDGER_COLUMNS: list[str] = [
    LEDGER_COL_TRANSACTION_ID,    # NEW — first column
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    LEDGER_COL_ACCOUNT_VALUE,
    LEDGER_COL_ACCOUNT_QUANTITY,
    LEDGER_COL_TRANSACTION_VALUE,
    LEDGER_COL_TRANSACTION_QUANTITY,
]
```

## Complexity Tracking

No constitution violations requiring justification.
