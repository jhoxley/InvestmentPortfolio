# Feature Specification: Capital Ledger Ingestion

**Feature Branch**: `003-capital-ledger-ingestion`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "Add a new ingestion endpoint to the portfolio-analysis-service to consume a capital ladder and store it in the same .\Data\ location by account name. The behavior should be the same as with POST /v1/accounts/{account_name}/ladder but instead of "ladder" it would be "capital". The expected file format and validation should be based on the output from the .\AccountPreparationPipeline\ codebase mode='create_capital_ledger'. A previously generated example is here: "C:\Users\jhoxl\OneDrive\Investments\HL_SIPP_Capital_Ledger.xlsx". The incoming data should be expanded to cover every business day (Mon-Fri) between the earliest and latest date recorded, forward filling prior observations where necessary - use the same code/logic as for expanding the sub-account ledger. There should be matching 'GET' to download a summary of the stored ladder and a means to directly download the entire XLSX stored within the service, same as with the prior 'Ladder' endpoint."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a New Capital Ledger for Processing (Priority: P1)

A developer calls the API with an account name and an XLSX capital ledger file produced by the
`create_capital_ledger` pipeline mode. The system validates the file's schema, detects it has not
been seen before, expands the sparse date-level records into a full daily business-day capital
ledger, and persists that expanded ledger to the API's local store. The response confirms success
and provides a link to retrieve the stored ledger.

**Why this priority**: This is the foundational capability — without it nothing else in this
feature has any meaning. All other stories depend on at least one capital ledger having been
submitted.

**Independent Test**: Submit a correctly formed XLSX capital ledger for a new account name. Verify
the response indicates success, the stored XLSX file is created, and it contains one row per
business day covering the earliest through the latest date recorded in the submitted file.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Successful ingestion of a new capital ledger
  Given a valid XLSX file conforming to the capital ledger schema
  And the account name "test-portfolio" has no existing capital ledger
  When the file is submitted to the capital ingestion endpoint with account name "test-portfolio"
  Then the response status is 201 Created
  And the response body contains a JSON processing summary (row count, date range)
  And the response body includes a "_links.download" URL to retrieve the XLSX binary
  And a capital ledger XLSX file is persisted to the local store for "test-portfolio"
  And the ledger contains one row per business day from the earliest recorded date through
      the latest recorded date

Scenario: Capital values forward-fill across days with no recorded observation
  Given a capital ledger with recorded observations on 2024-01-02 and 2024-01-10
  And no observations are recorded on 2024-01-03 through 2024-01-09
  When the ledger is ingested
  Then the ledger contains rows for every business day between 2024-01-02 and 2024-01-10
      carrying the capital, income, and book_value figures from 2024-01-02 forward
  And the row for 2024-01-10 reflects the values recorded on that date

Scenario: Expansion range is bounded by the recorded data, not by today's date
  Given a capital ledger whose latest recorded observation is several months before today
  When the ledger is ingested
  Then the stored capital ledger's last row is the latest business day on or before the
      latest recorded date
  And no rows are generated for dates after the latest recorded date
```

---

### User Story 2 - Retrieve a Previously Processed Capital Ledger (Priority: P2)

A developer queries the API by account name to retrieve a summary of a previously ingested
capital ledger, and separately can download the full stored XLSX binary. The summary response
returns a JSON object (row count, date range) plus `_links` to the summary itself and to the
download endpoint. The full ledger data is not returned inline to avoid oversized payloads.

**Why this priority**: The specification explicitly requires that the expanded capital ledger is
retrievable later, both as a summary and as a raw download, mirroring the existing ladder
retrieval behaviour.

**Independent Test**: After ingesting a capital ledger for account "test-portfolio", call the
summary endpoint and verify accurate counts and dates, then call the download endpoint and verify
it returns the full XLSX binary.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve summary of an existing capital ledger
  Given a capital ledger has previously been stored for account "test-portfolio"
  When a GET request is made for the capital ledger summary of "test-portfolio"
  Then the response status is 200 OK
  And the response body is a JSON object containing row count and date range
  And the response body includes a "_links.self" and a "_links.download" URL

Scenario: Retrieve a capital ledger summary for an unknown account
  Given no capital ledger exists for account "unknown-account"
  When a GET request is made for the capital ledger summary of "unknown-account"
  Then the response status is 404 Not Found
  And the response body contains a descriptive error message

Scenario: Download XLSX binary for a known account
  Given a capital ledger has previously been stored for account "download-portfolio"
  When a download request is made for the capital ledger of "download-portfolio"
  Then the download response status is 200 OK
  And the content type is the XLSX MIME type
  And the Content-Disposition header specifies an attachment filename

Scenario: Download a capital ledger for an unknown account
  Given no capital ledger exists for account "unknown-account"
  When a download request is made for the capital ledger of "unknown-account"
  Then the response status is 404 Not Found
```

---

### User Story 3 - Re-submit an Unchanged Capital Ledger (Idempotent) (Priority: P2)

