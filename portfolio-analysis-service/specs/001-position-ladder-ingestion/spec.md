# Feature Specification: Position Ladder Ingestion

**Feature Branch**: `001-position-ladder-ingestion`
**Created**: 2026-07-06
**Status**: Draft

## Clarifications

### Session 2026-07-06

- Q: When the retrieval endpoint is called, what format does the response use? → A: A JSON summary of the processing result (row counts, date range, sub-accounts present) plus `_links.download` pointing to an XLSX binary download endpoint. The full ladder data is NOT returned inline in the JSON payload as it would be too large.
- Q: Does the API require any form of authentication or authorisation? → A: No authentication required — open localhost API, matching the market-data-web-service pattern. Caller is trusted by virtue of network access.
- Q: What character set is valid for account names? → A: Alphanumeric, hyphens, and underscores only (`[A-Za-z0-9_-]`); 1–64 characters; case-sensitive. Invalid names are rejected at the API boundary.
- Q: When the expansion produces an empty date range (earliest activity date within two business days of today), what should the system do? → A: Reject with a 422 validation error identifying that the date range yields no business days. An empty ladder has no analytical value and must not be stored.
- Q: Should the Cash sub-account follow the same quantity=0 closure rule as equity positions? → A: No. Cash always appears on every date row regardless of balance. The closure rule (exclude after quantity reaches zero) applies to equity sub-accounts only. A zero Cash balance is a meaningful data point, not a closed position.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Submit a New Ledger for Processing (Priority: P1)

A developer calls the API with an account name and an XLSX sub-account ledger file produced
by the `create_subaccount_ledger` pipeline mode. The system validates the file's schema,
detects it has not been seen before, expands the ledger into a full daily position ladder,
and persists that ladder to the API's local store. The response confirms success and provides
a link to retrieve the stored ladder.

**Why this priority**: This is the foundational capability — without it nothing else in this
feature has any meaning. All other stories depend on at least one ledger having been submitted.

**Independent Test**: Submit a correctly formed XLSX ledger for a new account name. Verify the
response indicates success, the stored XLSX file is created, and it contains one row per
(business day, active sub-account) pair covering earliest date through T-2.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Successful ingestion of a new sub-account ledger
  Given a valid XLSX file conforming to the sub-account ledger schema
  And the account name "test-portfolio" has no existing position ladder
  When the file is submitted to the ingestion endpoint with account name "test-portfolio"
  Then the response status is 201 Created
  And the response body contains a JSON processing summary (row count, date range, sub-accounts)
  And the response body includes a "_links.download" URL to retrieve the XLSX binary
  And a position ladder XLSX file is persisted to the local store for "test-portfolio"
  And the ladder contains one row per active sub-account per business day from the earliest
      activity date through to two business days before today
  And sub-accounts with zero quantity do not appear in dates after they are closed

Scenario: Position forward-fill across days with no activity
  Given a ledger where sub-account "Equities A" has activity on 2024-01-02 and 2024-01-10
  And no activity occurs on 2024-01-03 through 2024-01-09
  When the ledger is ingested
  Then the ladder contains rows for "Equities A" on each business day between 2024-01-02
      and 2024-01-10 carrying the values from 2024-01-02 forward
  And the row for 2024-01-10 reflects the values recorded on that date

Scenario: Closed equity positions are excluded from subsequent dates
  Given a ledger where sub-account "Equities B" reaches quantity zero on 2024-03-01
  When the ledger is ingested
  Then the ladder contains rows for "Equities B" up to and including 2024-03-01
  And the ladder contains no rows for "Equities B" on any date after 2024-03-01

Scenario: Cash sub-account always appears regardless of balance
  Given a ledger where the Cash sub-account balance reaches zero on 2024-06-01
  When the ledger is ingested
  Then the ladder contains a Cash row on every business day in the date range
  And the Cash row on 2024-06-01 and all subsequent dates shows a balance of zero
```

---

### User Story 2 — Retrieve a Previously Processed Position Ladder (Priority: P2)

A developer queries the API by account name to retrieve a summary of a previously ingested
position ladder. The response returns a JSON summary (row count, date range, list of
sub-accounts) plus a `_links.download` URL to obtain the full XLSX binary. The full ladder
data is not returned inline to avoid oversized payloads.

**Why this priority**: The specification explicitly requires that the expanded ladder is
"retrievable later." This story exercises the read path independently of ingestion.

**Independent Test**: After ingesting a ledger for account "test-portfolio", call the retrieval
endpoint. Verify it returns a JSON summary with accurate counts and dates, and the
`_links.download` URL resolves to a valid XLSX file.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve summary of an existing position ladder
  Given a position ladder has previously been stored for account "test-portfolio"
  When a GET request is made for the position ladder of "test-portfolio"
  Then the response status is 200 OK
  And the response body is a JSON object containing row count, date range, and sub-account list
  And the response body includes a "_links.self" and a "_links.download" URL
  And following the "_links.download" URL returns the full XLSX binary of the position ladder

Scenario: Retrieve a ladder for an unknown account
  Given no position ladder exists for account "unknown-account"
  When a GET request is made for the position ladder of "unknown-account"
  Then the response status is 404 Not Found
  And the response body contains a descriptive error message
```

