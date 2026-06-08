# Feature Specification: Trade Cash Offset Entries

**Feature Branch**: `004-trade-cash-offsets`  
**Created**: 2026-06-05  
**Status**: Draft  
**Input**: User description: "Ensure cash balance is maintained correctly for buy/sell trade actions. When running consolidate_journals mode there should be a post-processing step that adds a synthetic transaction on the same date as a 'buy' or 'sell'. A quantity and value opposite equal to the value of the actual trade multipled by -1 should be included with a 'sub-account' of 'cash' and action of 'trading'. The reference should be the same as the reference of the trade (Bxxxx or Sxxxx) with '-offset' suffix appended."

## Clarifications

### Session 2026-06-08

- Q: When this feature is first used on an existing journal that already contains buy/sell trades, should those existing trades automatically get retroactive offset entries on the next run? → A: Yes — full backfill: on each run, scan all buy/sell rows in the journal and generate any missing offsets.
- Q: Should the consolidation summary report offset insertions as part of the existing `Events inserted` count, or as a separate labelled counter? → A: Combined — offsets counted within the existing `Events inserted` total; no separate line in the summary.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cash Offsets Generated for Buy and Sell Trades (Priority: P1)

A user runs `consolidate_journals` against a set of HL export files that contain buy and sell
events. After consolidation, the output journal contains not only the original trade rows but also
a matching synthetic "Cash" row for each trade — representing the equal-and-opposite cash
movement that accompanies every investment purchase or sale. The user can then run
`create_ledger` on the resulting journal and see an accurate running cash balance alongside each
investment position.

**Why this priority**: Without cash offsets, the Cash position in the ledger reflects only
explicit cash deposits and withdrawals, omitting the cash outflows and inflows caused by
investment trades. This makes the Cash balance incorrect and the ledger untrustworthy for
reconciliation purposes. Generating offsets automatically during consolidation is the foundational
requirement.

**Independent Test**: Run `consolidate_journals` with a set of HL CSV files that include at least
one buy trade (e.g. reference B12345, value £1 000.00) and one sell trade (e.g. reference
S67890, value −£500.00 — HL stores sell proceeds as a negative number). Open the output journal
and confirm it contains a row with `sub_account = "Cash"`, `action = "trading"`,
`reference = "B12345-offset"`, `value = -1 000.00`, `quantity = -1 000.00`; and a second offset
row for the sell with `reference = "S67890-offset"`, `value = 500.00`, `quantity = 500.00`
(positive — cash inflow from the sale).

**Acceptance Scenarios**:

