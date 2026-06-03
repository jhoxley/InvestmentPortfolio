# Implementation Plan: Journal Fragment Consolidation

**Branch**: `002-consolidate-journals` | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-consolidate-journals/spec.md`

## Summary

Add a `consolidate_journals` mode to the pipeline that accepts four arguments (output XLSX path,
input directory, consolidation method, account name) and merges journal fragment files into a
single standardised XLSX journal. The `HL` method parses Hargreaves Lansdown CSV exports,
maps transactions to normalised actions (`buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal`),
deduplicates against any existing journal content using a `date + reference` composite key, applies
sub-account derivation rules (investment name from description, or `"Cash"` for non-trade actions),
and outputs a two-section success/error summary to both stdout and the structured log. The mode
slots into the existing `ModeInterface` / `ModeRegistry` framework with no changes to the
dispatcher.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `python-json-logger>=2.0` (existing); `pandas>=2.0,<3.0`,
`openpyxl>=3.1,<4.0` (runtime); `pytest`, `pytest-bdd`, `pytest-cov`, `mypy`, `ruff`,
`pandas-stubs>=2.0,<3.0` (dev/test)
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

- [x] Virtual environment (`.venv`) already initialised; `pandas`, `openpyxl`, `pandas-stubs`
  added to `requirements.txt` / `requirements-dev.txt`; `pyproject.toml` unchanged
- [x] No magic numbers or strings — column names, action strings, regex patterns, number formats,
  and summary labels extracted to `src/modes/consolidate_journals/constants.py`
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
└── tasks.md                       # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
src/modes/consolidate_journals/
├── __init__.py
├── mode.py              # ConsolidateJournalsMode — ModeInterface implementation
├── constants.py         # Column names, regex patterns, action sets, number formats, labels
├── schema.py            # ActionType, ConsolidationMethod enums; JournalEvent, ParseError,
│                        # ParseResult, ConsolidationSummary dataclasses
├── journal_store.py     # JournalStore — XLSX load/merge/save with numeric column formatting
├── consolidator.py      # ConsolidationEngine — orchestrates parse → merge → summary
└── parsers/
    ├── __init__.py
    ├── base.py          # FragmentParser Protocol
    └── hl.py            # HLFragmentParser — HL CSV parse logic

tests/
├── features/
│   ├── consolidate_journals.feature          # BDD Gherkin acceptance scenarios
│   └── steps/
│       └── consolidate_journals_steps.py
├── unit/
│   └── consolidate_journals/
│       ├── __init__.py
│       ├── test_schema.py           # ActionType, JournalEvent, ParseError, ConsolidationSummary
│       ├── test_journal_store.py    # Load, merge, save, dedup, numeric formatting
│       ├── test_consolidator.py     # Engine orchestration
│       └── parsers/
│           ├── __init__.py
│           └── test_hl_parser.py    # Header discovery, action mapping, sub-account rules, errors
├── integration/
│   └── test_consolidate_journals_e2e.py  # Subprocess end-to-end
└── data/
    └── consolidate_journals/
        ├── valid_hl_simple.csv           # 3 rows, no preamble
        ├── valid_hl_with_preamble.csv    # 3 rows, with metadata preamble before header
        ├── valid_hl_contrib.csv          # Deposit and BACS rows
        ├── valid_hl_contrib_ref.csv      # Row with literal "contrib" reference
        ├── valid_hl_transfer_uri.csv     # Transfer (non-income) and URI reference rows
        ├── valid_hl_income_transfer.csv  # Transfer with income description
        ├── valid_hl_fee_interest.csv     # MANAGE FEE and INTEREST rows
        ├── valid_hl_rdp_cr.csv           # RDP CR reference row
        ├── valid_hl_fee_sale.csv         # Sell row with " Fee Sale -" description suffix
        ├── invalid_no_header.csv         # No recognisable header row
        └── invalid_bad_value.csv         # One row with non-numeric value, one valid row
```

**New runtime dependencies** (in `requirements.txt`):
```
pandas>=2.0,<3.0
openpyxl>=3.1,<4.0
```

