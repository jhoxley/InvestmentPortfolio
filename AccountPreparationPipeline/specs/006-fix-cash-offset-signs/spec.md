# Feature Specification: Fix Cash Offset Signs

**Feature Branch**: `006-fix-cash-offset-signs`
**Created**: 2026-06-10
**Status**: Draft
**Input**: User description: "There was a mistake in the prior feature 004 of creating cash offsets
for trades that needs to be fixed. The sign of the buy and sell offset needs to be inverted: a
'buy' trade reduces the cash value (transaction value and quantity are negative) whereas a 'sell'
trade increases the cash value (transaction value and quantity are positive). Make this fix to the
core logic and amend the test cases to reflect this correctly."

## Clarifications

### Session 2026-06-10

- Q: What is the actual HL sign convention for buy and sell values in the exported CSV files?
  → A: Real HL exports store buy event values as **negative** (money leaves the cash account when
  buying) and sell event values as **positive** (money enters the cash account when selling). This
  was confirmed by inspecting real SIPP and ISA journal outputs: buy rows have `value < 0`, sell
  rows have `value > 0`.

- Q: What sign should the Cash offset row carry for each trade type?
  → A: The Cash offset row should carry the **same sign** as the originating trade's value —
  because the trade value already encodes the correct cash direction. Buying (negative trade value)
  reduces cash; selling (positive trade value) increases cash. The offset mirrors this.

- Q: When a correct-sign offset conflicts with an existing wrong-sign offset row (same reference,
  different value), what should happen on re-run?
  → A: **Update in place** — if a `*-offset` row already exists with the same reference but wrong
  `value`/`quantity`, overwrite it with the corrected values. The journal store must actively
  replace stale offsets, not merely skip them. This requires implementation changes to the journal
  store beyond the one-line formula fix.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Buy Trade Produces a Negative Cash Offset (Priority: P1)

A user who has made investment purchases in their account runs `consolidate_journals` and then
`create_ledger`. When they look at the Cash position in the ledger, they can see that each buy
event causes the running cash balance to decrease — reflecting that cash was spent to fund the
purchase.

**Why this priority**: The Cash position in the ledger is the primary way a user tracks available
funds. A buy trade should consume cash. If the offset carries the wrong sign, the Cash balance
increases on every purchase — which is factually incorrect and misleads the user into thinking
more money is available than actually exists.

**Independent Test**: Run `consolidate_journals` against a journal fragment containing a single
buy event with value `−£1 000.00` (HL convention: buy values are negative). Open the output
journal and verify that the synthetic Cash offset row has `value = −1 000.00` and
`quantity = −1 000.00`. Then run `create_ledger` on the journal and verify that the Cash
`Account Value` decreases by £1 000.00 on the date of the buy.

**Acceptance Scenarios**:

1. **Given** a journal fragment containing a buy event (e.g. reference B12345,
   value = `−1 000.00`, date 2024-03-15),
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "B12345-offset"`, `value = −1 000.00`,
   `quantity = −1 000.00`, and `date = 2024-03-15`.

2. **Given** a journal containing a buy offset row with `value = −1 000.00`,
   **When** `create_ledger` is run,
   **Then** the Cash position's `Transaction Value` for that row equals `−1 000.00`
   and the Cash `Account Value` on that row equals the prior Cash `Account Value` minus
   £1 000.00 (i.e. the balance decreases).

---

### User Story 2 — Sell Trade Produces a Positive Cash Offset (Priority: P1)

A user who has sold investments runs `consolidate_journals` and then `create_ledger`. When they
look at the Cash position in the ledger, they can see that each sell event causes the running
cash balance to increase — reflecting that proceeds from the sale were received into the cash
account.

**Why this priority**: Equal priority to US1. A sell trade should add cash. If the offset carries
the wrong sign, the Cash balance decreases on every sale — the opposite of economic reality.

**Independent Test**: Run `consolidate_journals` against a journal fragment containing a single
sell event with value `+£500.00` (HL convention: sell values are positive). Open the output
journal and verify that the synthetic Cash offset row has `value = +500.00` and
`quantity = +500.00`. Then run `create_ledger` and verify that the Cash `Account Value`
increases by £500.00 on the date of the sell.

**Acceptance Scenarios**:

1. **Given** a journal fragment containing a sell event (e.g. reference S67890,
   value = `+500.00`, date 2024-04-01),
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "S67890-offset"`, `value = +500.00`,
   `quantity = +500.00`, and `date = 2024-04-01`.

