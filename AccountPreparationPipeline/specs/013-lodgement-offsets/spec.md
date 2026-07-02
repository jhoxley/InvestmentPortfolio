# Feature Specification: Lodgement Deposit and Trade Offsets

**Feature Branch**: `013-lodgement-offsets`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "Extend the handling of 'Lodgement' actions previously added to incorporate correct additional, offsetting line-items. For each journal entry of action=lodgement there needs to be two extra rows generated. Both new rows inherit the same date & account values. The first new row is a 'deposit' action mapped to the 'Cash' sub-account. The value of this line is the same as the lodgement but negative (x -1). The second additional line should follow the same logic as the 'trading' action for buy/sell actions and create an appropriate offset assuming a 'lodgement' action is just a special form of a 'buy' action."

## Overview

When an HL capital account journal is processed, lodgement transactions (in-specie security transfers identified by Feature 012) are recorded as single journal entries. However, a lodgement also represents a cash-equivalent event — securities arrive in the portfolio without a direct cash payment, which must be reflected in the cash and trade accounting. This feature adds two companion rows to every lodgement entry so that the journal's cash balance and trade offset accounting remain consistent with how outright purchases (buys) are treated.

## User Scenarios & Testing

### User Story 1 — Lodgement Entries Generate Two Offsetting Rows (Priority: P1)

When processing a journal that contains one or more lodgement entries, the system automatically creates two companion rows for each lodgement: a deposit row representing the cash-equivalent inflow, and a trading row representing the trade accounting offset (treating the lodgement as equivalent to a buy transaction).

**Why this priority**: Without these companion rows, the journal's cash sub-account does not balance for lodgement events, and downstream capital reports cannot correctly separate cash deposits from in-specie acquisitions. This is the only functional gap remaining from Feature 012.

**Independent Test**: Process a journal fragment containing exactly one lodgement entry. Verify: the output journal contains 3 rows total (1 lodgement + 1 deposit + 1 trading), the deposit row has `action=deposit`, `sub_account=Cash`, and a value that is the negation of the lodgement value; the trading row has `action=trading` and a reference in the standard offset format.

**Acceptance Scenarios**:

1. **Given** a journal with a single lodgement entry of value −£2,288.89, **When** `consolidate_journals` is run, **Then** the journal contains a deposit row with `action=deposit`, `sub_account=Cash`, `value=+£2,288.89` sharing the same date and account as the lodgement.

2. **Given** the same journal with the single lodgement entry of value −£2,288.89, **When** `consolidate_journals` is run, **Then** the journal contains a trading row with `action=trading`, `sub_account=Cash`, a value equal to the negation of the lodgement value, and a reference derived from the lodgement reference in the standard offset format (e.g., `L003538235-offset`).

3. **Given** a journal with two lodgement entries, **When** `consolidate_journals` is run, **Then** the journal contains 6 rows total (2 lodgements + 2 deposit rows + 2 trading rows).

4. **Given** a journal containing a mix of buy, sell, deposit, and lodgement entries, **When** `consolidate_journals` is run, **Then** all row types are present and each lodgement has exactly one companion deposit row and one companion trading row; existing buy/sell offset behaviour is unaffected.

5. **Given** a journal already containing correct lodgement companion rows, **When** `consolidate_journals` is re-run with the same input, **Then** no duplicate deposit or trading rows are created (idempotent — zero new rows inserted on a second run).

6. **Given** a journal where a lodgement has a positive value (unusual but possible edge case), **When** `consolidate_journals` is run, **Then** the companion deposit row has a negative value (still negated) and the trading row is generated consistently.

---

### Edge Cases

- What happens when the lodgement value is zero? Companion rows are still generated with value zero — no special handling needed.
- What happens on a re-run when companion rows already exist? The deduplication logic that prevents duplicate buy/sell offset rows applies equally to lodgement companion rows — no duplicates are created.
- What if a lodgement entry exists in the journal from a run before this feature was deployed? The system detects the missing companion rows and backfills them on the next run, consistent with how buy/sell offset backfilling works.
- What happens with the `quantity` field on companion rows? Both the deposit companion and the trading companion have no meaningful quantity — the quantity field is absent/null, consistent with how deposit and trading offset rows for buy/sell are stored.

