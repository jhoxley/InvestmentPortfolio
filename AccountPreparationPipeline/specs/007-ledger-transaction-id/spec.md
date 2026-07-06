# Feature Specification: Ledger Transaction ID

**Feature Branch**: `007-ledger-transaction-id`
**Created**: 2026-06-10
**Status**: Draft
**Input**: User description: "Introduce a 'Transaction ID' column into the final ledger that is a
monotonically increasing, integer ID of two parts, a 5-digit number with a hyphen then another
3-digit number..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every Ledger Row Has a Unique, Formatted Transaction ID (Priority: P1)

A user opens the ledger XLSX and sees a `Transaction ID` column on every row. Each ID has the
form `NNNNN-NNN` (e.g. `00001-001`, `00002-001`). When they sort the entire sheet by Transaction
ID ascending, the rows appear in the correct canonical order.

**Why this priority**: The Transaction ID is the foundation of the feature. Without it, sorting
is undefined, the insertion-slot mechanism (US3) has no anchor, and the invariant guarantee (US2)
cannot be expressed. Everything else builds on this.

**Independent Test**: Run `create_ledger` against a journal with three rows. Open the ledger
XLSX and verify the `Transaction ID` column exists, every cell is populated, and the values are
`00001-001`, `00002-001`, `00003-001` in row order.

**Acceptance Scenarios**:

1. **Given** a journal containing three events,
   **When** `create_ledger` is run,
   **Then** the output ledger contains a `Transaction ID` column as the first column, every row
   has a non-null value in that column, and the values are `00001-001`, `00002-001`, `00003-001`
   in ascending row order.

2. **Given** a journal containing 100 events,
   **When** `create_ledger` is run,
   **Then** Transaction IDs range from `00001-001` to `00100-001` with no gaps, no duplicates,
   and the suffix is always `-001` on a first-time run.

3. **Given** a single-event journal,
   **When** `create_ledger` is run,
   **Then** the single row has Transaction ID `00001-001`.

---

### User Story 2 — Sorting by Transaction ID Preserves the Per-Position Ledger Invariant (Priority: P1)

A user has a journal that includes multiple buy/sell trades settling on the same date, each of
which creates a cash offset row in the `Cash` sub-account. When they open the ledger XLSX and
sort by `Transaction ID` ascending (or simply rely on the row order produced by `create_ledger`),
every sub-account's running `Account Value` equals the previous row's `Account Value` plus the
current row's `Transaction Value`. There is no ambiguity about which Cash offset row comes before
another on the same date.

**Why this priority**: The primary value of the Transaction ID column is to give the ledger a
canonical, stable sort order. Without a deterministic ordering of same-date rows, the invariant
holds in some sort orderings but not others — the ledger is correct only by accident. This story
formalises and guarantees the invariant.

**Independent Test**: Build a journal with two buy trades settling on 2024-03-15 — `B001` (value
−£1 000) and `B002` (value −£500) — plus their Cash offsets `B001-offset` (value −£1 000) and
`B002-offset` (value −£500). Run `create_ledger`. Sort the output by `Transaction ID`. For the
Cash sub-account rows, verify: `Account Value[row2] = Account Value[row1] + Transaction Value[row2]`
and `Account Value[row3] = Account Value[row2] + Transaction Value[row3]` (where row1, row2, row3
are the Cash rows in Transaction ID order). The invariant must hold regardless of the original
journal row order.

**Acceptance Scenarios**:

1. **Given** a journal containing two buy trades settling on the same date, each with a
   corresponding Cash offset row,
   **When** `create_ledger` is run,
   **Then** the output ledger rows for the `Cash` sub-account, sorted by `Transaction ID`,
   satisfy `Account Value[i] = Account Value[i-1] + Transaction Value[i]` for every row `i`.

2. **Given** a journal where Cash offset rows appear BEFORE their originating trade rows (due to
   journal insertion order),
   **When** `create_ledger` is run,
   **Then** the `Transaction ID` values still produce an order in which the per-position invariant
   holds when sorted ascending — the invariant is not sensitive to the journal's physical row order.

3. **Given** any valid journal,
   **When** `create_ledger` is run and the output is sorted by `Transaction ID` ascending,
   **Then** for every `(account, sub_account)` pair, the invariant
   `Account Value[i] = Account Value[i-1] + Transaction Value[i]` holds for all rows `i > 1` in
   that group.