---

### User Story 3 — Re-submit an Unchanged Ledger (Idempotent) (Priority: P2)

A developer submits the same XLSX file for an account that was already successfully ingested.
The system detects via checksum that the file is unchanged, does nothing, and returns a
response indicating the existing ladder is already up to date.

**Why this priority**: Without idempotency, re-running pipelines or retrying on transient
errors would corrupt or duplicate stored data. This is a correctness guarantee.

**Independent Test**: Ingest a ledger for "test-portfolio," then submit the same file again.
Verify the response is 200 OK (not 201), the stored file is unchanged, and no reprocessing
occurred.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Re-submitting the same file is a no-op
  Given a position ladder has already been stored for account "test-portfolio"
  And the stored ladder was generated from file with checksum "abc123"
  When the same file (checksum "abc123") is submitted again for "test-portfolio"
  Then the response status is 200 OK
  And the response body is a JSON processing summary indicating the ladder is already current
  And the stored XLSX file is unchanged
  And the response body includes a "_links.download" URL to the existing stored XLSX
```

---

### User Story 4 — Submit a Changed Ledger (Merge Not Supported) (Priority: P3)

A developer submits a modified version of a ledger for an account that already has a stored
position ladder. The system detects via checksum that the file has changed and returns a
"merge not supported" error, leaving the existing ladder untouched.

**Why this priority**: The merge path is explicitly deferred; this story ensures a safe,
informative failure rather than silent corruption of existing data.

**Independent Test**: Ingest a ledger for "test-portfolio," then submit a different (modified)
file for the same account. Verify a 409 Conflict response is returned with a clear error, and
the original stored ladder is unchanged.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Submitting a changed file returns a merge-not-supported error
  Given a position ladder has already been stored for account "test-portfolio"
  And the stored ladder was generated from file with checksum "abc123"
  When a modified file (checksum "def456") is submitted for "test-portfolio"
  Then the response status is 409 Conflict
  And the response body states that merging an updated ledger is not currently supported
  And the existing stored ladder for "test-portfolio" is unchanged
```

---

### Edge Cases

- What happens when the uploaded file is not a valid XLSX file (e.g., a CSV or binary)?
- What happens when the XLSX file is missing one or more required columns?
- What happens when the XLSX file contains no data rows?
- What happens when all sub-accounts are closed (quantity zero) before today minus two business days? → Accepted: the ladder is stored as-is, containing rows only through the last date on which any position was active. The expansion end date (T-2) still applies as the ceiling, but the stored ladder will simply have no rows after the final closure date. This is a valid, complete snapshot — not an error condition. Cash may still appear on dates after all equity positions close if it had a non-zero balance at closure (per the Cash-always-present rule).
- What happens when the earliest date in the file is within two business days of today (producing an empty date range)? → Rejected with a 422 error stating no business days fall within the expansion range.
- What happens when the account name contains characters outside `[A-Za-z0-9_-]` or exceeds 64 characters? → Rejected with a 422 error identifying the constraint violated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an endpoint to ingest a sub-account ledger file for a
  named account.
- **FR-002**: The system MUST accept the ledger as a file upload (XLSX format) alongside an
  account name parameter. The account name MUST match the pattern `[A-Za-z0-9_-]`, be between
  1 and 64 characters long, and be treated as case-sensitive. Requests with invalid account
  names MUST be rejected with a descriptive 422 error.
- **FR-003**: The system MUST validate that the uploaded file is a well-formed XLSX file;
  non-XLSX files MUST be rejected with a descriptive error.
- **FR-004**: The system MUST validate that the XLSX file contains all required columns:
  `date`, `sub_account`, `book_cost`, `quantity`, `total_income`; files missing any column
  MUST be rejected with a descriptive error identifying the missing columns.
- **FR-005**: The system MUST validate that column data types are correct (date column contains
  parseable dates; numeric columns contain numeric values); invalid rows MUST cause the entire
  file to be rejected.
- **FR-006**: The system MUST compute a deterministic checksum of the uploaded file's contents
  and store it alongside the generated position ladder.
- **FR-007**: If a position ladder already exists for the account and the checksum matches,
  the system MUST return a success response indicating the ladder is already current, without
  reprocessing.
- **FR-008**: If a position ladder already exists for the account and the checksum differs,
  the system MUST return a conflict error stating that merging updated ledgers is not supported.
