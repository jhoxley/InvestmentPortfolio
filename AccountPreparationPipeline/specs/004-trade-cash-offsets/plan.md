# Implementation Plan: Trade Cash Offset Entries

**Branch**: `004-trade-cash-offsets` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-trade-cash-offsets/spec.md`

## Summary

Extend the existing `consolidate_journals` mode with an offset-backfill step that, after every
consolidation run, scans the full journal for any `buy` or `sell` event lacking a corresponding
`"trading"` Cash offset row and inserts the missing offsets. Each offset carries
`sub_account = "Cash"`, `action = "trading"`, a negated value and quantity, and a reference
formed by appending `"-offset"` to the trade reference. Running the mode on an existing journal
(pre-deployment) will retroactively generate all missing offsets in a single run. No new CLI
mode or arguments are required.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pandas>=2.0,<3.0`, `openpyxl>=3.1,<4.0` (all existing)
**Storage**: XLSX files on local filesystem (read + write via `pandas` + `openpyxl`)
**Testing**: `pytest` (unit), `pytest-bdd` (Gherkin BDD), `pytest` integration (subprocess)
**Target Platform**: Command-line; Windows / macOS / Linux
**Project Type**: Enhancement to existing CLI mode within the pipeline framework
**Performance Goals**: Backfill scan is O(N) over buy/sell rows in the journal — negligible
  for typical journal sizes; ≤5 s additional time per SC-004
**Constraints**: Idempotent (SC-002); no new runtime dependencies; no new CLI arguments; no
  changes to the XLSX schema; backfill must leave journal consistent with SC-001 after any run
**Scale/Scope**: Single-developer tool; matches existing scope of `consolidate_journals`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Virtual environment (`.venv`) already initialised; no new runtime dependencies — all
  required packages (`pandas`, `openpyxl`) already declared in `requirements.txt`
- [x] No magic numbers or strings — `OFFSET_SUFFIX`, `RE_OFFSET`, `ActionType.TRADING`
  extracted to `constants.py` and `schema.py`; no raw strings in business logic
- [x] SOLID principles applied — `OffsetGenerator` (SRP: offset computation only);
  `ConsolidationEngine` delegates to `OffsetGenerator` for the backfill pass; `JournalStore`
  extended minimally with a backfill query method; no shared mutable state
- [x] All code fully type-annotated; `mypy --strict src/` planned as quality gate
- [x] `ruff check .` + `ruff format --check .` planned as quality gates
- [x] BDD Gherkin scenarios added to `tests/features/consolidate_journals.feature`; pytest
  unit tests in `tests/unit/consolidate_journals/test_offset_generator.py`; integration tests
  in `tests/integration/test_consolidate_journals_e2e.py`
- [x] Structured logging: backfill milestone logged in `ConsolidationEngine.run()` with
  count of offsets generated; no new `print()` statements

**Post-design re-check**: All gates confirmed. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/004-trade-cash-offsets/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Entity definitions and constant additions
├── quickstart.md        # Setup + run instructions
├── contracts/
│   └── cli-contract.md  # CLI delta contract
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code Changes

```text
src/modes/consolidate_journals/
├── schema.py              # ADD ActionType.TRADING = "trading"
├── constants.py           # ADD OFFSET_SUFFIX, RE_OFFSET
├── journal_store.py       # ADD missing_offset_trades() query method
│                          # EXTEND _is_transaction_reference() for RE_OFFSET
├── consolidator.py        # ADD backfill pass after all files merged
└── offset_generator.py    # NEW: OffsetGenerator class

tests/
├── features/
│   ├── consolidate_journals.feature               # ADD offset + backfill BDD scenarios
│   └── steps/
│       └── consolidate_journals_steps.py          # ADD step implementations
├── unit/
│   └── consolidate_journals/
│       └── test_offset_generator.py               # NEW: OffsetGenerator unit tests
└── integration/
    └── test_consolidate_journals_e2e.py           # ADD offset + backfill integration tests
```

**Structure Decision**: All changes within the existing `consolidate_journals` module. The new
`offset_generator.py` follows the single-file, single-class pattern established by the other
module files. No new package or subpackage is created.

## Complexity Tracking

> No constitution violations. Table omitted.

---

## Implementation Notes

### `schema.py` — ActionType extension

```python
class ActionType(StrEnum):
    ...
    TRADING = "trading"   # Synthetic cash offset for buy/sell trades
```

### `constants.py` — new constants

```python
OFFSET_SUFFIX: str = "-offset"
RE_OFFSET: re.Pattern[str] = re.compile(r"^[BS]\d+-offset$")
```