---

### User Story 3 — Inserting New Rows on Re-Run Preserves Existing Transaction IDs (Priority: P2)

A user re-runs `create_ledger` after new journal events have been added that settle on dates
already present in the existing ledger. The new rows are assigned Transaction IDs that fit
between the surrounding existing IDs, using an incremented 3-digit suffix (`-002`, `-003`, etc.).
All previously existing Transaction IDs remain unchanged.

**Why this priority**: Stable IDs protect users who have annotated, filtered, or linked to
specific rows by Transaction ID. Inserting with suffix increments prevents ID conflicts while
allowing rows to be inserted anywhere. This story requires US1 and US2 to be complete first.

**Independent Test**: Run `create_ledger` to produce a ledger with rows `00001-001`, `00002-001`,
`00003-001`. Add a new journal event that sorts between the first and second existing events. Re-run
`create_ledger`. Verify that the original three rows still have their original Transaction IDs, and
the new row has `Transaction ID = 00001-002`.

**Acceptance Scenarios**:

1. **Given** an existing ledger with rows `00001-001`, `00002-001`, `00003-001`,
   **And** a new journal event that canonically sorts between `00001-001` and `00002-001`,
   **When** `create_ledger` is re-run,
   **Then** the new row is assigned `Transaction ID = 00001-002`, and the existing three rows
   retain `00001-001`, `00002-001`, `00003-001` unchanged.

2. **Given** an existing ledger where a slot already has suffix `-002` (i.e. `00001-002` exists),
   **And** another new event sorts between `00001-001` and `00001-002`,
   **When** `create_ledger` is re-run,
   **Then** the newest inserted row is assigned `00001-003`, and all previous IDs are unchanged.

3. **Given** an existing ledger,
   **And** a new journal event that canonically sorts after all existing rows,
   **When** `create_ledger` is re-run,
   **Then** the new row is assigned the next sequential 5-digit number with suffix `-001`
   (e.g. if the last existing row was `00042-001`, the new row gets `00043-001`).

4. **Given** an existing ledger,
   **And** no new journal events (idempotent re-run),
   **When** `create_ledger` is re-run,
   **Then** all Transaction IDs are identical to the previous run — no IDs change on an
   idempotent re-run.

---

### Edge Cases

- What if a journal is empty? The ledger is also empty; no Transaction IDs are assigned.
- What if two rows have identical (date, sub_account, reference) keys? This would be a journal
  data error — `create_ledger` treats references as unique within a position on a given date.
  The ID assignment uses the deterministic sort order to break ties if duplicates exist.
- What if the 3-digit suffix reaches `999` (i.e. 999 insertions between the same two rows)?
  This is treated as an overflow error; the user must restructure the journal. The maximum
  number of insertions between any two adjacent 5-digit IDs is 998 (suffixes 002–999).
- What if the 5-digit prefix reaches `99999`? This supports up to 99 999 ledger rows on a single
  first-time run, which exceeds any realistic journal size for a retail investment account.
- What if the existing ledger output file does not exist or cannot be read on a re-run? The
  system treats it as a first-time run and assigns IDs from `00001-001`.

## Clarifications

### Session 2026-06-10

- Q: Should `account` be included in the canonical sort key to handle multi-account journals where different accounts may share the same `sub_account` and `reference` on the same date? → A: Yes — extend the sort key to `(date, account, sub_account, reference)` so that rows from different accounts are unambiguously ordered and the PriorIDMap key is globally unique per row.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `create_ledger` output MUST include a `Transaction ID` column. On a first-time
  run (no prior ledger), IDs are assigned as `00001-001`, `00002-001`, `00003-001`, … in the
  canonical ledger sort order. The suffix is always `-001` on a first-time run.

- **FR-002**: The canonical sort order used to assign Transaction IDs MUST ensure that for every
  `(account, sub_account)` pair, sorting the ledger by `Transaction ID` ascending produces an
  ordering where `Account Value[i] = Account Value[i-1] + Transaction Value[i]` holds for all
  rows `i > 1`. The sort key for a row is `(date, account, sub_account, reference)` — rows are
  ordered by date ascending, then by account alphabetically, then by sub_account alphabetically,
  then by reference alphabetically — so that rows from the same position on the same date are
  always grouped and ordered consistently, and rows from different accounts with the same
  sub_account and reference are unambiguously distinguished.

