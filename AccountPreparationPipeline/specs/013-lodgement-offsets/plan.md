# Implementation Plan: Lodgement Deposit and Trade Offsets

**Branch**: `013-lodgement-offsets` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/013-lodgement-offsets/spec.md`

---

## Summary

For every `action=lodgement` journal entry, generate two synthetic cash companion rows: a `deposit` companion (cash-equivalent inflow at negated value, reference `{ref}-deposit`) and a `trading` companion (trade accounting offset at mirrored value, reference `{ref}-offset`). This extends the existing `OffsetGenerator` and `JournalStore.missing_offset_trades()` to cover lodgements, with idempotent deduplication and automatic backfill for historical entries. No parser changes required — Feature 012 is the foundation.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: pandas, openpyxl, Decimal (stdlib)  
**Storage**: Excel `.xlsx` journal file (read/written by `JournalStore`)  
**Testing**: pytest (unit), pytest-bdd (BDD), ruff, mypy  
**Target Platform**: Windows/Linux CLI pipeline  
**Project Type**: CLI pipeline extension (internal module change only)  
**Performance Goals**: No new performance requirements — same batch pipeline  
**Constraints**: Zero regressions; all 4 quality gates must pass  
**Scale/Scope**: 3 source files changed; ~50 new test cases

---

## Constitution Check

*GATE: Must pass before implementation.*

- [X] Virtual environment (`.venv`) initialised; dependencies in `requirements.txt` / `requirements-dev.txt`; tool config in `pyproject.toml` — no new dependencies introduced by this feature
- [X] No magic numbers or strings — `DEPOSIT_SUFFIX = "-deposit"` added to `constants.py`; all existing constants (`OFFSET_SUFFIX`, `CASH_SUB_ACCOUNT`) reused
- [X] SOLID principles applied — `OffsetGenerator` extended via new private methods (SRP preserved); no cross-module coupling added; `JournalStore` changes are isolated to two methods
- [X] All code fully type-annotated; `mypy --strict` planned as quality gate
- [X] `ruff check` + `ruff format --check` planned as quality gate
- [X] BDD Gherkin scenarios in `tests/features/consolidate_journals.feature`; pytest unit tests in `tests/unit/consolidate_journals/`
- [X] Structured logging — `consolidator.py` already logs backfill; no new log sites needed for this change; `OffsetGenerator` is a pure computation module (no logging required)

**No constitution violations. No complexity justifications required.**

---

## Project Structure

### Documentation (this feature)

```text
specs/013-lodgement-offsets/
├── plan.md              ← this file
├── spec.md              ← feature specification
├── research.md          ← design decisions (reference for implementer)
├── data-model.md        ← companion row rules and dedup key table
└── tasks.md             ← task list (created by /speckit-tasks)
```

### Source Code Changes

```text
src/modes/consolidate_journals/
├── constants.py          ← ADD: DEPOSIT_SUFFIX = "-deposit"
├── journal_store.py      ← EXTEND: _is_transaction_reference(), missing_offset_trades()
└── offset_generator.py   ← EXTEND: generate(), ADD: _make_lodgement_deposit(), _make_lodgement_trading()

tests/
├── features/
│   ├── consolidate_journals.feature            ← ADD: 3 new BDD scenarios
│   └── steps/consolidate_journals_steps.py    ← ADD: @scenario bindings, @given/@then steps
└── unit/consolidate_journals/
    ├── test_offset_generator.py                ← ADD: TestLodgementCompanions class
    └── test_journal_store.py                   ← ADD: lodgement dedup and backfill tests
```

No changes to: `hl.py`, `schema.py`, `consolidator.py`, `mode.py`.

---

## Implementation Detail

### Phase A: `constants.py`

Add after `OFFSET_SUFFIX`:

```python
DEPOSIT_SUFFIX: str = "-deposit"
```

### Phase B: `journal_store.py`

**Import change**: Add `RE_LODGEMENT, DEPOSIT_SUFFIX` to the import from `constants`.

**`_is_transaction_reference()` change**: Extend the boolean to recognise lodgement references and deposit companions:

```python
def _is_transaction_reference(reference: str) -> bool:
    return bool(
        RE_BUY.match(reference)
        or RE_SELL.match(reference)
        or RE_LODGEMENT.match(reference)
        or reference.endswith(OFFSET_SUFFIX)
        or reference.endswith(DEPOSIT_SUFFIX)
    )
```

**`missing_offset_trades()` change**: After the existing buy/sell/dividend check, add a lodgement check:

```python
def missing_offset_trades(self) -> pd.DataFrame:
    if self._df.empty:
        return self._df.iloc[0:0]

    # Existing: buy, sell, dividend without trading offset
    trade_mask = self._df["action"].isin(
        {ActionType.BUY.value, ActionType.SELL.value, ActionType.DIVIDEND.value}
    )
    existing_trading_refs: set[str] = set(
        self._df.loc[self._df["action"] == ActionType.TRADING.value, "reference"]
    )
    needs_trading_offset = trade_mask & ~self._df["reference"].apply(
        lambda ref: (str(ref) + OFFSET_SUFFIX) in existing_trading_refs
    )

    # New: lodgements missing either companion
    lodgement_mask = self._df["action"] == ActionType.LODGEMENT.value
    existing_deposit_refs: set[str] = set(
        self._df.loc[self._df["action"] == ActionType.DEPOSIT.value, "reference"]
    )
    needs_lodgement_companion = lodgement_mask & (
        ~self._df["reference"].apply(
            lambda ref: (str(ref) + OFFSET_SUFFIX) in existing_trading_refs
        )
        | ~self._df["reference"].apply(
            lambda ref: (str(ref) + DEPOSIT_SUFFIX) in existing_deposit_refs
        )
    )

    return self._df[needs_trading_offset | needs_lodgement_companion].copy()
