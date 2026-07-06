# Quickstart: Journal Fragment Consolidation

**Feature**: 002-consolidate-journals
**Date**: 2026-05-31

## Prerequisites

- Python 3.11+ installed
- Virtual environment activated: `.venv/Scripts/activate` (Windows) or
  `source .venv/bin/activate` (Unix)
- Dependencies installed: `pip install -r requirements.txt`

## Running the Mode

### First-time consolidation (creates a new journal)

```
python pipeline.py consolidate_journals \
    data/my_journal.xlsx \
    data/hl_exports/ \
    HL \
    "My ISA"
```

- `data/my_journal.xlsx` — output XLSX path; will be created
- `data/hl_exports/` — directory containing HL CSV export files
- `HL` — consolidation method
- `"My ISA"` — account label written into every row

### Incremental update (adds new exports to existing journal)

```
python pipeline.py consolidate_journals \
    data/my_journal.xlsx \
    data/hl_exports/2025_q2/ \
    HL \
    "My ISA"
```

Running the same command twice is safe — duplicate events are detected and skipped.

### Getting help

```
python pipeline.py consolidate_journals --help
```

## Expected Output

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

If problems occur:

```
=== Consolidation Summary ===

SUCCESS
  Files processed:  3
  Events inserted:  85
  Events merged:    0
  Events removed:   0

ERRORS (2 total)
  [march_2025.csv] Line 14: Unparseable date "31/13/2025" in Settle date column
  [april_2025.csv] No header row found matching "Trade date / Settle date" pattern
```

Exit code is `0` even when parse errors occur (partial success). Exit code `2` means invalid
arguments; exit code `3` means the output file could not be written.

## Running Tests

```bash
# All tests (unit + BDD)
python -m pytest tests/

# Specific to this feature
python -m pytest tests/unit/consolidate_journals/ tests/features/consolidate_journals.feature -v

# With coverage
python -m pytest tests/unit/consolidate_journals/ --cov=src/modes/consolidate_journals --cov-report=term-missing
```

## Quality Gates

```bash
# Type checking
mypy --strict src/

# Linting
ruff check .
ruff format --check .
```

All four gates must be green before the feature is considered complete.

## Input File Format (HL CSV)

Hargreaves Lansdown CSV exports contain metadata rows at the top before the actual data header.
The pipeline automatically skips preamble rows and begins processing from the row containing
`Trade date, Settle date, ...` onwards.

Example HL CSV structure:
```
Hargreaves Lansdown
Account name,...
Date range,...
<blank>
Trade date,Settle date,Reference,Description,Unit cost,Qty,Value (£),...
15/01/2024,17/01/2024,B12345,"Vanguard US Equity Index 10.00 @ £200.00",...
```

The pipeline uses the **Settle date** column as the canonical event date.
