# Implementation Plan: Dividend Cash Offset Entries

**Branch**: `010-dividend-cash-offset` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-dividend-cash-offset/spec.md`

## Summary

Extend offset generation in `consolidate_journals` to include `dividend` action type alongside
existing `buy` and `sell` actions. The change touches three files in the existing
`consolidate_journals` mode:

1. `OffsetGenerator.generate()` — add `ActionType.DIVIDEND` to the action filter
2. `JournalStore.missing_offset_trades()` — extend backfill scan to dividend rows
3. `JournalStore.rectify_offsets()` — extend value-correction pass to dividend events
4. `JournalStore._is_transaction_reference()` — extend dedup key selection to dividend offset refs
5. `constants.py` — remove `RE_OFFSET` (superseded by `OFFSET_SUFFIX` string check)

The same-sign rule (offset value = dividend value, both positive) is inherited from Feature 006
with no additional sign logic. No new constants, entities, or CLI parameters are required.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pandas, openpyxl (existing; no new dependencies)
**Storage**: XLSX journal file (existing `JournalStore`)
**Testing**: pytest + pytest-bdd (existing test suites — extend only)
**Target Platform**: Windows/cross-platform CLI (existing pipeline)
**Project Type**: CLI data pipeline
**Performance Goals**: No change from baseline; same throughput as existing offset generation
**Constraints**: OFFSET_SUFFIX (`"-offset"`) already produces the correct dividend offset
  references (`"ST DIV-offset"`, `"OVR CR-offset"`, etc.); no new constant required
**Scale/Scope**: Income account journals (tens to hundreds of dividend events per account per year)

## Constitution Check

- [X] Virtual environment (`.venv`) is initialised; dependencies declared in `requirements.txt` /
  `requirements-dev.txt`; tool config in `pyproject.toml`
- [X] No magic numbers or strings — all values flow from existing named constants (`OFFSET_SUFFIX`,
  `CASH_SUB_ACCOUNT`, `ActionType.DIVIDEND`)
- [X] SOLID principles applied — change is Open/Closed compliant: extending behaviour by modifying
  the action-type filter, not adding new responsibilities to existing classes
- [X] All code fully type-annotated; `mypy --strict` planned as a quality gate
- [X] `ruff check` + `ruff format --check` planned as a quality gate; `RE_OFFSET` removal
  eliminates a pending unused-import violation once the feature lands
- [X] BDD Gherkin scenarios planned in `tests/features/`; `pytest` unit tests planned in
  `tests/unit/`
- [X] Structured logging: existing log points in `OffsetGenerator` and `JournalStore` cover all
  relevant milestones; no new log sites required for this surgical change

## Project Structure

### Documentation (this feature)

```text
specs/010-dividend-cash-offset/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal — no new entities)
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (affected files only)

```text
src/modes/consolidate_journals/
├── offset_generator.py        # CHANGE: Add ActionType.DIVIDEND to generate() filter; update docstring
├── journal_store.py           # CHANGE: Extend missing_offset_trades(), rectify_offsets(),
│                              #         _is_transaction_reference() (see research.md for rationale)
└── constants.py               # CHANGE: Remove RE_OFFSET (see research.md Decision 3)

tests/
├── features/
│   └── consolidate_journals.feature       # ADD: 2 BDD scenarios (dividend offset generated; idempotency)
├── features/steps/
│   └── consolidate_journals_steps.py      # ADD: step bindings for new scenarios
├── unit/consolidate_journals/
│   ├── test_offset_generator.py           # ADD: dividend offset unit tests
│   └── test_journal_store.py             # ADD: missing_offset_trades + rectify dividend tests
└── data/consolidate_journals/
    └── valid_hl_st_div.csv               # REUSE: existing Feature 009 fixture (no new file needed)
```

## Complexity Tracking

No constitution violations to justify. This is a surgical, additive change within the existing
`consolidate_journals` architecture — no new classes, abstractions, or dependencies.