```

### Phase C: `offset_generator.py`

**Import change**: Add `DEPOSIT_SUFFIX` to the import from `constants`; add `ActionType.DEPOSIT` (already accessible via the `ActionType` import).

**Two new private methods**:

```python
def _make_lodgement_deposit(self, event: JournalEvent) -> JournalEvent:
    return JournalEvent(
        date=event.date,
        account=event.account,
        sub_account=CASH_SUB_ACCOUNT,
        action=ActionType.DEPOSIT,
        reference=event.reference + DEPOSIT_SUFFIX,
        value=-event.value,   # Negated — FR-001
        quantity=None,        # FR-008
    )

def _make_lodgement_trading(self, event: JournalEvent) -> JournalEvent:
    return JournalEvent(
        date=event.date,
        account=event.account,
        sub_account=CASH_SUB_ACCOUNT,
        action=ActionType.TRADING,
        reference=event.reference + OFFSET_SUFFIX,
        value=event.value,    # Mirrors — FR-002 / same logic as buy/sell
        quantity=None,        # FR-008
    )
```

**`generate()` change**:

```python
def generate(self, events: list[JournalEvent]) -> list[JournalEvent]:
    result: list[JournalEvent] = []
    for e in events:
        if e.action in (ActionType.BUY, ActionType.SELL, ActionType.DIVIDEND):
            result.append(self._make_offset(e))
        elif e.action is ActionType.LODGEMENT:
            result.append(self._make_lodgement_deposit(e))
            result.append(self._make_lodgement_trading(e))
    return result
```

---

## Test Strategy

### Unit tests: `test_offset_generator.py` — new `TestLodgementCompanions` class

| Test | Assertion |
|------|-----------|
| `test_lodgement_produces_two_companions` | `len(generate([lodgement])) == 2` |
| `test_lodgement_deposit_action` | companion[0].action == DEPOSIT |
| `test_lodgement_deposit_sub_account_is_cash` | companion[0].sub_account == "Cash" |
| `test_lodgement_deposit_reference_has_deposit_suffix` | companion[0].reference == "L003538235-deposit" |
| `test_lodgement_deposit_value_is_negated` | lodgement -2288.89 → deposit +2288.89 |
| `test_lodgement_deposit_quantity_is_none` | companion[0].quantity is None |
| `test_lodgement_trading_action` | companion[1].action == TRADING |
| `test_lodgement_trading_sub_account_is_cash` | companion[1].sub_account == "Cash" |
| `test_lodgement_trading_reference_has_offset_suffix` | companion[1].reference == "L003538235-offset" |
| `test_lodgement_trading_value_mirrors_lodgement` | companion[1].value == Decimal("-2288.89") |
| `test_lodgement_trading_quantity_is_none` | companion[1].quantity is None |
| `test_lodgement_date_account_inherited` | both companions inherit date and account |
| `test_two_lodgements_produce_four_companions` | `len(generate([l1, l2])) == 4` |
| `test_mixed_events_lodgement_and_buy` | buy produces 1 offset; lodgement produces 2; total = 3 |
| `test_generate_from_df_lodgement` | `generate_from_df` with lodgement DataFrame produces 2 results |

### Unit tests: `test_journal_store.py` — new lodgement methods

| Test | Assertion |
|------|-----------|
| `test_lodgement_reference_is_transaction_reference` | `_is_transaction_reference("L003538235") is True` |
| `test_deposit_suffix_is_transaction_reference` | `_is_transaction_reference("L003538235-deposit") is True` |
| `test_lodgement_dedup_by_date_and_reference` | re-merging same lodgement event inserts 1, merges 1 |
| `test_lodgement_missing_both_companions` | lodgement without both companions → returned by `missing_offset_trades()` |
| `test_lodgement_missing_deposit_companion_only` | returns lodgement when only trading companion present |
| `test_lodgement_missing_trading_companion_only` | returns lodgement when only deposit companion present |
| `test_lodgement_with_both_companions_not_missing` | not returned when both companions present |
| `test_two_same_date_same_value_lodgements_both_kept` | verifies primary key dedup (regression for latent bug) |

### BDD scenarios: `consolidate_journals.feature` — 3 new scenarios under Feature 013 heading

```gherkin
# ─── Feature 013: Lodgement Deposit and Trading Companions ───

Scenario: Lodgement generates a deposit companion row
  Given a valid HL CSV file with lodgement rows
  And no existing consolidated journal
  When I run consolidate_journals with method HL and account "Test ISA"
  Then the exit code is 0
  And the journal contains a row with action "deposit" and reference "L003538235-deposit"

Scenario: Lodgement generates a trading companion row
  Given a valid HL CSV file with lodgement rows
  And no existing consolidated journal
  When I run consolidate_journals with method HL and account "Test ISA"
  Then the exit code is 0
  And the journal contains a row with action "trading" and reference "L003538235-offset"

Scenario: Re-running consolidation does not duplicate lodgement companions
  Given a valid HL CSV file with lodgement rows
  And no existing consolidated journal
  When I run consolidate_journals with method HL and account "Test ISA"
  And I run consolidate_journals with method HL and account "Test ISA" again
  Then the exit code is 0
  And the journal contains exactly 6 rows
```

---

## Constitution Check (Post-Design)

All constitution principles remain satisfied:
- No new constants outside `constants.py`
- `OffsetGenerator` remains a pure computation class (no I/O, no logging)
- Both new private methods have a single responsibility (one companion type each)
- `missing_offset_trades()` is extended in-place; no new abstraction layer needed
- Full type annotations on all new methods; `mypy --strict` will be verified
- BDD scenarios cover idempotency and the primary companion generation path

---

## Complexity Tracking

*No constitution violations requiring justification.*