A developer submits the same XLSX capital ledger file for an account that was already
successfully ingested. The system detects via checksum that the file is unchanged and returns a
response confirming the existing stored ledger is current, without re-expanding the data.

**Why this priority**: Without idempotency, re-running upstream pipelines or retrying on
transient errors would risk redundant reprocessing. This is a correctness guarantee shared with
the existing ladder endpoint.

**Independent Test**: Ingest a capital ledger for "test-portfolio," then submit the same file
again. Verify the response is 200 OK (not 201), the stored file's row count and date range are
unchanged, and the response still includes a working download link.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Re-submitting the same file confirms the ledger is current
  Given a capital ledger has already been stored for account "idempotent-portfolio"
  When the same file is submitted again for "idempotent-portfolio"
  Then the response status is 200 OK
  And the response body contains status "refreshed"
  And the stored ledger's row count and date range are unchanged
  And the response body includes a "_links.download" URL to the existing stored XLSX
```

---

### User Story 4 - Submit a Changed Capital Ledger (Merge Not Supported) (Priority: P3)

A developer submits a modified version of a capital ledger for an account that already has a
stored capital ledger. The system detects via checksum that the file has changed and returns a
"merge not supported" error, leaving the existing stored ledger untouched.

**Why this priority**: The merge path is explicitly deferred, matching the existing ladder
endpoint's behaviour; this story ensures a safe, informative failure rather than silent
corruption of existing data.

**Independent Test**: Ingest a capital ledger for "test-portfolio," then submit a different
(modified) file for the same account. Verify a 409 Conflict response is returned with a clear
error, and the original stored ledger is unchanged.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Submitting a changed file returns a merge-not-supported error
  Given a capital ledger has already been stored for account "conflict-portfolio"
  And the stored ledger was generated from file with checksum "abc123"
  When a modified file (checksum "def456") is submitted for "conflict-portfolio"
  Then the response status is 409 Conflict
  And the response body states that merging an updated capital ledger is not currently
      supported
  And the existing stored capital ledger for "conflict-portfolio" is unchanged
```

---

### Edge Cases

- What happens when the uploaded file is not a valid XLSX file (e.g., a CSV or binary)? →
  Rejected with a descriptive 422 error, same as the ladder endpoint.
- What happens when the XLSX file is missing one or more required columns
  (`date`, `capital`, `income`, `book_value`)? → Rejected with a 422 error listing the missing
  columns.
- What happens when the XLSX file contains no data rows? → Rejected with a 422 error.
- What happens when `capital`, `income`, or `book_value` contain non-numeric values? → Rejected
  with a 422 error identifying the offending column(s).
- What happens when every recorded date in the file falls outside any business day (e.g., a
  single-row file whose only date is a Saturday)? → Rejected with a 422 error stating no
  business days fall within the recorded date range, mirroring the ladder endpoint's empty-range
  handling.
- What happens when the account name contains characters outside `[A-Za-z0-9_-]` or exceeds 64
  characters? → Rejected with a 422 error identifying the constraint violated.
- What happens if an account already has a stored position ladder but no capital ledger, or vice
  versa? → The two are stored and versioned independently; ingesting one has no effect on, and
  has no dependency on, the other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an endpoint to ingest a capital ledger file for a named
  account, at a path that mirrors the existing position ladder ingestion endpoint with "capital"
  in place of "ladder".
- **FR-002**: The system MUST accept the capital ledger as a file upload (XLSX format) alongside
  an account name parameter, using the same account name validation as the existing ladder
  endpoint (`[A-Za-z0-9_-]`, 1–64 characters, case-sensitive; invalid names rejected with a
  descriptive 422 error).
- **FR-003**: The system MUST validate that the uploaded file is a well-formed XLSX file;
  non-XLSX files MUST be rejected with a descriptive error.
- **FR-004**: The system MUST validate that the XLSX file contains all required columns: `date`,
  `capital`, `income`, `book_value`; files missing any column MUST be rejected with a descriptive
  error identifying the missing columns.
- **FR-005**: The system MUST validate that column data types are correct (the `date` column
  contains parseable dates; `capital`, `income`, and `book_value` contain numeric values);
  invalid values MUST cause the entire file to be rejected with a descriptive error.
- **FR-006**: The system MUST compute a deterministic checksum of the uploaded file's contents
  and store it alongside the generated capital ledger.
- **FR-007**: If a capital ledger already exists for the account and the checksum matches, the
  system MUST return a success response confirming the ledger is current, without re-expanding
  the stored data.
- **FR-008**: If a capital ledger already exists for the account and the checksum differs, the
  system MUST return a conflict error stating that merging updated capital ledgers is not
  supported, and MUST leave the existing stored ledger unchanged.
