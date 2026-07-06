# Quickstart: Pipeline Entrypoint & Mode Dispatch

**Feature**: 001-pipeline-entrypoint
**Date**: 2026-05-31

## Prerequisites

- Python 3.11 or later
- `pip`

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install runtime dependencies
pip install -r requirements.txt

# 3. Install development/test dependencies
pip install -r requirements-dev.txt
```

## Run the pipeline

```bash
# Show all available modes
python pipeline.py --help

# Show arguments for the example mode
python pipeline.py example --help

# Execute the example mode
python pipeline.py example --message "hello world"

# Execute with debug-level logging
python pipeline.py --log-level DEBUG example --message "hello"
```

## Run tests

```bash
# All tests (unit + BDD + integration)
pytest

# Unit tests only
pytest tests/unit/

# BDD scenarios only
pytest tests/features/

# With coverage report
pytest --cov=src --cov-report=term-missing
```

## Run quality gates

```bash
# Type checking
mypy --strict src/

# Linting
ruff check .

# Formatting check
ruff format --check .

# All gates in one go
mypy --strict src/ && ruff check . && ruff format --check . && pytest
```

## Add a new mode

1. Create `src/modes/<your-mode-name>/mode.py` with a class that satisfies `ModeInterface`
   (see `contracts/mode-interface-contract.md`).
2. Register the mode instance in `pipeline.py` by calling `registry.register(YourMode())`.
3. Run `python pipeline.py --help` to verify the new mode appears.
4. Write BDD scenarios in `tests/features/<your-mode-name>.feature` and unit tests in
   `tests/unit/test_<your_mode_name>.py`.

**Zero changes to the dispatcher are required.**

## Validate against spec success criteria

| Criterion | Validation command |
|---|---|
| SC-001 — discover modes | `python pipeline.py --help` |
| SC-002 — discover mode args | `python pipeline.py example --help` |
| SC-003 — unrecognised mode exits clean | `python pipeline.py nonexistent` (check stderr, no traceback) |
| SC-004 — zero dispatcher changes for new mode | Add a mode per instructions above |
| SC-005/SC-006 — logs + metrics on every run | Run any mode; inspect stderr JSON output |
| SC-007 — all quality gates pass | Run the "all gates" command above |
