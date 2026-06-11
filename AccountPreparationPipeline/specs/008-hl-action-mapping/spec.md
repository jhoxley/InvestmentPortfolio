# Feature Specification: HL Action Mapping — Card Web, FPC, Commission

**Feature Branch**: `008-hl-action-mapping`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "There are some missing transaction types from the HL ISA accounts that are not mapped."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Card Web and FPC Deposit References (Priority: P1)

When processing HL Stocks and Shares ISA transaction files, cash deposit events made via card payment ("Card Web") or the FPC transfer mechanism are not currently recognised and cause rows to be dropped with parse errors. A user running the pipeline against real HL ISA data must be able to process all such rows without error and have them categorised as deposit events.

**Why this priority**: These references appear in real ISA transaction files and block end-to-end processing. Any dropped row means the ledger is incomplete and unreliable for investment analysis.

**Independent Test**: Can be fully tested by parsing a single HL CSV fragment containing a "Card Web" row and a "FPC" row; both must produce deposit events with no parse errors.

**Acceptance Scenarios**:

1. **Given** an HL fragment containing a row with reference `"Card Web"`, **When** the parser processes the file, **Then** the row produces a deposit event with no parse error and the sub-account is "Cash".
2. **Given** an HL fragment containing a row with reference `"card web"` (lowercase), **When** the parser processes the file, **Then** the row is treated identically to `"Card Web"` — matching is case-insensitive.
3. **Given** an HL fragment containing a row with reference `"FPC"`, **When** the parser processes the file, **Then** the row produces a deposit event with no parse error and the sub-account is "Cash".
4. **Given** an HL fragment containing a row with reference `"fpc"` (lowercase), **When** the parser processes the file, **Then** the row is treated identically to `"FPC"` — matching is case-insensitive.

---

### User Story 2 — Commission Income Reference (Priority: P2)

Commission payments from HL (e.g. fund commission rebates or interest payments described as commission) currently cause rows to be dropped with parse errors. A user must be able to process these rows so that commission income is correctly categorised as an income event.

**Why this priority**: Income events affect the accuracy of portfolio returns analysis. Dropped commission rows silently understate income. Lower priority than US1 only because commission events are typically less frequent than card deposits.

**Independent Test**: Can be fully tested by parsing a single HL CSV fragment containing a "Commission" row; the row must produce an income event with no parse error and the sub-account is "Cash".

**Acceptance Scenarios**:

1. **Given** an HL fragment containing a row with reference `"Commission"`, **When** the parser processes the file, **Then** the row produces an income event with no parse error and the sub-account is "Cash".
2. **Given** an HL fragment containing a row with reference `"COMMISSION"` (uppercase), **When** the parser processes the file, **Then** the row is treated identically to `"Commission"` — matching is case-insensitive.
3. **Given** an HL fragment containing a row with reference `"commission"` (lowercase), **When** the parser processes the file, **Then** the row is treated identically to `"Commission"` — matching is case-insensitive.

---

### User Story 3 — End-to-End Pipeline Success on HL ISA Fragments (Priority: P3)

After adding the new reference mappings, a user who runs the full pipeline (`consolidate_journals` followed by `create_ledger`) against the actual HL ISA transaction fragment files should see no dropped rows and a complete output ledger.

**Why this priority**: This is an integration validation that depends on US1 and US2 being complete. It provides the ultimate acceptance signal that no other unmapped references remain in the current HL ISA data.

**Independent Test**: Run `consolidate_journals` against the HL ISA fragments; the summary must report zero errors and the output row count must match the total input rows across all fragment files.

**Acceptance Scenarios**:

1. **Given** the HL ISA fragment CSV files, **When** `consolidate_journals` is run, **Then** the exit code is 0, zero parse errors are reported, and no input rows are dropped.
2. **Given** the consolidated journal produced in the above step, **When** `create_ledger` is run, **Then** the exit code is 0 and the output ledger contains one row per consolidated journal row.

---

### Edge Cases

- Reference strings with leading/trailing whitespace (e.g. `" Card Web "`) — whitespace is stripped before matching, consistent with how all other references are handled.
- A reference value that begins with "Card Web" but has additional text (e.g. `"Card Web 2024-01"`) — only an exact case-insensitive match (after whitespace trimming) should map to deposit; a prefixed match must NOT silently consume unrecognised variants.
- Multiple new-reference rows in the same file mixed with existing reference types — all must parse successfully in a single pass.
- A "Commission" row that also has a non-empty `description` field — the description must not affect the action mapping (the reference alone determines the action).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The parser MUST recognise a reference of `"Card Web"` (case-insensitive, exact match after whitespace trim) and map it to action `deposit`.
- **FR-002**: The parser MUST recognise a reference of `"FPC"` (case-insensitive, exact match after whitespace trim) and map it to action `deposit`.
- **FR-003**: The parser MUST recognise a reference of `"Commission"` (case-insensitive, exact match after whitespace trim) and map it to action `income`.
- **FR-004**: Events mapped to `deposit` via FR-001 or FR-002 MUST be assigned the "Cash" sub-account, consistent with all other deposit events.
- **FR-005**: Events mapped to `income` via FR-003 MUST be assigned the "Cash" sub-account, consistent with all other income events.
- **FR-006**: All three new mappings MUST be case-insensitive; `"CARD WEB"`, `"card web"`, and `"Card Web"` are all equivalent.
- **FR-007**: The new mappings MUST NOT affect parsing of any currently recognised reference types.
- **FR-008**: A file containing rows with the new references mixed with existing reference types MUST parse with zero errors for both old and new row types.
- **FR-009**: The `consolidate_journals` command MUST exit with code 0 and report zero dropped rows when run against the current HL ISA fragment files once the above mappings are in place.

### Key Entities

- **Reference**: The string value from the "Reference" column of an HL CSV fragment row. Used as the primary signal for action type classification. Matched case-insensitively after whitespace trimming.
- **Action Type**: The categorisation of a transaction event — one of: `buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal`, `trading`. Determines both the ledger behaviour and the sub-account assignment.
- **HL Fragment**: A single CSV file exported from the HL platform containing a transaction history for a period within one account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero parse errors are produced when processing any HL fragment file containing `"Card Web"`, `"FPC"`, or `"Commission"` references.
- **SC-002**: 100% of input rows from the current HL ISA fragment files are retained in the consolidated journal output (zero dropped rows).
- **SC-003**: All three new reference types have automated unit tests that verify the correct action mapping and correct sub-account assignment, passing with zero failures.
- **SC-004**: No regressions — all pre-existing action mapping tests continue to pass after the change.

## Assumptions

- Matching is an exact case-insensitive comparison after whitespace trimming; prefix or substring matching is explicitly out of scope.
- "Card Web" and "FPC" always represent cash deposits into the ISA account, not withdrawals or other actions — no description-based disambiguation is needed.
- "Commission" always represents income, not a fee or other action — no description-based disambiguation is needed.
- The sub-account for all three new action types follows the existing rule: `deposit` and `income` events are assigned the "Cash" sub-account automatically.
- No new `ActionType` enum values are required; the existing `deposit` and `income` types are sufficient.
- The real HL ISA fragment files are available locally for the end-to-end acceptance test (US3) but are not checked into the repository; this test is a manual or local-only validation step.
- The existing test fixture CSV files pattern (small synthetic CSV files in `tests/data/`) will be used to add automated unit tests for the three new mappings.