- **FR-009**: The system MUST validate that the expansion date range (earliest `date` in the
  file through to two business days before today, inclusive) contains at least one business day;
  if not, the file MUST be rejected with a 422 error identifying the constraint. For a valid
  range, the system MUST expand the sparse event records into a full daily position ladder
  covering every Monday–Friday in that range.
- **FR-010**: For each business day in the date range, the system MUST forward-fill each
  sub-account's `book_cost`, `quantity`, and `total_income` values from its most recent
  activity record on or before that date.
- **FR-011**: An equity sub-account (any sub-account that is not "Cash") MUST NOT appear in
  the ladder on any date after the date on which its cumulative `quantity` first reaches zero.
  The Cash sub-account MUST appear on every date row in the ladder regardless of its balance;
  a zero Cash balance is a valid and meaningful data point.
- **FR-012**: The expanded position ladder MUST be persisted as a human-readable XLSX file
  within the API instance's local data store, one file per account.
- **FR-013**: The system MUST expose a summary retrieval endpoint that returns a JSON object
  containing: total row count, first and last date in the ladder, and the list of distinct
  sub-account names present. The full ladder data MUST NOT be returned inline.
- **FR-014**: Retrieving a ladder for an account that has not been ingested MUST return a
  404 Not Found response.
- **FR-015**: All ladder-related responses MUST include HATEOAS `_links` containing at minimum
  `self` (the summary endpoint) and `download` (the XLSX binary download endpoint).
- **FR-016**: All error responses MUST use RFC 7807 Problem Details format.
- **FR-017**: The system MUST expose a dedicated download endpoint that returns the stored
  position ladder as a binary XLSX file (`application/vnd.openxmlformats-officedocument
  .spreadsheetml.sheet`) for the requested account.

### Key Entities

- **Account**: A named logical grouping of sub-account positions; identified by a
  client-supplied account name string. One account maps to one stored position ladder.
- **Sub-Account Ledger**: The sparse input file recording activity events. Each row
  represents a date on which one or more transactions occurred for a given sub-account.
  Columns: `date`, `sub_account`, `book_cost` (cumulative), `quantity` (cumulative),
  `total_income` (cumulative).
- **Daily Position Ladder**: The expanded output. One row per (business day, sub-account)
  pair, covering all active positions for every business day in the configured date range.
  Same columns as the ledger but densified by forward-fill. Persisted as XLSX.
- **Ingestion Checksum**: A deterministic fingerprint of the input file used to detect
  whether a re-submission represents an identical or modified ledger.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A correctly formed ledger file for a new account is accepted and a position
  ladder is available for retrieval within 10 seconds of submission for files containing
  up to 5,000 activity rows.
- **SC-002**: Re-submitting the same file for the same account produces an identical stored
  ladder and completes in under 1 second (no reprocessing).
- **SC-003**: Submitting a file with an invalid schema returns a descriptive error response
  in under 1 second, identifying the specific validation failure.
- **SC-004**: 100% of business days in the date range appear in the stored ladder for at
  least one sub-account (no gaps in the date series).
- **SC-005**: All closed positions (quantity = 0) are absent from the ladder on every date
  after closure, verified across all sub-accounts in the test data set.
- **SC-006**: The stored XLSX ladder file is human-readable (columns labelled, dates
  formatted as dates, numeric values as numbers) and can be opened directly in a
  spreadsheet application.

## Assumptions

- The `portfolio-analysis-service` is a new FastAPI service modelled on the existing
  `market-data-web-service` in this repository, sharing the same technology conventions
  (structlog, Pydantic, ruff, mypy, pyproject.toml).
- "Business days" means Monday through Friday; no public holiday calendar is applied
  (weekends only are excluded).
- "Today minus two business days" uses the server's local date at the time of the request.
- Account names are case-sensitive, restricted to `[A-Za-z0-9_-]`, and capped at 64
  characters. These constraints make the name safe as both a URL path segment and a filesystem
  key without escaping.
- The local data store is a directory on the API host's filesystem; no external database is
  required for this feature.
- A single XLSX file per account holds the complete position ladder; there is no versioning
  or history of previous ladder states.
- The `book_cost`, `quantity`, and `total_income` columns in the input are cumulative values
  as produced by `create_subaccount_ledger` — they are not deltas.
- The Cash sub-account is always present on every date row of the ladder regardless of
  balance. The quantity=0 closure rule applies exclusively to equity sub-accounts. This
  preserves the distinction between "no cash held" (zero balance) and "position closed."
- The merge path (handling a changed ledger) is explicitly out of scope for this feature and
  MUST return a clearly documented "not supported" error.
- The API requires no authentication. It is a locally hosted service; callers are trusted by
  virtue of network access, consistent with the market-data-web-service in this repository.
  Authentication is a known gap deferred to a future security hardening pass.
