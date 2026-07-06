# Account Preparation Pipeline

A command-line pipeline for preparing and consolidating investment account data. The pipeline
is structured as a set of independently invokable **modes**, each performing a distinct data
preparation task. All execution produces structured JSON logs and a metrics record.

## Table of Contents

- [How it works](#how-it-works)
- [Installation and setup](#installation-and-setup)
- [Running the pipeline](#running-the-pipeline)
- [Available modes](#available-modes)
  - [consolidate\_journals](#consolidate_journals)
  - [example](#example)
- [Exit codes](#exit-codes)
- [Logging](#logging)
- [Development](#development)

---

## How it works

`pipeline.py` is the single entrypoint. It accepts a **mode name** as its first argument and
dispatches to the corresponding mode implementation. Every mode:

1. Declares its accepted arguments via argparse
2. Receives an `ExecutionContext` carrying a UUID correlation ID and start timestamp
3. Executes its logic and returns an integer exit code
4. Has its execution time and outcome captured in a structured metrics log record

Modes are registered at startup in `pipeline.py`; adding a new mode requires only writing a
conformant class and registering it — no changes to the dispatcher or argument parser.

```
pipeline.py
    │
    ├── parses global flags (--log-level)
    ├── resolves mode name → ModeRegistry
    └── dispatches to mode.execute(context, args)
                │
                ├── structured JSON logs → stderr
                └── mode-specific output → stdout
```

---

## Installation and setup

### Prerequisites

- Python 3.11 or later
- `pip` (bundled with Python)

### 1. Clone the repository

```bash
git clone <repo-url>
cd AccountPreparationPipeline
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (cmd)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### 3. Install runtime dependencies

```bash
pip install -r requirements.txt
```

Runtime dependencies:

| Package | Version | Purpose |
|---|---|---|
| `python-json-logger` | >=2.0,<3.0 | Structured JSON log output |
| `pandas` | >=2.0,<3.0 | DataFrame-based journal merging |
| `openpyxl` | >=3.1,<4.0 | XLSX read/write |

### 4. (Optional) Install development dependencies

Required only if you intend to run tests or the quality gates:

```bash
pip install -r requirements-dev.txt
```

Additional dev dependencies: `pytest`, `pytest-bdd`, `pytest-cov`, `mypy`, `ruff`, `pandas-stubs`.

There is no build step. The pipeline runs directly from source.

---

## Running the pipeline

```
python pipeline.py [--log-level LEVEL] <mode> [mode arguments]
```

### Global options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--log-level` | `DEBUG` `INFO` `WARNING` `ERROR` | `INFO` | Minimum severity for structured log output on stderr |

### Getting help

```bash
# List all available modes
python pipeline.py --help

# Help for a specific mode
python pipeline.py consolidate_journals --help
```

---

## Available modes

### `consolidate_journals`

Merges journal fragment files (e.g. transaction CSV exports from Hargreaves Lansdown) into a
single standardised consolidated journal in XLSX format. Running the mode multiple times against
the same inputs is safe — duplicate events are detected and skipped (idempotent).

#### Usage

```
python pipeline.py consolidate_journals JOURNAL_PATH FRAGMENTS_DIR METHOD ACCOUNT
```

#### Arguments

| Position | Name | Description |
|---|---|---|
| 1 | `JOURNAL_PATH` | Path to the consolidated journal XLSX. Created if it does not exist; updated in place if it does. The parent directory must already exist. |
| 2 | `FRAGMENTS_DIR` | Directory containing the journal fragment files to process. Must exist. |
| 3 | `METHOD` | Consolidation method — determines how fragment files are parsed. Currently accepted: `HL`. |
| 4 | `ACCOUNT` | Free-text account name written into the `account` column of every output row (e.g. `"ISA 2024"`). |

#### Output schema

The consolidated journal XLSX always has these seven columns, in this order:

| Column | Type | Description |
|---|---|---|
| `date` | date | Settlement date (preferred); trade date used only if settlement date is absent |
| `account` | string | Account name passed as the fourth argument |
| `sub_account` | string | Investment or position name (e.g. fund or stock name) |
| `action` | string | Normalised action: `buy`, `sell`, `contrib`, or `withdrawal` |
| `reference` | string | Original transaction reference from the source file |
| `value` | decimal | Transaction value in GBP |
| `quantity` | decimal | Number of units (empty for cash-only events) |

#### Consolidation methods

**`HL` — Hargreaves Lansdown CSV exports**

Parses CSV files exported from the Hargreaves Lansdown platform:

- Skips all preamble rows until a header row beginning `Trade date, Settle date, ...` is found
- Uses the **Settle date** column as the event date
- Maps transaction references to actions:
  - Reference matching `B` + digits (e.g. `B12345`) → `buy`
  - Reference matching `S` + digits (e.g. `S67890`) → `sell`
  - Reference of `Deposit` or starting with `BACS` → `contrib`
  - Any other reference pattern → reported as a parse error
- Strips the unit-cost/quantity suffix from the Description column (e.g.
  `"Vanguard US Equity Fund 10.00 @ £200.00"` → `"Vanguard US Equity Fund"`)
- Non-CSV files in the input directory are ignored

#### Deduplication

When an existing journal is updated, events are deduplicated using a composite key:

- **Buy/sell transactions**: `date + reference` (the provider reference is unique per trade)
- **Cash movements** (contrib/deposit): `date + action + value` (no unique reference available)

An event already present in the journal is counted as **merged** (skipped); a new event is
counted as **inserted**.

#### Console output

```
=== Consolidation Summary ===

SUCCESS
  Files processed:  3
  Events inserted:  87
  Events merged:    0
  Events removed:   0

ERRORS
  None
```

When parse errors occur:

```
=== Consolidation Summary ===

SUCCESS
  Files processed:  3
  Events inserted:  85
  Events merged:    0
  Events removed:   0

ERRORS (2 total)
  [march_2025.csv] Line 14: Invalid date "31/13/2025" in Settle date column
  [april_2025.csv] No header row found matching 'Trade date / Settle date'
```

The mode exits with code `0` even when parse errors exist (partial success). Processing
continues for all remaining files when one file fails.

#### Examples

First-time consolidation — create a new journal from a directory of HL exports:

```bash
python pipeline.py consolidate_journals \
    data/my_journal.xlsx \
    data/hl_exports/ \
    HL \
    "ISA 2024"
```

Incremental update — add a new quarter of exports to an existing journal:

```bash
python pipeline.py consolidate_journals \
    data/my_journal.xlsx \
    data/hl_exports/2025_q1/ \
    HL \
    "ISA 2024"
```

---

### `example`

A placeholder mode used to validate that the pipeline framework is functioning correctly.
Not intended for production use.

```bash
python pipeline.py example --message "hello"
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Unrecognised mode name |
| `2` | Invalid arguments (missing required argument, unrecognised method, directory not found) |
| `3` | Unhandled execution failure |

---

## Logging

All structured log output is written to **stderr** as newline-delimited JSON. Each record includes
at minimum:

```json
{
  "timestamp": "2026-06-03T12:34:56.789Z",
  "level": "INFO",
  "logger": "pipeline.dispatcher",
  "message": "Dispatching to mode",
  "correlation_id": "a1b2c3d4-...",
  "mode_name": "consolidate_journals"
}
```

A **metrics record** is emitted at the end of every execution:

```json
{
  "event": "metrics",
  "correlation_id": "a1b2c3d4-...",
  "mode_name": "consolidate_journals",
  "start_time": "2026-06-03T12:34:56.000Z",
  "end_time": "2026-06-03T12:34:57.234Z",
  "duration_seconds": 1.234,
  "exit_status": 0
}
```

Redirect stderr to a file to retain logs:

```bash
python pipeline.py consolidate_journals data/journal.xlsx data/exports/ HL "ISA" 2> run.log
```

Use `--log-level DEBUG` to see per-row parse trace output.

---

## Development

### Running tests

```bash
# All tests (unit + BDD + integration)
python -m pytest tests/

# Unit tests only
python -m pytest tests/unit/

# BDD scenarios only
python -m pytest tests/features/

# With coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Quality gates

All four gates must pass before any change is considered complete:

```bash
# Type checking (zero errors required)
mypy --strict src/ pipeline.py

# Linting (zero violations required)
ruff check .

# Formatting (zero diffs required)
ruff format --check .
```

Apply formatting:

```bash
ruff format .
```

### Project structure

```
pipeline.py                        # Entrypoint — argument parsing and mode dispatch

src/
├── constants.py                   # Exit codes and log field name constants
├── context.py                     # ExecutionContext (correlation ID, start time, mode)
├── interfaces.py                  # ModeInterface Protocol
├── registry.py                    # ModeRegistry — register and look up modes
├── dispatcher.py                  # Dispatch logic — resolve mode, call execute()
├── logging_config.py              # Structured JSON logging setup
├── metrics.py                     # MetricsRecord and emit_metrics()
└── modes/
    ├── example/                   # Placeholder mode for framework validation
    └── consolidate_journals/      # Journal fragment consolidation mode
        ├── constants.py           # Column names, regex patterns, dedup keys
        ├── schema.py              # ActionType, JournalEvent, ParseError, ParseResult,
        │                          # ConsolidationMethod, ConsolidationSummary
        ├── journal_store.py       # JournalStore — XLSX load / merge / save
        ├── consolidator.py        # ConsolidationEngine — orchestrates parse → merge
        ├── mode.py                # ConsolidateJournalsMode + render_summary()
        └── parsers/
            ├── base.py            # FragmentParser Protocol
            └── hl.py              # HLFragmentParser — Hargreaves Lansdown CSV parser

tests/
├── unit/                          # pytest unit tests (per-module)
├── features/                      # Gherkin BDD .feature files + step implementations
├── integration/                   # Subprocess end-to-end tests
└── data/                          # Test fixture CSV files
```

### Adding a new mode

1. Create `src/modes/<your_mode>/mode.py` with a class that satisfies `ModeInterface`
   (attributes `name` and `description`; methods `register_arguments` and `execute`)
2. Register it in `pipeline.py` inside `_build_registry()`
3. Write BDD scenarios in `tests/features/<your_mode>.feature` and unit tests in
   `tests/unit/<your_mode>/`

No changes to the dispatcher, registry, or argument parser are required.

### Adding a new consolidation method

1. Add a new value to `ConsolidationMethod` in `src/modes/consolidate_journals/schema.py`
2. Implement a class satisfying the `FragmentParser` Protocol in
   `src/modes/consolidate_journals/parsers/`
3. Add a branch to `_get_parser()` in `src/modes/consolidate_journals/consolidator.py`