## Requirements

### Functional Requirements

- **FR-001**: For every lodgement entry in the journal, the system MUST generate a companion deposit row with `action=deposit`, `sub_account=Cash`, the same `date` and `account` as the lodgement, and a `value` equal to the lodgement value multiplied by negative one.
- **FR-002**: For every lodgement entry in the journal, the system MUST generate a companion trading row with `action=trading`, `sub_account=Cash`, the same `date` and `account` as the lodgement, a `value` equal to the lodgement value (mirroring the original — same sign, consistent with how buy/sell trade offsets are generated), and a `reference` derived from the lodgement's reference by appending the standard offset suffix (e.g., `L003538235-offset`).
- **FR-003**: The deposit companion row MUST use a reference derived from the lodgement's reference by appending a `-deposit` suffix (e.g., `L003538235-deposit`), to uniquely identify it and distinguish it from both the lodgement entry and the trading companion.
- **FR-004**: Both companion rows MUST be generated in the same processing pass that handles buy/sell trade offsets, ensuring consistent ordering in the journal.
- **FR-005**: The companion row generation MUST be idempotent — re-running `consolidate_journals` with the same inputs MUST NOT create duplicate companion rows.
- **FR-006**: Companion rows MUST be backfilled for any lodgement entries already present in the journal that were written before this feature was deployed.
- **FR-007**: No existing journal entries (buy, sell, deposit, income, dividend, fee, trading) MUST be modified or removed by this change.
- **FR-008**: The `quantity` field on both companion rows MUST be absent (null/empty), consistent with how cash and trading offset rows are stored for other action types.

### Key Entities

- **Lodgement entry**: A journal row with `action=lodgement`, representing an in-specie security transfer. Has a date, account, sub_account (security name), reference, value, and optional quantity.
- **Deposit companion row**: A new row generated per lodgement. Has `action=deposit`, `sub_account=Cash`, value = lodgement value × −1 (negated), same date/account, reference = `{lodgement_reference}-deposit`, no quantity.
- **Trading companion row**: A new row generated per lodgement. Has `action=trading`, `sub_account=Cash`, value = lodgement value (mirrors — same sign as lodgement), same date/account, reference = `{lodgement_reference}-offset`, no quantity.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every lodgement entry in any processed journal is accompanied by exactly 2 companion rows — 0 lodgement entries have missing companions after processing.
- **SC-002**: Re-running `consolidate_journals` against a journal that already contains correct companion rows results in 0 new rows inserted (idempotent).
- **SC-003**: The cash sub-account balance in the journal correctly reflects lodgement events — the sum of (lodgement value + deposit companion value) is zero for each lodgement pair.
- **SC-004**: The existing passing test suite continues to pass in full — 0 regressions introduced in buy/sell/deposit/dividend offset behaviour.
- **SC-005**: A journal containing historical lodgement entries (written before this feature) receives correctly backfilled companion rows on the first post-deployment run.

## Assumptions

- Lodgement companion rows are generated in the same pipeline step as buy/sell trade offsets (`consolidate_journals`), not in a separate processing mode.
- The deposit companion row uses a `{reference}-deposit` suffix (e.g., `L003538235-deposit`) rather than the bare lodgement reference, to avoid a deduplication collision — if both the lodgement and its deposit companion shared the same reference, the journal store's primary-key dedup would be unable to distinguish them.
- The trading companion row uses the standard `{reference}-offset` suffix format, consistent with buy/sell offset references (`B12345-offset`, `S67890-offset`).
- The deposit companion value is the lodgement value × −1 (negated), so that `lodgement.value + deposit.value = 0` for each pair (SC-003). The trading companion value mirrors the lodgement value (same sign), consistent with how buy/sell trading offsets mirror their originating trade.
- Idempotency is enforced by checking whether a companion row with the matching reference already exists in the journal before inserting, using the same deduplication approach applied to buy/sell offsets.
- No changes are required to the lodgement parser or the `ActionType` enumeration — Feature 012 is the foundation and is considered complete.
- Lodgements are assumed to always appear in capital account journals; income account journals do not contain lodgements and are unaffected.
