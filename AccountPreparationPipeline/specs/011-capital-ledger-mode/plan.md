# Implementation Plan: Capital Ledger Mode

**Branch**: `011-capital-ledger-mode` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/011-capital-ledger-mode/spec.md`

## Summary

Introduce a new pipeline mode `create_capital_ledger` that reads a `create_ledger` output XLSX,
filters to `deposit`, `income`, `buy`, and `sell` rows, and emits a single date-level summary
XLSX with three running-total columns: `capital` (cumulative deposits), `income` (cumulative
income), and `book_value` (cumulative net buy+sell). Rows are produced in Transaction ID order
(per spec 007 canonical sort: `date ASC, account ASC, sub_account ASC, reference ASC`) and
forward-filled so every date has a fully-populated row. `run_pipeline.ps1` is extended to invoke
this mode as step 3 for HL SIPP and HL ISA capital accounts only.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)
**Primary Dependencies**: `pandas`, `openpyxl` (already in `requirements.txt`)
**Storage**: XLSX files — input ledger (from `create_ledger`), output capital summary XLSX
**Testing**: `pytest` (unit), `pytest-bdd` (BDD Gherkin); existing test fixtures in
  `tests/data/create_ledger/`
**Target Platform**: Windows/cross-platform CLI (runs under `.venv\Scripts\python.exe`)
**Project Type**: CLI pipeline mode (identical pattern to `create_ledger`)
**Performance Goals**: No specific latency requirement; capital accounts have < 10 000 ledger rows
**Constraints**: No new runtime dependencies; reuse `LEDGER_COLUMNS` and `TRANSACTION_ID_SORT_COLS`
  from `src/modes/create_ledger/constants.py`
**Scale/Scope**: Two capital accounts (HL SIPP, HL ISA); each ledger has hundreds to low-thousands
  of rows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [X] Virtual environment (`.venv`) is initialised; dependencies declared in `requirements.txt`
  / `requirements-dev.txt`; tool config in `pyproject.toml` — **already in place; no new deps**
- [X] No magic numbers or strings — all column names, action strings, and output paths extracted
  to `src/modes/create_capital_ledger/constants.py`
- [X] SOLID principles — `CreateCapitalLedgerMode` owns only CLI wiring; `CapitalLedgerEngine`
  owns the computation; no fat interfaces introduced
- [X] All code fully type-annotated; `mypy --strict` planned as quality gate
- [X] `ruff check` + `ruff format --check` planned as quality gate
- [X] BDD Gherkin scenarios planned in `tests/features/create_capital_ledger.feature`; pytest
  unit tests in `tests/unit/create_capital_ledger/`
- [X] Structured logging with timestamps and correlation IDs included in implementation scope

## Project Structure

### Documentation (this feature)

```text
specs/011-capital-ledger-mode/
├── plan.md          ← this file
├── research.md      ← Phase 0 output
├── data-model.md    ← Phase 1 output
└── tasks.md         ← /speckit-tasks output
```

### Source Code

```text
src/
├── modes/
│   ├── create_capital_ledger/        ← NEW
│   │   ├── __init__.py
│   │   ├── constants.py              ← column names, action strings, log keys
│   │   ├── engine.py                 ← CapitalLedgerEngine.run()
│   │   └── mode.py                   ← CreateCapitalLedgerMode (CLI wiring)
│   ├── create_ledger/                ← READ-ONLY (reuse constants/schema)
│   └── consolidate_journals/         ← READ-ONLY

tests/
├── features/
│   └── create_capital_ledger.feature ← NEW BDD scenarios
│   └── steps/
│       └── create_capital_ledger_steps.py  ← NEW step definitions
├── unit/
│   └── create_capital_ledger/        ← NEW
│       └── test_engine.py
└── data/
    └── create_capital_ledger/        ← NEW fixtures
        ├── simple_ledger.xlsx        ← basic 3-date fixture
        └── mixed_actions_ledger.xlsx ← deposit + income + buy + sell + trading rows

pipeline.py    ← register CreateCapitalLedgerMode in _build_registry()
run_pipeline.ps1 ← add step 3 for HL SIPP and HL ISA
```

**Structure Decision**: Single-project layout matching the existing `create_ledger` module
exactly — one `mode.py` for CLI wiring, one `engine.py` for computation, one `constants.py`
for all named constants.

## Complexity Tracking

No constitution violations. No new patterns beyond what `create_ledger` already establishes.
