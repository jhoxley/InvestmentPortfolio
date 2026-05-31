# Implementation Plan: Journal Fragment Consolidation

**Branch**: `002-consolidate-journals` | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-consolidate-journals/spec.md`

## Summary

Add a `consolidate_journals` mode to the pipeline that accepts four arguments (output XLSX path,
input directory, consolidation method, account name) and merges journal fragment files into a
single standardised XLSX journal. The initial `HL` method parses Hargreaves Lansdown CSV exports,
maps transactions to normalised actions (`buy`, `sell`, `contrib`), deduplicates against any
existing journal content using a `date + reference` composite key, and outputs a two-section
success/error summary to both stdout and the structured log. The mode slots into the existing
`ModeInterface` / `ModeRegistry` framework with no changes to the dispatcher.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `python-json-logger>=2.0` (existing); `pandas>=2.0`, `openpyxl>=3.0`
(new runtime); `pytest`, `pytest-bdd`, `pytest-cov`, `mypy`, `ruff` (existing dev/test)
**Storage**: XLSX file on local filesystem (read + write via `pandas` + `openpyxl`)
**Testing**: `pytest` (unit), `pytest-bdd` (Gherkin BDD), `pytest` integration (subprocess)
**Target Platform**: Command-line; Windows / macOS / Linux (Python standard)
**Project Type**: CLI mode within existing pipeline framework
**Performance Goals**: Process 12 monthly HL CSV exports in under 60 seconds (SC-004)
**Constraints**: Idempotent — running twice against same inputs yields identical output (SC-002);
no intermediate directory creation for output path (Assumption 7)
**Scale/Scope**: Single-developer tool; initial delivery includes `HL` method only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Virtual environment (`.venv`) already initialised; `pandas` and `openpyxl` added to
  `requirements.txt`; `pyproject.toml` unchanged (existing tool config applies)
- [x] No magic numbers or strings — column names, action strings, regex patterns, and
  summary labels extracted to `src/modes/consolidate_journals/constants.py`
- [x] SOLID principles applied — `FragmentParser` Protocol (OCP/LSP/ISP), `ConsolidationEngine`
  takes parser via factory (DIP), `JournalStore` has single reason to change (SRP),
  `HLFragmentParser` only knows about HL format (SRP)
- [x] All code fully type-annotated; `mypy --strict src/` planned as quality gate
- [x] `ruff check .` + `ruff format --check .` planned as quality gates
- [x] BDD Gherkin scenarios in `tests/features/consolidate_journals.feature`; pytest unit tests
  in `tests/unit/consolidate_journals/`; integration tests in `tests/integration/`
- [x] Structured logging covers: mode entry, per-file parse start/end, per-error warning,
  consolidation summary, mode exit

**Post-design re-check**: All gates confirmed after Phase 1 design. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-consolidate-journals/
├── plan.md                        # This file
├── research.md                    # Phase 0 decisions
├── data-model.md                  # Entity definitions
├── quickstart.md                  # Setup + run instructions
├── contracts/
│   ├── cli-contract.md            # CLI argument and output contract
│   └── fragment-parser-contract.md  # FragmentParser Protocol contract
└── tasks.md                       # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code

```text
src/modes/consolidate_journals/
├── __init__.py
├── mode.py              # ConsolidateJournalsMode — ModeInterface implementation
├── constants.py         # COLUMN_* names, ACTION_* strings, regex patterns, summary labels
├── schema.py            # ActionType enum, JournalEvent, ParseError, ParseResult,
│                        # ConsolidationSummary dataclasses
├── journal_store.py     # JournalStore — XLSX load/merge/save
├── consolidator.py      # ConsolidationEngine — orchestrates parse → merge → summary
└── parsers/
    ├── __init__.py
    ├── base.py          # FragmentParser Protocol
    └── hl.py            # HLFragmentParser — HL CSV parse logic