**New dev dependencies** (in `requirements-dev.txt`):
```
pandas-stubs>=2.0,<3.0
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
- `execute`: validates args (directory exists, method enum valid), instantiates engine, calls
  `engine.run()`, calls `render_summary()`, prints to stdout, emits structured log record,
  returns exit code
- `render_summary(summary) -> str`: pure function; produces two-section console block

**`constants.py`**
- `JOURNAL_COLUMNS: list[str]` — ordered list of 7 column names for the output schema
- `DEDUP_KEY_COLUMNS: list[str]` — `["date", "reference"]`
- `DEDUP_FALLBACK_KEY_COLUMNS: list[str]` — `["date", "action", "value"]`
- `HL_HEADER_COL0: str`, `HL_HEADER_COL1: str` — expected header row cell values
- `HL_DEPOSIT_REFERENCES: frozenset[str]` — `{"Deposit", "BACS"}`
- `RE_BUY`, `RE_SELL` — compiled regex patterns (`^B\d+$`, `^S\d+$`)
- `RE_BACS` — compiled regex pattern (`^BACS`, case-insensitive)
- `RE_DESCRIPTION_SUFFIX` — regex to strip trailing `<qty> @ <price>` from descriptions
- `CASH_SUB_ACCOUNT: str` — `"Cash"`
- `CASH_ACTION_TYPES: frozenset[str]` — `{"deposit", "fee", "income"}`
- `SUB_ACCOUNT_STRIP_SUFFIXES: tuple[str, ...]` — trailing suffixes to remove from sub_account
- `NUMBER_FORMAT_VALUE: str` — `"#,##0.00"` (XLSX number format for value column)
- `NUMBER_FORMAT_QUANTITY: str` — `"#,##0.######"` (XLSX number format for quantity column)
- Summary label constants

**`schema.py`**
- `ActionType(StrEnum)` — `BUY`, `SELL`, `DEPOSIT`, `INCOME`, `FEE`, `WITHDRAWAL`
- `ConsolidationMethod(StrEnum)` — `HL`
- `JournalEvent` — `@dataclass(frozen=True)` with all seven fields
- `ParseError` — `@dataclass(frozen=True)`
- `ParseResult` — `@dataclass(frozen=True)` with `events` + `errors` lists
- `ConsolidationSummary` — `@dataclass(frozen=True)` with counts + errors list

**`journal_store.py` — JournalStore**
- `load(path: Path) -> JournalStore`: reads XLSX into DataFrame if file exists (converting
  `value` and `quantity` columns to numeric via `pd.to_numeric`), else returns empty DataFrame
- `merge(events: list[JournalEvent]) -> tuple[int, int]`: stores `value`/`quantity` as `float`;
  applies `date + reference` dedup key for buy/sell, `date + action + value` fallback for
  non-trade events; returns `(inserted, merged)` counts
- `save(path: Path) -> None`: writes via `pd.ExcelWriter`; applies `NUMBER_FORMAT_VALUE` to
  the `value` column and `NUMBER_FORMAT_QUANTITY` to the `quantity` column; atomically replaces
  the target file via temp-file rename

**`parsers/base.py`**
- `FragmentParser` Protocol with `parse(file_path, account) -> ParseResult`

**`parsers/hl.py` — HLFragmentParser**
- `_read_text(file_path)`: reads file attempting `utf-8-sig` first, then `cp1252` fallback
- Parses CSV using `csv.reader(io.StringIO(content))`
- Scans for header row (`Trade date` / `Settle date`); all pre-header rows discarded
- Per data row: parse settle date, apply action mapping (FR-012), apply sub-account rules
  (FR-013), parse value/quantity as `Decimal`
- All row-level failures captured as `ParseError` with line number; file-level failures
  (no header, undecodable file) captured without line number
- Never raises; always returns `ParseResult`

**`consolidator.py` — ConsolidationEngine**
- `run(journal_path, fragments_dir, method, account) -> ConsolidationSummary`
- Calls `JournalStore.load()`, resolves parser via `_get_parser(method)` factory, iterates
  `*.csv` files in `fragments_dir` (for HL method), calls `parser.parse()` for each, calls
  `store.merge()`, accumulates errors, calls `store.save()`, returns `ConsolidationSummary`

### HL Action Mapping Rules

```
Reference pattern             → Action
─────────────────────────────────────────────────────
^B\d+$                        → buy
^S\d+$                        → sell
Deposit, BACS, BACS*          → deposit
"contrib" (any case)          → deposit
"Transfer" + "income" in desc → income
"Transfer" (other desc)       → deposit
URI* (any case)               → income
MANAGE FEE (any case)         → fee
INTEREST, RDP CR (any case)   → income
(no match)                    → ParseError
```

### HL Sub-Account Rules

```
1. action in {deposit, fee, income}  → sub_account = "Cash"  (stop)
2. otherwise                         → strip "<qty> @ <price>" suffix from Description
3.                                   → strip any suffix in SUB_ACCOUNT_STRIP_SUFFIXES
                                        (currently: " Fee Sale -")
```

### Key Deduplication Logic

```
For each event from fragment:
  if reference matches ^B\d+$ or ^S\d+$ (buy/sell transaction):
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
