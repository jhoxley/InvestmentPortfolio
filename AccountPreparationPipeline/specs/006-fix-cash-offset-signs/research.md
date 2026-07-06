# Research: Fix Cash Offset Signs

**Feature**: 006-fix-cash-offset-signs
**Date**: 2026-06-10

---

## Root Cause Analysis

### Decision: HL CSV sign convention for buy and sell values

- **Decision**: HL CSV export files store buy event values as **negative** (cash outflow — you pay
  money to purchase) and sell event values as **positive** (cash inflow — you receive proceeds).
- **Rationale**: Confirmed by direct inspection of real SIPP and ISA journal XLSX files produced
  from actual HL CSV exports. Representative samples:
  - SIPP buy: `reference=B915160961, value=-1031.25` (negative)
  - SIPP sell: `reference=S872695061, value=81.87` (positive)
  - ISA buy: `reference=B393848012, value=-200.0` (negative)
  - ISA sell: `reference=S772615533, value=67.9` (positive)
- **Alternatives considered**: Positive buy / negative sell (assumed by feature 004 test fixtures
  and `valid_hl_simple.csv`). Rejected because real data contradicts this assumption.

### Decision: Offset generator formula

- **Decision**: Change `_make_offset` from `value = -event.value` to `value = event.value`
  (mirror the trade's value directly, no sign inversion). Same change applies to `quantity`.
- **Rationale**: Because HL encodes the cash direction in the value sign itself (negative = outflow,
  positive = inflow), the correct offset simply mirrors that sign. The previous formula negated
  it, thereby reversing the cash direction — a buy appeared to add cash and a sell appeared to
  remove it.
- **Alternatives considered**: Conditional logic (`if action == BUY: negate, else: keep`). Rejected
  because a simple mirror is sufficient and avoids conditional branching on sign. The HL data
  already encodes direction.

### Decision: Test fixture sign convention

- **Decision**: Update all test fixtures for buy events to use negative values (e.g., `"-1000.00"`)
  and sell events to use positive values (e.g., `"75.00"`), matching real HL CSV convention.
- **Rationale**: The existing test fixtures in `test_offset_generator.py` and `valid_hl_simple.csv`
  used the wrong sign convention (positive buys, negative sells). Tests were passing while
  asserting the wrong behaviour. Fixtures must use real-world sign convention so tests are
  meaningful.
- **Alternatives considered**: Keeping fixtures with wrong signs and inverting expectations.
  Rejected — tests must reflect the real data contract.

### Decision: Scope of changes

- **Decision**: Three files require changes: `offset_generator.py` (source), 
  `test_offset_generator.py` (unit tests), `valid_hl_simple.csv` (test data). No other files need
  modification.
- **Rationale**:
  - BDD consolidate_journals scenarios only assert trading row COUNT, not values — no step changes.
  - `test_consolidator.py` only asserts `events_inserted` count — no changes.
  - `create_ledger` engine is sign-agnostic for `trading` action — no changes.
  - `test_create_ledger_e2e.py` uses `action="deposit"` for Cash rows — no changes needed.
  - `test_engine.py` `test_invariant_holds_for_trading_offset` uses `value=1000.0` for the
    trading row — this is semantically wrong (a buy offset should be negative) but the test only
    checks the mathematical invariant which holds regardless of sign. Updated for correctness.
- **Alternatives considered**: Broader changes to BDD steps or integration tests. Rejected — those
  tests do not assert offset values and will pass unchanged.

### Decision: Self-healing re-run behaviour (no code changes needed)

- **Decision**: Journals already produced by the buggy code (wrong-sign offsets) will self-correct
  on the next `consolidate_journals` run. No additional migration code or manual intervention is
  required.
- **Rationale**: The existing journal store merge/deduplication logic matches rows by reference.
  An existing wrong-sign offset row (`B001-offset` with `value=+1000`) will be matched by the
  new correct-sign offset (`B001-offset` with `value=-1000`) during the merge, and the existing
  row will be updated (or it will be re-inserted as correct). The idempotency mechanism already
  handles this case.
- **Alternatives considered**: Explicit migration step or a one-time correction script. Rejected
  — unnecessary complexity when the existing mechanism already handles it.