`RE_OFFSET` matches offset references of the form `Bxxx-offset` / `Sxxx-offset` and is used
to classify them as "transaction references" for reference-based deduplication.

### `journal_store.py` — two additions

**1. `missing_offset_trades()` — new public method**

Returns a `pd.DataFrame` containing every row in the journal with `action in ("buy", "sell")`
for which no corresponding offset row (reference = `<trade-ref>-offset`) currently exists:

```python
def missing_offset_trades(self) -> pd.DataFrame:
    """Return buy/sell rows that have no corresponding offset row."""
    if self._df.empty:
        return self._df.iloc[0:0]
    trade_mask = self._df["action"].isin(
        {ActionType.BUY.value, ActionType.SELL.value}
    )
    existing_offset_refs: set[str] = set(
        self._df.loc[
            self._df["action"] == ActionType.TRADING.value, "reference"
        ]
    )
    needs_offset = trade_mask & ~self._df["reference"].apply(
        lambda ref: (ref + OFFSET_SUFFIX) in existing_offset_refs
    )
    return self._df[needs_offset].copy()
```

**2. Extend `_is_transaction_reference()`**

```python
from src.modes.consolidate_journals.constants import RE_BUY, RE_OFFSET, RE_SELL

def _is_transaction_reference(reference: str) -> bool:
    return bool(
        RE_BUY.match(reference)
        or RE_SELL.match(reference)
        or RE_OFFSET.match(reference)
    )
```

### `offset_generator.py` — new file

```python
class OffsetGenerator:
    def generate(self, trades: pd.DataFrame | list[JournalEvent]) -> list[JournalEvent]:
        """Return one synthetic Cash offset JournalEvent per buy/sell trade."""
```

Accepts either a `pd.DataFrame` slice (from `missing_offset_trades()`) or a list of
`JournalEvent` objects. Iterates rows, creates a `JournalEvent` per trade:

```python
JournalEvent(
    date=event.date,
    account=event.account,
    sub_account=CASH_SUB_ACCOUNT,
    action=ActionType.TRADING,
    reference=event.reference + OFFSET_SUFFIX,
    value=-event.value,
    quantity=-event.value,   # Cash: quantity mirrors value
)
```

No I/O; fully deterministic; independently unit-testable without importing the engine or mode.

### `consolidator.py` — backfill integration

After `store.save(journal_path)` in `ConsolidationEngine.run()`, add a backfill pass:

```python
# Backfill: generate offsets for any buy/sell without a matching offset row
missing_trades = store.missing_offset_trades()
if not missing_trades.empty:
    offsets = OffsetGenerator().generate_from_df(missing_trades)
    inserted, _ = store.merge(offsets)
    total_inserted += inserted
    store.save(journal_path)
    _logger.info(
        "Offset backfill complete",
        extra={"offsets_generated": inserted},
    )
```

The backfill save is a second write only when missing offsets exist. On subsequent runs
(when the journal is already fully offset), `missing_trades` is empty and no extra write occurs.

### `OffsetGenerator` — dual interface

`OffsetGenerator` exposes two methods to support both call sites cleanly:

- `generate(events: list[JournalEvent]) -> list[JournalEvent]` — used in unit tests and for
  generating offsets from freshly-parsed events (future use)
- `generate_from_df(trades: pd.DataFrame) -> list[JournalEvent]` — used by the backfill pass,
  converting the DataFrame rows into `JournalEvent` objects before building offsets

Both methods share the same core offset-construction logic (extracted to a private helper).

### Backfill idempotency

`missing_offset_trades()` checks for the **absence** of the offset reference in the journal.
On a second run, the offset rows already exist, so `missing_offset_trades()` returns an empty
DataFrame, the backfill block is skipped entirely, and no extra write occurs. Idempotency is
preserved per SC-002.

### Test data strategy

All test inputs created programmatically via `pandas.DataFrame.to_excel()` into `tmp_path`.
No new binary fixture files.

**New test scenarios required:**

- Unit: `test_offset_generator.py` — generate from list of JournalEvents; generate from
  DataFrame; buy and sell produce correct fields; non-trade actions produce no offsets; empty
  input produces empty output
- BDD: new scenario in `consolidate_journals.feature` — "Offset rows are generated for buy
  and sell trades"; "Re-running with same inputs does not duplicate offsets"; "Existing journal
  without offsets receives backfilled offsets on next run"
- Integration: `TestUSOffsets` class in `test_consolidate_journals_e2e.py` — buy/sell inserts
  produce offset rows; offsets not duplicated on re-run; existing journal backfilled; summary
  count includes offsets