- **FR-009**: The system MUST validate that the recorded date range (earliest `date` through
  latest `date` present in the file, inclusive) contains at least one business day; if not, the
  file MUST be rejected with a 422 error identifying the constraint. For a valid range, the
  system MUST expand the sparse date-level records into a full daily capital ledger covering
  every Monday–Friday between the earliest and latest date recorded in the file — unlike the
  position ladder, this range is NOT extended forward to the current date.
- **FR-010**: For each business day in the expansion range, the system MUST forward-fill
  `capital`, `income`, and `book_value` from the most recent recorded observation on or before
  that date, using the same expansion approach (business-day generation and forward-fill) as the
  existing position ladder expansion.
- **FR-011**: The expanded capital ledger MUST be persisted as a human-readable XLSX file within
  the API instance's local data store, one file per account, stored independently of any position
  ladder file for the same account (ingesting or retrieving one MUST have no effect on the
  other).
- **FR-012**: The system MUST expose a summary retrieval endpoint that returns a JSON object
  containing: total row count, and the first and last date in the stored capital ledger. The full
  ledger data MUST NOT be returned inline.
- **FR-013**: Retrieving or downloading a capital ledger for an account that has not been
  ingested MUST return a 404 Not Found response.
- **FR-014**: All capital ledger responses MUST include HATEOAS `_links` containing at minimum
  `self` (the summary endpoint) and `download` (the XLSX binary download endpoint).
- **FR-015**: All error responses MUST use RFC 7807 Problem Details format, consistent with the
  existing ladder endpoints.
- **FR-016**: The system MUST expose a dedicated download endpoint that returns the stored
  capital ledger as a binary XLSX file (`application/vnd.openxmlformats-officedocument
  .spreadsheetml.sheet`) for the requested account.

### Key Entities

- **Account**: The same named logical grouping used by the existing position ladder feature. One
  account MAY have a stored position ladder, a stored capital ledger, both, or neither —
  independently of one another.
- **Capital Ledger Input File**: The sparse input file produced by the `create_capital_ledger`
  pipeline mode, recording one row per date on which capital, income, or book value changed.
  Columns: `date`, `capital` (cumulative), `income` (cumulative), `book_value` (cumulative).
- **Daily Capital Ledger**: The expanded output. One row per business day, covering every
  Monday–Friday between the earliest and latest date recorded in the submitted file. Same
  columns as the input, densified by forward-fill. Persisted as XLSX.
- **Ingestion Checksum**: A deterministic fingerprint of the input file used to detect whether a
  re-submission represents an identical or modified capital ledger, tracked independently of any
  position ladder checksum for the same account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A correctly formed capital ledger file for a new account is accepted and a daily
  capital ledger is available for retrieval within 10 seconds of submission for files containing
  up to 5,000 recorded rows.
- **SC-002**: Re-submitting the same file for the same account leaves the stored ledger
  identical and completes in under 1 second (no reprocessing).
- **SC-003**: Submitting a file with an invalid schema returns a descriptive error response in
  under 1 second, identifying the specific validation failure.
- **SC-004**: 100% of business days between the earliest and latest recorded date appear as a
  row in the stored capital ledger (no gaps).
- **SC-005**: The stored XLSX capital ledger file is human-readable (columns labelled, dates
  formatted as dates, numeric values as numbers) and can be opened directly in a spreadsheet
  application.

## Assumptions

- The capital ledger and the existing position ladder are independent resources per account:
  separate stored files, separate metadata (including separate checksums), and separate
  ingestion/retrieval/download endpoints. Neither requires the other to exist.
- The capital ledger's expansion range is bounded by the earliest and latest `date` values
  actually present in the submitted file. This intentionally differs from the position ladder,
  whose expansion is extended forward to "today minus two business days" to support market
  pricing lookups — the capital ledger has no forward-looking pricing step, so there is no reason
  to extend it beyond the data actually recorded.
- No market-data-service lookups or pricing enrichment apply to the capital ledger. The
  `capital`, `income`, and `book_value` figures are already expressed in the account's base
  currency by the `create_capital_ledger` pipeline mode, so this endpoint has no equivalent of
  the ladder's price/market-value/portfolio-weight enrichment step and no corresponding 502
  upstream-failure mode.
- On a checksum match, the system returns the same "refreshed" response shape used by the ladder
  endpoint (for interface consistency) but performs no recomputation — there is no external
  pricing data to refresh, so the response simply confirms the ledger is current and updates the
  stored ingestion timestamp.
- "Business days" means Monday through Friday; no public holiday calendar is applied (weekends
  only are excluded), consistent with the existing ladder feature.
- Account names use the same validation, storage-key, and no-authentication posture as the
  existing ladder endpoints in this service.
- The `capital`, `income`, and `book_value` columns in the input are cumulative values as
  produced by `create_capital_ledger` — they are not deltas — matching the pattern confirmed by
  inspection of the reference example `HL_SIPP_Capital_Ledger.xlsx`.
- The merge path (handling a changed capital ledger) is explicitly out of scope for this feature
  and MUST return a clearly documented "not supported" error, matching the ladder endpoint.