tests/
├── features/
│   └── consolidate_journals.feature  # BDD Gherkin acceptance scenarios
│       └── steps/
│           └── consolidate_journals_steps.py
├── unit/
│   └── consolidate_journals/
│       ├── __init__.py
│       ├── test_schema.py           # ActionType, JournalEvent, ParseError, ConsolidationSummary
│       ├── test_journal_store.py    # Load empty, load existing, merge, save
│       ├── test_consolidator.py     # Engine integration (mocked parser)
│       └── parsers/
│           ├── __init__.py
│           └── test_hl_parser.py    # Header discovery, action mapping, description stripping, errors
└── integration/
│   └── test_consolidate_journals_e2e.py  # Subprocess end-to-end
└── data/
    └── consolidate_journals/
        ├── valid_hl_simple.csv           # 3 rows, no preamble
        ├── valid_hl_with_preamble.csv    # 3 rows, with preamble rows before header
        ├── valid_hl_contrib.csv          # Deposit and BACS rows
        ├── invalid_no_header.csv         # No recognisable header row
        └── invalid_bad_value.csv         # One row with non-numeric value
```

**New runtime dependencies** (add to `requirements.txt`):
```
pandas>=2.0,<3.0
openpyxl>=3.1,<4.0
```

**Structure Decision**: Single project layout; the new mode follows the exact same pattern as
`src/modes/example/`. The `ConsolidationEngine` and `JournalStore` are separate from `mode.py`
to keep `mode.py` thin (argument parsing → delegate → return exit code only).

## Complexity Tracking

> No constitution violations. Table omitted.

---

## Implementation Notes

### Module Responsibilities

**`mode.py` — ConsolidateJournalsMode**
- Declares `name = "consolidate_journals"`, `description = "..."`
- `register_arguments`: adds 4 positional args (`journal_path`, `fragments_dir`, `method`,
  `account`) with full `help=` strings
- `execute`: validates args (path exists, method enum valid), instantiates engine, calls
  `engine.run()`, renders summary to stdout + log, returns exit code

**`constants.py`**
- `JOURNAL_COLUMNS: list[str]` — ordered list of column names for the output schema
- `DEDUP_KEY_COLUMNS: list[str]` — `["date", "reference"]`
- `DEDUP_FALLBACK_KEY_COLUMNS: list[str]` — `["date", "action", "value"]`
- `HL_HEADER_COL0: str`, `HL_HEADER_COL1: str` — expected header row cell values
- `RE_BUY`, `RE_SELL` — compiled regex patterns for reference matching
- `HL_CONTRIB_ACTIONS: frozenset[str]` — `{"Deposit", "BACS"}`
- Summary label constants

**`schema.py`**
- `ActionType(str, Enum)` — `BUY`, `SELL`, `CONTRIB`, `WITHDRAWAL`
- `JournalEvent` — `@dataclass(frozen=True)` with all seven fields
- `ParseError` — `@dataclass(frozen=True)`
- `ParseResult` — `@dataclass(frozen=True)` with `events` + `errors` lists
- `ConsolidationSummary` — `@dataclass(frozen=True)` with counts + errors list

**`journal_store.py` — JournalStore**
- `load(path: Path) -> JournalStore`: reads XLSX into DataFrame if file exists, else empty DataFrame
- `merge(events: list[JournalEvent]) -> tuple[int, int]`: anti-join on dedup key, concat new
  rows; returns `(inserted, merged)` counts
- `save(path: Path) -> None`: write to temp file, rename (atomic)

**`parsers/base.py`**
- `FragmentParser` Protocol with `parse(file_path, account) -> ParseResult`

**`parsers/hl.py` — HLFragmentParser**
- Open file with `csv.reader`
- Scan for header row; map column indices
- Iterate data rows; for each: parse date, map action, strip description, parse value/quantity
- Collect events + errors; return `ParseResult`

**`consolidator.py` — ConsolidationEngine**
- `run(journal_path, fragments_dir, method, account) -> ConsolidationSummary`
- Calls `JournalStore.load()`, resolves parser, iterates fragment files, calls
  `parser.parse()`, calls `store.merge()`, calls `store.save()`, builds and returns summary

### Key Deduplication Logic

```
For each event from fragment:
  if reference is non-empty and looks like a transaction ID (matches B/S pattern):
    key = (date, reference)
  else:
    key = (date, action_string, value)
  if key already in journal → count as merged (skip)
  else → count as inserted (add row)
```

### Summary Rendering

The `ConsolidateJournalsMode.execute()` method calls a pure `render_summary(summary) -> str`
function and prints the result. The same data is also emitted as a structured log record. This
keeps the rendering logic independently testable.