1. **Given** an HL CSV containing a buy event (reference B12345, value £1 000.00, date 2024-03-15),
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "B12345-offset"`, `value = -1 000.00`,
   `quantity = -1 000.00`, `date = 2024-03-15`, and `account` matching the buy event.

2. **Given** an HL CSV containing a sell event (reference S67890, value −£500.00, date 2024-04-01)
   — HL export files store sell proceeds as negative values,
   **When** `consolidate_journals` is run,
   **Then** the output journal contains a synthetic row with `sub_account = "Cash"`,
   `action = "trading"`, `reference = "S67890-offset"`, `value = 500.00`,
   `quantity = 500.00` (positive — cash inflow from the sale), `date = 2024-04-01`.

3. **Given** an HL CSV containing both buy and sell events,
   **When** `consolidate_journals` is run,
   **Then** one synthetic offset row is produced for each trade — the number of offset rows
   equals the number of buy and sell rows in the journal.

4. **Given** an HL CSV containing only deposit, income, or fee events (no buy or sell trades),
   **When** `consolidate_journals` is run,
   **Then** no synthetic offset rows are generated.

---

### User Story 2 — Offset Deduplication on Re-Run (Priority: P2)

A user runs `consolidate_journals` a second time with the same or overlapping inputs. Because
offset entries carry a unique reference derived from the original trade reference, re-running does
not create duplicate offsets in the journal.

**Why this priority**: The existing consolidation mode is idempotent for all other event types;
this feature must not break that guarantee. A re-run must produce the same journal as the first
run.

**Independent Test**: Run `consolidate_journals` twice with identical inputs. Confirm that the
journal after the second run contains the same number of rows as after the first run — no offset
row is duplicated.

**Acceptance Scenarios**:

1. **Given** a journal already containing buy events and their corresponding offset entries,
   **When** `consolidate_journals` is run again with the same input files,
   **Then** the count of offset rows in the journal is unchanged (offsets are not duplicated),
   and the success summary reports zero events inserted.

2. **Given** a journal containing existing trades and offsets, and new input files containing
   additional buy events not yet in the journal,
   **When** `consolidate_journals` is run,
   **Then** only the new trades and their corresponding new offsets are inserted; existing offsets
   are not duplicated.

---

### User Story 3 — Offset Rows Visible in Consolidation Summary (Priority: P3)

Offset rows inserted during consolidation are counted in the success summary alongside regular
event insertions, so the user can see how many synthetic rows were added.

**Why this priority**: Transparency about what was written to the journal is useful for
verification. Users should be able to confirm offsets were generated without having to open
and inspect the XLSX manually.

**Independent Test**: Run `consolidate_journals` against a file with two buy events and one sell
event. Confirm the success summary shows at least 3 inserted events attributable to the offset
step (in addition to the 3 real trade events).

**Acceptance Scenarios**:

1. **Given** an input file with two buy events and one sell event,
   **When** `consolidate_journals` is run for the first time,
   **Then** the success summary reports `Events inserted: 6` (3 real + 3 offsets combined in
   the existing counter; no separate offset line).

---

### Edge Cases

- What happens when a buy or sell event has a zero value (£0.00)? The offset entry is still
  generated (value and quantity both 0.00), preserving the row count symmetry.
- What happens if the "-offset" reference suffix would make the reference exceed any storage
  limit? Not applicable — the journal stores references as variable-length text.
- What happens when a buy or sell event is removed from the journal between runs? Its
  corresponding offset (if already present) is not automatically removed; the user must manually
  remove it if necessary. Automated removal of orphaned offsets is out of scope.
- What happens if an HL export file contains a trade whose reference already ends in "-offset"
  (colliding with the synthetic naming convention)? This is considered a data quality issue
  in the source export; the behaviour follows the existing parse-error pattern.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After all fragment files are parsed and consolidated into the journal, the system
  MUST scan the full journal and generate one synthetic offset row for every `buy` or `sell`
  event that does not already have a corresponding offset entry (identified by the absence of
  a row with `reference = <trade-ref>-offset`). This applies to both newly inserted events and
  any pre-existing buy/sell trades that were present before this feature was deployed.

- **FR-002**: All synthetic offset rows (both newly generated and backfilled) MUST be written
  into the consolidated journal within the same invocation as the real trade events, so that
  the output XLSX reflects both the real and synthetic rows after a single pipeline run. (The
  implementation may use more than one internal save call — e.g. a backfill pass after the
  initial merge — provided the final state is correct before the process exits.)

- **FR-003**: The synthetic offset row MUST carry the following field values, derived from the
  corresponding trade event:
  - `date`: same as the trade event's date
  - `account`: same as the trade event's account
  - `sub_account`: the literal string `"Cash"`
  - `action`: the literal string `"trading"`
  - `reference`: the trade event's reference with the literal suffix `"-offset"` appended
    (e.g. `"B12345"` → `"B12345-offset"`)
  - `value`: the trade event's value multiplied by −1
  - `quantity`: the trade event's value multiplied by −1 (same as the offset value)

- **FR-004**: The system MUST NOT generate a synthetic offset row for events with actions other
  than `buy` or `sell` (e.g. `deposit`, `income`, `fee`, `withdrawal`, or `trading`).

- **FR-005**: Offset rows MUST be subject to the same deduplication logic as all other journal
  events. Because offset references are unique and reference-based deduplication applies to
  trade references, a re-run with identical inputs MUST NOT produce duplicate offset rows.

- **FR-006**: The offset row's `quantity` column value MUST be the negated value of the trade,
  not the trade's own `quantity`. This ensures the Cash position always tracks money in/out, not
  units.

- **FR-007**: The schema of each offset row MUST conform to the existing seven-column journal
  schema: `date`, `account`, `sub_account`, `action`, `reference`, `value`, `quantity`. No
  additional columns may be added.

- **FR-008**: The number of rows in the consolidated journal after a run MUST equal the number of
  rows before the run plus the number of newly inserted real events plus the number of newly
  generated offset rows. The row count invariant is preserved.

- **FR-009**: Offset rows MUST appear in the journal in the same sort order as all other rows
  (the journal is not re-sorted by this feature; offsets are appended alongside real events
  during the normal merge step).

### Key Entities

- **Trade Event**: A journal row with `action` of `buy` or `sell`. The source for offset
  generation.
- **Synthetic Offset Row**: A programmatically generated journal row with `sub_account = "Cash"`
  and `action = "trading"`, representing the cash impact of a single trade. Always paired 1:1
  with a Trade Event.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every `buy` or `sell` event in the output journal, exactly one corresponding
  synthetic offset row exists with `sub_account = "Cash"`, `action = "trading"`, and
  `reference = <trade-ref>-offset`. The count of offset rows equals the count of buy+sell rows
  at all times.

- **SC-002**: Running `consolidate_journals` twice in succession with identical inputs produces
  a journal with the same row count as a single run — no offset row is duplicated (idempotency
  preserved).

- **SC-003**: The `value` and `quantity` of every offset row equal the negated value of their
  corresponding trade event, verifiable by summing `value` over each (account, sub_account) pair:
  for a position with only buy/sell trades, the sum of all trade values plus the sum of all
  offset values equals zero.

- **SC-004**: Adding the offset generation step does not increase the total wall-clock time for
  a standard consolidation run (12 monthly HL CSV files) by more than 5 seconds compared to a
  run without offsets.

## Assumptions

- The offset generation step runs as part of the existing `consolidate_journals` mode; it does
  not require a new pipeline mode or CLI command.
- Only events with `action = "buy"` or `action = "sell"` trigger offset generation; other action
  types (`deposit`, `income`, `fee`, `withdrawal`) are excluded.
- The `quantity` field of offset rows is always set to the negated trade `value`, not the
  negated trade `quantity`. This reflects the nature of Cash positions, where quantity and value
  are the same.
- A backfill pass runs after each consolidation: the system scans all buy/sell rows in the
  journal and inserts a corresponding offset row for any trade that does not already have one
  (identified by the absence of a row with `reference = <trade-ref>-offset`). This ensures
  SC-001 holds even for journals built before this feature was deployed.
- The feature applies to all future consolidation runs regardless of which consolidation method
  is in use (currently only `HL`; the offset rule is method-agnostic).
- Manually editing the journal to remove an offset row while leaving its corresponding trade in
  place is supported (the offset will be re-inserted on the next run, as the dedup key will no
  longer exist).
- The consolidated journal XLSX is the sole output artifact; no separate report of offset rows
  is produced.
