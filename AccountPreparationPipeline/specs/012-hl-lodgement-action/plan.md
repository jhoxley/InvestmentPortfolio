# Implementation Plan: HL Lodgement Action Mapping

**Branch**: `012-hl-lodgement-action` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/012-hl-lodgement-action/spec.md`

## Summary

Extend the HL journal parser to recognise lodgement transactions (in-specie security transfers)
identified by `L`+digits references (e.g. `L003538235`). Assign action type `lodgement` and
derive the sub-account from the description by stripping the leading `"Lodgement "` prefix.
This is a surgical, three-file change: `schema.py` (new enum value), `constants.py` (two new
constants), and `parsers/hl.py` (two new branches). No new modules, no new dependencies.

## Technical Context

**Language/Version**: Python 3.11+ (existing project standard)
**Primary Dependencies**: `re` (stdlib — already used for `RE_BUY`, `RE_SELL`); no new packages
**Storage**: N/A — parser-only change; output is `JournalEvent` objects fed to the existing journal store
**Testing**: `pytest` (unit tests in `tests/unit/`), `pytest-bdd` (BDD scenarios in `tests/features/`)
**Target Platform**: Windows/cross-platform CLI (existing project context)
**Project Type**: Parser extension within existing `consolidate_journals` CLI mode
**Performance Goals**: No specific latency requirement; lodgement rows are rare (tens per journal)
**Constraints**: No new runtime dependencies; all changes within existing module boundaries
**Scale/Scope**: Surgical edit to 3 existing files + 1 new CSV fixture + test additions

## Constitution Check

- [X] Virtual environment (`.venv`) is initialised; dependencies declared in `requirements.txt` /
  `requirements-dev.txt`; tool config in `pyproject.toml` — **already in place; no new deps**
- [X] No magic numbers or strings — `RE_LODGEMENT` and `LODGEMENT_DESCRIPTION_PREFIX` extracted
  to `constants.py`; `ActionType.LODGEMENT` extracted to `schema.py`
- [X] SOLID principles — existing `_map_action()` and `_parse_row()` each have SRP; adding one
  branch each does not violate SRP. No new classes introduced
- [X] All code fully type-annotated; `mypy --strict` planned as quality gate
- [X] `ruff check` + `ruff format --check` planned as quality gate
- [X] BDD Gherkin scenario planned in `tests/features/consolidate_journals.feature`;
  unit tests in `tests/unit/consolidate_journals/parsers/test_hl_parser.py`
- [X] Structured logging — existing `_logger.debug("HL parse complete", ...)` covers all rows;
  no additional log sites needed for this narrow change

## Project Structure

### Documentation (this feature)

```text
specs/012-hl-lodgement-action/
├── plan.md          ← this file
├── research.md      ← Phase 0 output
├── data-model.md    ← Phase 1 output
└── tasks.md         ← /speckit-tasks output (not yet created)
```

### Source Code — Modified Files Only

```text
src/modes/consolidate_journals/
├── schema.py          ← ADD ActionType.LODGEMENT = "lodgement"
├── constants.py       ← ADD RE_LODGEMENT, LODGEMENT_DESCRIPTION_PREFIX
└── parsers/
    └── hl.py          ← UPDATE _map_action(), UPDATE _parse_row()

tests/
├── features/
│   └── consolidate_journals.feature   ← ADD lodgement scenarios (3–4 scenarios)
│   └── steps/
│       └── consolidate_journals_steps.py  ← ADD @given step for lodgement fixture (if needed)
├── unit/
│   └── consolidate_journals/
│       └── parsers/
│           └── test_hl_parser.py      ← ADD TestLodgementActionMapping class
└── data/
    └── consolidate_journals/
        └── valid_hl_lodgement.csv     ← NEW: 2-row lodgement fixture
```

**Structure Decision**: No new source files — all changes are additions/extensions to existing
files. This follows the Open/Closed principle: the parser is extended (new enum value, new
constants, new branches) without modifying the existing mapping table or sub-account logic for
other action types.

## Complexity Tracking

No constitution violations. No new patterns beyond what already exists in the HL parser.