2. **Given** a journal containing a sell offset row with `value = +500.00`,
   **When** `create_ledger` is run,
   **Then** the Cash position's `Transaction Value` for that row equals `+500.00`
   and the Cash `Account Value` on that row equals the prior Cash `Account Value` plus
   £500.00 (i.e. the balance increases).

---

### User Story 3 — End-to-End Cash Balance Coherence Across Buy and Sell (Priority: P2)

A user runs `consolidate_journals` against a history that includes both buy and sell events
alongside explicit cash deposits. When they open the resulting ledger, the Cash position's
running `Account Value` correctly reflects all three contributions: deposits add cash,
purchases reduce it, and sales add it back. The running balance is coherent and reconcilable.

**Why this priority**: US1 and US2 verify individual offset signs in isolation. This story
verifies the combined picture — that deposits, buys, and sells all interact correctly in a
single coherent Cash balance. Without this, individual sign fixes might be correct in isolation
but still produce an incorrect net balance.

**Independent Test**: Provide a journal with one deposit (+£2 000), one buy (−£1 000),
and one sell (+£300). Run `create_ledger`. Verify the final Cash `Account Value` equals
`+2 000 − 1 000 + 300 = +1 300`.

**Acceptance Scenarios**:

1. **Given** a journal with a deposit of `+£2 000`, a buy of `−£1 000`, and a sell of `+£300`
   on the Cash sub-account (via their respective offset rows),
   **When** `create_ledger` is run,
   **Then** the final Cash `Account Value` equals `+1 300.00`.

2. **Given** any journal produced by the corrected `consolidate_journals`,
   **When** `create_ledger` is run on it,
   **Then** the Cash `Account Value` and `Transaction Value` columns satisfy the standard
   ledger invariant: `Account Value[i] = Account Value[i−1] + Transaction Value[i]` for every
   row in the Cash position.

---

### Edge Cases

- What if a journal was produced by the buggy version of feature 004 (offsets with wrong signs)?
  Re-running `consolidate_journals` after this fix will update existing wrong-sign offsets in
  place (see FR-005). The journal self-corrects on the next run. Note: the existing merge logic
  skips rows whose reference already exists — FR-005 requires an explicit update path in the
  journal store for offset rows whose value has changed.
- What if a buy trade has an unexpectedly positive value in the CSV (data quality issue)?
  The offset will mirror that positive value — the offset always mirrors the trade's stored value
  without additional sign manipulation.
- What if a sell trade has an unexpectedly negative value?
  Same as above — mirrored as-is. The correctness of the offset depends on the upstream CSV
  data quality; this feature makes no attempt to validate or correct upstream sign errors.
- What about the offset `quantity` field? It always equals the offset `value` (Cash quantity
  mirrors Cash value). The same sign correction applies to quantity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For each buy event in the journal, the synthetic Cash offset row generated by
  `consolidate_journals` MUST have `value` equal to the buy event's `value` (same sign, same
  magnitude). Given that HL exports store buy values as negative, this results in a negative
  offset — correctly representing a cash outflow.

- **FR-002**: For each sell event in the journal, the synthetic Cash offset row generated by
  `consolidate_journals` MUST have `value` equal to the sell event's `value` (same sign, same
  magnitude). Given that HL exports store sell values as positive, this results in a positive
  offset — correctly representing a cash inflow.

