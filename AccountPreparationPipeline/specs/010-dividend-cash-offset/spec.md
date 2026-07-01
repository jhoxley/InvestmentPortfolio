# Feature Specification: Dividend Cash Offset Entries

**Feature Branch**: `010-dividend-cash-offset`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "A variation on the 004-trade-cash-offsets and 006-fix-cash-offset-signs feature is required for the income stream. Extend the logic on creating a cash offset to include line items that are of action 'dividend'; the 'trading' action line that pairs up with a 'dividend' line should retain the same value/quantity sign. If we get a ST DIV dividend of 64.71 then the cash balance of the income account should increase by 64.71 as well. A testable assertion is that the income account ledger should not yield a negative cash account value: dividends increase the available cash, management fee and transfer lines decrease it (latter to the capital account). Reuse existing code and logic where possible, just extend 'buy' and 'sell' actions to handle 'dividend'."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Dividend Event Generates a Same-Sign Cash Offset (Priority: P1)

A user runs `consolidate_journals` against an HL income account export. Each received dividend
payment should appear twice in the output journal: once as the `dividend` event (the income
received into the named holding's sub-account) and once as a synthetic `trading` row representing
the equal cash movement into the Cash sub-account. When the user subsequently runs `create_ledger`,
the Cash position in the income account ledger increases on every dividend date.

**Why this priority**: Without cash offsets for dividend events, the income account ledger has
no Cash position at all — every dividend increases the nominal holding sub-account value but the
available cash (which should be swept or reinvested) is invisible. This is the foundational
correctness requirement that all subsequent income-stream analysis depends on.

**Independent Test**: Run `consolidate_journals` with an HL income CSV containing a single ST DIV
row with value `+64.71`. Open the output journal and confirm it contains a synthetic row with
`sub_account = "Cash"`, `action = "trading"`, `reference = "ST DIV-offset"`, `value = +64.71`,
`quantity = +64.71` on the same date. Then run `create_ledger` and confirm the Cash
`Account Value` increases by £64.71 on that date.

**Acceptance Scenarios**:

1. **Given** an HL income CSV containing a ST DIV event (value `+64.71`, date 2026-03-31),
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "ST DIV-offset"`, `value = +64.71`,
   `quantity = +64.71`, and `date = 2026-03-31`.

2. **Given** an HL income CSV containing an OVR CR (overseas dividend) event (value `+257.69`),
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "OVR CR-offset"`, `value = +257.69`,
   `quantity = +257.69`.

3. **Given** an HL income CSV containing UTC CR, LOYALTYU, UTO CR, or LOYALTYC dividend events,
   **When** `consolidate_journals` is run,
   **Then** each dividend event generates a corresponding synthetic Cash offset row with the
   same positive value, following the pattern `<reference>-offset`.

4. **Given** an income CSV containing only non-dividend events (deposit, fee, income, withdrawal),
   **When** `consolidate_journals` is run,
   **Then** no synthetic offset rows are generated for those events (offset generation remains
   exclusive to `buy`, `sell`, and `dividend` actions).

---

### User Story 2 — Income Account Cash Balance is Non-Negative End-to-End (Priority: P1)

A user runs the full pipeline (`consolidate_journals` then `create_ledger`) against the historical
HL ISA or SIPP Income Account. When they inspect the Cash sub-account in the resulting ledger, the
running `Account Value` is non-negative at every date — dividends received build up the cash
balance, and any management fees or transfer-to-capital-account events reduce it, but never below
zero in a correctly ordered real account history.

**Why this priority**: Equal to US1 — this is the end-to-end correctness assertion the user
explicitly requested. A negative Cash balance in the income account ledger would indicate a sign
error in offset generation (e.g., dividends being applied as negative cash rather than positive).
The non-negative balance invariant is the primary observable proof that the feature works correctly.

**Independent Test**: Run `consolidate_journals` then `create_ledger` against the HL ISA Income
Account historical files. Filter the ledger to the Cash sub-account rows. Confirm that every row's
`Account Value` is greater than or equal to zero.

**Acceptance Scenarios**:

1. **Given** a consolidated income account journal containing dividend, fee, and transfer events
   (with their respective offsets),
   **When** `create_ledger` is run,
   **Then** the Cash sub-account `Account Value` is ≥ 0 at every date in the ledger output.

2. **Given** a journal with a single dividend event (value `+64.71`) and no prior Cash balance,
   **When** `create_ledger` is run,
   **Then** the Cash `Account Value` after the dividend date equals `+64.71` (the dividend
   offset is the opening Cash entry).

3. **Given** a journal with a dividend event (`+64.71`) followed by a management fee event
   (`−10.00`, represented via its existing `income` or `fee` action offset if applicable),
   **When** `create_ledger` is run,
   **Then** the Cash `Account Value` after the fee date equals `+54.71` — reflecting that
   dividends increase and fees decrease the balance.

---

### User Story 3 — Idempotency: Re-Run Does Not Duplicate Dividend Offsets (Priority: P2)

A user runs `consolidate_journals` a second time with the same income account inputs. Because
dividend offset rows carry a unique reference derived from the original dividend reference, re-running
does not create duplicate offset rows in the journal. This is the same deduplication guarantee
that already holds for buy and sell offsets.

**Why this priority**: The pipeline is expected to be re-runnable without side effects. Duplicated
offset rows would inflate the apparent Cash balance and break the correctness assertion in US2.

**Independent Test**: Run `consolidate_journals` twice with identical income CSV inputs. Confirm
that the journal after the second run contains the same number of rows as after the first run —
no dividend offset row is duplicated.

**Acceptance Scenarios**:

1. **Given** a journal already containing dividend events and their corresponding Cash offset rows,
   **When** `consolidate_journals` is run again with the same input files,
   **Then** the count of `trading` rows in the journal is unchanged and the success summary
   reports zero events inserted.

2. **Given** a journal containing existing dividend offsets, and new input files with additional
   dividend events not yet in the journal,
   **When** `consolidate_journals` is run,
   **Then** only the new dividend offsets are inserted; existing offsets are not duplicated.

---

### Edge Cases

- A dividend event with a zero value (£0.00) — the offset row is still generated (`value = 0`,
  `quantity = 0`), preserving the 1:1 symmetry with the originating event.
- Multiple dividend events sharing the same `reference` (e.g., two "ST DIV" rows on different
  dates) — each generates an independent offset row, distinguished by date. The deduplication
  key is `date + reference`, so same-date dividends with identical references may collapse to a
  single offset row. This is noted as an accepted limitation in the Assumptions section.
- A dividend event added to a journal that already contains other action types (buy, sell, deposit)
  — only the dividend events are affected by this feature; buy/sell offsets are unchanged.
- What sign should the dividend offset carry? Dividend income in HL exports is always positive
  (money received into the account). The offset mirrors this positive value — cash increases.
  Unlike feature 004 (which negated the value) and feature 006 (which corrected to same-sign),
  the same-sign rule from feature 006 applies directly to dividends and produces the correct
  result with no additional sign logic.
- A historical income account journal processed before this feature is deployed — the backfill
  mechanism (inherited from feature 004) will generate missing dividend offset rows on the next
  run, exactly as it does for missing buy/sell offsets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The offset generation step in `consolidate_journals` MUST be extended to treat
  `dividend` events identically to `buy` and `sell` events: for every `dividend` event in the
  journal that does not already have a corresponding offset row (identified by the absence of a
  row with `reference = <dividend-ref>-offset`), a synthetic Cash offset row MUST be generated
  and inserted into the journal.

- **FR-002**: The synthetic offset row generated for a `dividend` event MUST carry `value` equal
  to the dividend event's `value` (same sign, same magnitude). Since HL exports record dividend
  receipts as positive values, the offset value is positive — representing a cash inflow into the
  income account's Cash sub-account.

- **FR-003**: The dividend offset `quantity` MUST equal the dividend offset `value`, consistent
  with the existing rule for buy/sell offsets (Cash quantity mirrors Cash value).

- **FR-004**: All other fields of the dividend offset row MUST follow the same contract as
  buy/sell offsets:
  - `date`: same as the originating dividend event's date
  - `account`: same as the originating dividend event's account
  - `sub_account`: the literal string `"Cash"`
  - `action`: the literal string `"trading"`
  - `reference`: the dividend event's reference with the literal suffix `"-offset"` appended
    (e.g. `"ST DIV"` → `"ST DIV-offset"`, `"OVR CR"` → `"OVR CR-offset"`)

- **FR-005**: The offset generation logic MUST NOT generate offset rows for `deposit`, `income`,
  `fee`, `withdrawal`, or `trading` events. Only `buy`, `sell`, and `dividend` actions trigger
  offset generation.

- **FR-006**: The backfill mechanism inherited from feature 004 MUST apply to dividend events:
  on each run, the system MUST scan all `dividend` rows in the journal and generate any missing
  offset rows, including for `dividend` events that were present in the journal before this
  feature was deployed.

- **FR-007**: The dividend offset rows MUST be subject to the same deduplication logic as all
  other journal events. A re-run with identical inputs MUST NOT produce duplicate dividend
  offset rows.

- **FR-008**: No changes to the `create_ledger` mode, the journal column schema, or the CLI
  interface are required. The `trading` action type is already recognised by `create_ledger` and
  handled correctly.

### Key Entities

- **Dividend Event**: A journal row with `action = "dividend"`. In HL income account exports
  the `value` column is positive (cash received into the account). The corresponding Cash offset
  therefore also carries a positive value.
- **Cash Offset Row (Dividend)**: A synthetic journal row with `sub_account = "Cash"` and
  `action = "trading"`, generated for each dividend event. Its `value` and `quantity` mirror
  the originating dividend's `value` (same sign — positive). Structurally identical to the Cash
  offset rows generated for buy and sell events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every `dividend` event in any journal produced by `consolidate_journals`,
  exactly one corresponding synthetic offset row exists with `sub_account = "Cash"`,
  `action = "trading"`, and `reference = <dividend-ref>-offset`. The count of dividend offset
  rows equals the count of dividend rows in the journal (subject to the same-date same-reference
  edge case noted in Assumptions).

- **SC-002**: The `value` and `quantity` of every dividend offset row are positive (matching the
  positive value of the originating dividend event), verifiable across the full historical HL
  Income Account dataset.

- **SC-003**: Running `consolidate_journals` then `create_ledger` against the full historical HL
  ISA Income Account produces a Cash `Account Value` that is ≥ 0 at every date in the output.
  Zero rows with a negative Cash balance.

- **SC-004**: Running `consolidate_journals` twice in succession with identical income account
  inputs produces a journal with the same row count as a single run — no dividend offset row
  is duplicated (idempotency preserved).

- **SC-005**: All pre-existing buy/sell offset tests continue to pass unchanged after the feature
  is implemented. The change is purely additive — no existing offset behaviour is altered.

## Assumptions

- The sign convention for dividend events in HL income account exports is always positive
  (money received). The offset value therefore mirrors this — it is also positive — and no
  sign inversion is required. This contrasts with the original (wrong) feature 004 behaviour
  but is consistent with the corrected feature 006 same-sign rule.
- The implementation change is limited to the list of action types that trigger offset generation
  (adding `"dividend"` alongside `"buy"` and `"sell"`). No changes to the offset construction
  logic, journal store, deduplication mechanism, or `create_ledger` are expected.
- Dividend references in HL exports are categorical rather than unique per transaction (e.g.,
  all UK equity dividends share the reference `"ST DIV"`). Where two dividend events share
  both the same `reference` and the same `date`, their offset rows will share the same
  deduplication key (`date + "ST DIV-offset"`), and only one offset row will survive the merge.
  This is an accepted limitation for this feature scope; addressing it would require changes to
  the journal deduplication strategy and is deferred.
- The non-negative Cash balance assertion (SC-003, US2) is validated against the real HL ISA
  Income Account historical data, where dividends chronologically precede any fee or transfer
  events. In a hypothetical account where fees are charged before any dividends are received,
  a brief negative Cash balance would be expected and does not indicate a bug.
- The backfill mechanism that re-scans all journal rows on each run (inherited from feature 004)
  will automatically generate dividend offset rows for any historical dividend events already
  present in the journal before this feature is deployed.
- The `trading` action type is already a recognised value in the `ActionType` enum and is already
  handled by `create_ledger`. No schema changes are needed.