- **FR-003**: On a re-run (an existing ledger is present for the same output path), the system
  MUST read the existing Transaction IDs and preserve them for all rows whose
  `(date, account, sub_account, reference)` key already appears in the prior ledger. Existing IDs
  MUST NOT change.

- **FR-004**: On a re-run, new rows whose canonical sort position falls between two existing rows
  MUST be assigned a Transaction ID whose 5-digit prefix equals the preceding row's 5-digit
  prefix and whose 3-digit suffix is one greater than the highest existing suffix for that
  prefix (starting from `-002` for the first insertion, `-003` for the second, etc.).

- **FR-005**: On a re-run, new rows whose canonical sort position falls after all existing rows
  MUST be assigned the next sequential 5-digit prefix with suffix `-001`.

- **FR-006**: Transaction IDs MUST be formatted as zero-padded strings: exactly 5 digits, a
  hyphen, exactly 3 digits (e.g. `00001-001`, not `1-1` or `1-001`). The column MUST be stored
  as a text/string value in the output XLSX so that Excel sorts it lexicographically as intended.

- **FR-007**: An idempotent re-run (no new journal events) MUST produce a ledger identical in
  Transaction ID values to the prior run.

- **FR-008**: The `Transaction ID` column MUST be the first (leftmost) column in the output
  ledger XLSX so that it is immediately visible and easy to sort on in Excel.

### Key Entities

- **Transaction ID**: A two-part string identifier `NNNNN-NNN` (5-digit prefix, hyphen, 3-digit
  suffix), uniquely identifying a row in the ledger. The prefix encodes the row's canonical
  sequence position; the suffix distinguishes rows inserted between two consecutive prefix values
  on subsequent runs.
- **Canonical Sort Order**: The ordering `(date ASC, account ASC, sub_account ASC, reference ASC)`
  applied to all ledger rows to produce a deterministic, invariant-preserving sequence. This
  ordering is used for both ID assignment and row sequencing in the output. Including `account`
  ensures rows from different accounts with the same sub_account and reference on the same date
  are unambiguously ordered.
- **Prior Ledger**: The existing output XLSX file (if any) from a previous `create_ledger` run.
  The system reads its Transaction ID column to determine which IDs are already allocated before
  assigning IDs to new rows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every row in every ledger produced by `create_ledger` contains a non-null
  `Transaction ID` value. Zero rows with missing or malformed Transaction IDs across the full
  test suite.

- **SC-002**: For any ledger sorted by `Transaction ID` ascending, the per-position invariant
  (`Account Value[i] = Account Value[i-1] + Transaction Value[i]`) holds for 100% of rows in
  every `(account, sub_account)` group. Zero invariant violations, including on dates with
  multiple same-day Cash offset rows.

- **SC-003**: On an idempotent re-run (same journal, same output path), 100% of Transaction IDs
  are unchanged. Zero ID mutations on a no-change re-run.

- **SC-004**: When a single new row is inserted into an existing ledger at any position via a
  re-run, the new row receives a correctly-formatted suffix-incremented ID, and 100% of existing
  IDs remain unchanged. Zero regressions in existing ID assignments.

- **SC-005**: All existing `create_ledger` tests pass with no regressions after the Transaction
  ID column is introduced. The column addition does not alter the values in any other column.

## Assumptions

- The canonical sort key `(date, account, sub_account, reference)` produces a fully deterministic
  order that satisfies the per-position invariant. Including `account` ensures rows from different
  accounts with matching `sub_account` and `reference` values on the same date are unambiguously
  distinguished. References are assumed unique within a `(date, account, sub_account)` triple in
  well-formed journal data.
- The existing output file (prior ledger) is readable if present; if it is locked, corrupted, or
  unreadable, the system treats it as absent and issues a warning.
- Transaction IDs are stored as plain text strings in the XLSX output, not as numeric values, to
  preserve the hyphen separator and zero-padding through Excel operations.
- The 5-digit prefix supports up to 99 999 rows per first-time run, which is sufficient for any
  realistic retail investment account ledger.
- The `create_ledger` mode currently takes two positional arguments (input journal path, output
  ledger path). The output path is used to locate the prior ledger on re-runs; no additional
  CLI arguments are needed.
- `Transaction ID` is a new column added to the existing ledger schema; all existing columns
  (`date`, `sub_account`, `action`, etc.) and their values are unchanged.