- **FR-003**: The offset `quantity` MUST equal the offset `value` (the existing rule that Cash
  quantity mirrors Cash value is unchanged).

- **FR-004**: All other offset fields (`date`, `account`, `sub_account`, `action`, `reference`)
  MUST remain unchanged from feature 004's contract — only the `value` and `quantity` signs
  are corrected.

- **FR-005**: When `consolidate_journals` is re-run against a journal that already contains
  wrong-sign offsets (produced by the buggy feature 004 implementation), the corrected offsets
  MUST replace the old ones in place. Specifically: if an offset row with reference `<ref>-offset`
  already exists but its `value` or `quantity` differs from the correct (mirrored) value, the
  journal store MUST update that row's `value` and `quantity` to the correct values. The journal
  MUST self-correct on the next run without requiring manual intervention. This requires the
  journal store to implement an explicit update-in-place path for offset rows — the existing
  insert-only merge logic is insufficient.

- **FR-006**: All test fixtures, CSV test data files, and BDD scenarios that asserted the
  old (incorrect) offset signs MUST be updated to assert the correct signs. No test may pass
  while testing for the wrong sign.

### Key Entities

- **Cash Offset Row**: A synthetic journal row with `sub_account = "Cash"` and
  `action = "trading"`, generated for each buy/sell trade. Its `value` and `quantity` mirror
  the originating trade's `value` (same sign), representing the cash movement that accompanies
  the trade.
- **Buy Event**: A trade with `action = "buy"`. In HL exports the `value` column is negative
  (cash paid out). The corresponding Cash offset therefore also carries a negative value.
- **Sell Event**: A trade with `action = "sell"`. In HL exports the `value` column is positive
  (cash received). The corresponding Cash offset therefore also carries a positive value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every buy event in any journal produced by `consolidate_journals`, the
  corresponding Cash offset row's `value` is less than zero (negative cash outflow). Zero
  failures across the full test suite.

- **SC-002**: For every sell event in any journal produced by `consolidate_journals`, the
  corresponding Cash offset row's `value` is greater than zero (positive cash inflow). Zero
  failures across the full test suite.

- **SC-003**: Running `consolidate_journals` followed by `create_ledger` against a journal
  containing deposits, buys, and sells produces a Cash `Account Value` that equals the
  arithmetic sum of all Cash transactions (deposits + sell proceeds − buy costs). The
  computed balance matches the expected value exactly (no rounding errors beyond £0.01).

- **SC-004**: Re-running `consolidate_journals` on a journal that was produced by the buggy
  feature 004 implementation results in all wrong-sign offsets being replaced by correct-sign
  offsets. After re-run, the journal contains no positive-valued buy offsets and no
  negative-valued sell offsets.

- **SC-005**: All existing tests pass after the fix. No new test failures are introduced
  outside of the intentionally updated offset-sign assertions.

## Assumptions

- The HL CSV export format consistently stores buy values as negative and sell values as
  positive. This is confirmed by inspection of real SIPP and ISA exports and is treated as
  the authoritative sign convention for this codebase.
- The core formula fix is a one-character change to the offset generator (`value = event.value`
  instead of `value = -event.value`). Additionally, FR-005 requires changes to the journal store's
  merge/update logic to support updating existing offset rows whose values are stale. No changes
  are required to `create_ledger`, the mode CLI interface, or any other pipeline mode.
- Test fixtures and CSV test data that assumed the old (wrong) sign convention must be
  corrected as part of this fix. Tests passing against incorrect data are not acceptable.
- Journals already in production (e.g., `HL_SIPP_Journal.xlsx`, `HL_ISA.xlsx`) contain
  wrong-sign offsets. These will be corrected automatically when `consolidate_journals` is
  re-run after the fix is deployed (covered by FR-005).
- No change is needed to the offset `reference` format (`<trade_ref>-offset`) or any other
  field. Only `value` and `quantity` signs change.
