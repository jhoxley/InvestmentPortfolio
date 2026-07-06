# Implementation Plan: Ledger Running Balance

**Branch**: `003-create-ledger` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-create-ledger/spec.md`

## Summary

Add a `create_ledger` mode to the pipeline that reads a consolidated journal XLSX (produced by
`consolidate_journals`) and writes a ledger XLSX containing the same rows sorted by
(account, sub_account, date), with `value` and `quantity` columns replaced by their cumulative
running totals per position. Buy and sell values are negated before cumulation; sell quantities
are negated; Cash rows with blank quantity have value copied to quantity before cumulation. The
mode slots into the existing `ModeInterface` / `ModeRegistry` framework with zero changes to the
dispatcher.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `python-json-logger>=2.0`, `pandas>=2.0,<3.0`, `openpyxl>=3.1,<4.0`
(all existing runtime deps — no new packages required)
**Storage**: XLSX files on local filesystem (read + write via `pandas` + `openpyxl`)
**Testing**: `pytest` (unit), `pytest-bdd` (Gherkin BDD), `pytest` integration (subprocess)
**Target Platform**: Command-line; Windows / macOS / Linux
**Project Type**: CLI mode within existing pipeline framework
**Performance Goals**: 500 rows across 20 positions in under 10 seconds (SC-004)
**Constraints**: Row count preserved (FR-002); idempotent (SC-003); output parent dir must exist
**Scale/Scope**: Single-developer tool; no new runtime dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Virtual environment (`.venv`) already initialised; no new runtime dependencies — all
  required packages (`pandas`, `openpyxl`) already declared in `requirements.txt`
- [x] No magic numbers or strings — action type checks, Cash sub_account identifier, number
  formats, and log field names extracted to `src/modes/create_ledger/constants.py`
- [x] SOLID principles applied — `LedgerEngine` (SRP: computation only), `CreateLedgerMode`
  (SRP: CLI only), no shared mutable state; engine is independently testable
- [x] All code fully type-annotated; `mypy --strict src/` planned as quality gate
- [x] `ruff check .` + `ruff format --check .` planned as quality gates
- [x] BDD Gherkin scenarios in `tests/features/create_ledger.feature`; pytest unit tests in
  `tests/unit/create_ledger/`; integration tests in `tests/integration/`
- [x] Structured logging: mode entry, computation milestone (rows processed), mode exit

**Post-design re-check**: All gates confirmed after Phase 1 design. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-create-ledger/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Setup + run instructions
├── contracts/
│   └── cli-contract.md  # CLI argument and output contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code

```text
src/modes/create_ledger/
├── __init__.py
├── mode.py         # CreateLedgerMode — ModeInterface implementation
├── constants.py    # CASH_SUB_ACCOUNT, BUY_SELL_ACTIONS, SELL_ACTION, log field names
└── engine.py       # LedgerEngine — sign adjustment + groupby cumsum computation

tests/
├── features/
│   ├── create_ledger.feature               # BDD Gherkin acceptance scenarios
│   └── steps/
│       └── create_ledger_steps.py
├── unit/
│   └── create_ledger/
│       ├── __init__.py
│       ├── test_engine.py   # Sign adjustment, cumsum, Cash rule, ordering, row count
│       └── test_mode.py     # Argument parsing, input validation, exit codes, log output
└── integration/
    └── test_create_ledger_e2e.py  # Subprocess end-to-end against programmatic fixtures
```

**No new binary test data files**: test inputs are generated programmatically in pytest fixtures
using `pandas.DataFrame.to_excel` into `tmp_path` (see Decision 4 in research.md).

**Structure Decision**: Two-file module (`mode.py` + `engine.py`); the engine holds all
computation logic and is independently unit-testable without importing the mode or pipeline
framework.

## Complexity Tracking

> No constitution violations. Table omitted.

---

## Implementation Notes

### Module Responsibilities

**`constants.py`**
- `CASH_SUB_ACCOUNT: str = "Cash"` — canonical identifier for cash positions
- `BUY_SELL_ACTIONS: frozenset[str] = frozenset({"buy", "sell"})` — actions whose value is negated
- `SELL_ACTION: str = "sell"` — action whose quantity is negated
- `LOG_CL_CORRELATION_ID: str = "correlation_id"` — structured log field name
- `COMPLETION_MSG: str = "Ledger written"` — stdout completion label

**`engine.py` — LedgerEngine**

Single public method: `run(input_df: pd.DataFrame) -> pd.DataFrame`

Internal adjustment and cumulation sequence (see Decision 3 in research.md):

```
1. Validate columns — raise ValueError if any of JOURNAL_COLUMNS are missing

2. Cash rule:
     where sub_account == CASH_SUB_ACCOUNT and quantity is NaN:
       quantity ← value

3. Adjusted value:
     adj_value ← -value   if action in BUY_SELL_ACTIONS
     adj_value ←  value   otherwise

4. Adjusted quantity:
     adj_quantity ← -quantity   if action == SELL_ACTION
     adj_quantity ←  quantity   otherwise

5. Stable sort by (account, sub_account, date)

6. Cumulative sums per (account, sub_account) group:
     value    ← cumsum(adj_value)
     quantity ← cumsum(adj_quantity)

7. Drop adj_value, adj_quantity

8. Return with JOURNAL_COLUMNS column order preserved
```

**`mode.py` — CreateLedgerMode**
- `name = "create_ledger"`, `description = "Compute running position balances from a consolidated journal"`
- `register_arguments`: adds 2 positional args (`input_path`, `output_path`) with `help=` strings
- `execute`:
  1. Validate `input_path` exists → exit code 2 if not
  2. Read XLSX: `pd.read_excel(input_path, engine="openpyxl")`
  3. Call `LedgerEngine().run(df)` — may raise `ValueError` for schema errors → exit code 2
  4. Write output via `pd.ExcelWriter` + openpyxl; apply `NUMBER_FORMAT_VALUE` to `value` column
     and `NUMBER_FORMAT_QUANTITY` to `quantity` column (imported from
     `consolidate_journals/constants.py` — see Decision 6 in research.md)
  5. Print `"Ledger written: {N} rows processed → {output_path}"` to stdout
  6. Emit structured INFO log record

### XLSX Write Pattern

Reuses the `pd.ExcelWriter` + openpyxl cell format pattern established in
`consolidate_journals/journal_store.py`. No atomic temp-file rename is required here because the
output is always a new file (not an in-place update of a shared store).

### Registration in pipeline.py

Add to `_build_registry()`:

```python
from src.modes.create_ledger.mode import CreateLedgerMode
registry.register(CreateLedgerMode())
```
