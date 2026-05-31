# Feature Specification: Journal Fragment Consolidation

**Feature Branch**: `002-consolidate-journals`  
**Created**: 2026-05-31  
**Status**: Draft  
**Input**: User description: "Add a mode for consolidate_journals that takes 4 arguments to the script."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Consolidation from HL Exports (Priority: P1)

A user has a directory of Hargreaves Lansdown CSV export files and wants to produce a single standardised consolidated journal XLSX file for the first time. They invoke the pipeline with the `consolidate_journals` mode, providing the destination XLSX path, the input directory, `HL` as the consolidation method, and a free-text account name.

**Why this priority**: This is the foundational scenario — a fresh journal must be generatable before any update or merge scenario is meaningful.

**Independent Test**: Run the pipeline with a non-existent output XLSX path, a directory of HL CSV fragments, method `HL`, and an account name. Verify a valid XLSX is created at the output path with all standardised columns populated and all parseable events correctly mapped from the input files.

**Acceptance Scenarios**:

1. **Given** a directory of valid HL CSVs and a non-existent output XLSX path, **When** `consolidate_journals` is invoked, **Then** the output XLSX is created containing all parseable events with the standardised schema columns.
2. **Given** an HL CSV that has extra rows before the header, **When** processing, **Then** pre-header rows are skipped and only rows following the "Trade date / Settle date" header are imported.
3. **Given** an HL CSV row where the Reference starts with 'B' followed by digits, **When** processed, **Then** the event action is recorded as `buy`.
4. **Given** an HL CSV row where the Reference starts with 'S' followed by digits, **When** processed, **Then** the event action is recorded as `sell`.
5. **Given** an HL CSV row where the action/type column contains `Deposit` or `BACS`, **When** processed, **Then** the event action is recorded as `contrib`.
6. **Given** an HL CSV Description of "Vanguard US Equity Index Fund 500 @ £10.23", **When** processed, **Then** the sub-account is recorded as "Vanguard US Equity Index Fund" (with the quantity/unit-cost suffix stripped).
7. **Given** a successful run, **When** the pipeline finishes, **Then** the console and log both display a success summary with a count of inserted events.

---

### User Story 2 - Incremental Update of an Existing Journal (Priority: P2)

A user has a previously consolidated journal and wishes to add new HL CSV export files covering a more recent period. Running the pipeline again merges the new events into the existing journal without duplicating events that were already present.

**Why this priority**: Incremental updates are the expected ongoing usage pattern once the initial journal exists.

**Independent Test**: Create a consolidated journal from an initial set of CSVs. Add new CSV files covering a later period to the input directory and re-run. Verify new events are added and no events are duplicated.

**Acceptance Scenarios**:

1. **Given** an existing consolidated XLSX and new fragment files with events not yet in the journal, **When** `consolidate_journals` is invoked, **Then** the new events are added and the success summary reports the count of inserted events.
2. **Given** an existing consolidated XLSX and fragment files whose events are already fully represented in it, **When** processing, **Then** no new rows are added and the success summary reports zero inserted events.
3. **Given** a mix of new and already-present events in the fragments, **When** processing, **Then** only genuinely new events are inserted and the summary accurately reflects inserted vs merged counts.

---

### User Story 3 - Graceful Error Handling with Mixed File Quality (Priority: P3)

A user's input directory contains a mix of valid HL CSVs and one or more malformed or unrecognisable files. The pipeline processes the valid files, writes their events to the consolidated journal, and produces a clear error section in the summary identifying each problematic file.

**Why this priority**: Robust partial-success handling ensures valid progress is not lost and the user can identify and fix problematic files without re-running from scratch.

**Independent Test**: Place one valid HL CSV and one corrupted/headerless CSV in the input directory. Run the pipeline. Verify the output journal contains events from the valid file only, and the summary error section names the problematic file with an appropriate error message.

**Acceptance Scenarios**:

1. **Given** a directory with one valid and one invalid HL CSV, **When** processing, **Then** valid events are consolidated and the error summary lists the invalid file with a description of the failure.
2. **Given** a CSV file with no recognisable header row, **When** processed under the HL method, **Then** that file is skipped and reported in the error section with a "header not found" message.
3. **Given** a row with a missing or non-numeric value, **When** processed, **Then** that row is reported in the error section with the source file and line number, while surrounding valid rows are still processed.

---

### Edge Cases

- What happens when the input directory is empty (no fragment files present)?
- What happens when an HL CSV has a valid header but zero data rows following it?
- What happens when a Description field contains no `@` separator (no unit cost/quantity suffix to strip)?
- What happens when the value column is missing or non-numeric for a given row?
- What happens when the output XLSX path's parent directory does not exist?
- What happens when a Reference does not match any known pattern (not `B<digits>`, `S<digits>`, `Deposit`, or `BACS`)?
- What happens when non-CSV files (e.g. `.xlsx`, `.txt`) are present in the input directory?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST support a `consolidate_journals` mode, invoked with four positional arguments: (1) consolidated journal XLSX path, (2) input directory path, (3) consolidation method, (4) account name.
- **FR-002**: If no file exists at the consolidated journal path, the system MUST create a new XLSX file there with the standardised schema.
- **FR-003**: If a consolidated journal already exists, the system MUST merge new events from fragment files into it, applying deduplication to avoid inserting events that are already present. [NEEDS CLARIFICATION: What constitutes a duplicate — is a duplicate identified by the combination of `date + reference + sub_account`, or a different composite key? And should an exact duplicate silently skip or be counted as "merged" in the summary?]
- **FR-004**: The system MUST process every file in the input directory using the rules for the specified consolidation method.
- **FR-005**: The consolidated journal MUST use a fixed standardised schema with the following columns in order: `date`, `account`, `sub_account`, `action`, `reference`, `value`, `quantity`.
- **FR-006**: The `date` column MUST use the settlement date where available; trade date is used only when settlement date is absent.
- **FR-007**: The `account` column MUST be populated from the fourth argument (account name) for every row.
- **FR-008**: For the `HL` consolidation method, only CSV files in the input directory are processed; other file types are skipped without error.
- **FR-009**: For HL CSVs, the parser MUST skip all rows until it finds a header row whose first cell is "Trade date" and second cell is "Settle date"; rows before that header are discarded.
- **FR-010**: For HL CSVs, the `date` column MUST be populated from the "Settle date" column.
- **FR-011**: For HL CSVs, a Reference value matching the pattern of the letter `B` immediately followed by one or more digits MUST produce an action of `buy`.
- **FR-012**: For HL CSVs, a Reference value matching the pattern of the letter `S` immediately followed by one or more digits MUST produce an action of `sell`.
- **FR-013**: For HL CSVs, a row where the action/type field equals `Deposit` or `BACS` MUST produce an action of `contrib`.
- **FR-014**: For HL CSVs, the `sub_account` MUST be derived from the Description column by stripping any trailing suffix that contains a quantity and unit cost separated by `@` (e.g. "500 @ £10.23" or similar).
- **FR-015**: For HL CSVs, the original Reference value MUST be passed through to the `reference` column unchanged.
- **FR-016**: The pipeline MUST continue processing remaining files when a parse error is encountered for one file, rather than aborting the entire run.
- **FR-017**: On completion, the pipeline MUST output a two-section summary to both the console and the log:
  - **Success**: count of distinct events inserted, merged (deduplicated), and removed.
  - **Errors**: for each failure — source file name, line number (where applicable), and error message or detail.

### Key Entities

- **Consolidated Journal**: The canonical XLSX output file accumulating all processed events across runs. Has a fixed schema and is the sole output artifact for this mode.
- **Journal Fragment**: An input file (e.g. CSV for the HL method) containing raw exported transaction data from a provider.
- **Consolidation Method**: An enumeration value (e.g. `HL`) that selects the parser and field-mapping rules for interpreting fragment files.
- **Journal Event**: A single normalised row in the consolidated journal representing one financial transaction or cash movement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All parseable events from valid HL fragment files appear in the consolidated journal with no omissions for standard HL CSV formats.
- **SC-002**: Running consolidation twice in succession against the same input directory and existing journal produces an identical result to running it once (idempotency).
- **SC-003**: The error summary section correctly names every file that could not be fully parsed, including the line number (where applicable) and a descriptive error message.
- **SC-004**: Processing a directory of 12 typical monthly HL CSV exports (one per calendar month) completes within 60 seconds on a standard desktop.
- **SC-005**: The consolidated journal schema (column names, order, and types) is identical regardless of how many consolidation runs have been performed or which account name is used.

## Assumptions

- Input fragment files for the `HL` method are CSV files (`.csv` extension); other file types in the input directory are silently skipped.
- The consolidated journal XLSX, once created, is not manually edited between pipeline runs; the pipeline is the sole writer.
- Monetary values in HL fragment files are already denominated in GBP; no currency conversion is required.
- The `quantity` column may be empty or zero for non-unit-based events such as cash contributions.
- The pipeline is run interactively from the command line; no background scheduling is required.
- The HL CSV export format is consistent with Hargreaves Lansdown's current layout; changes to the HL export schema are out of scope.
- Events whose Reference does not match any known action pattern are recorded in the error section rather than silently dropped or passed through with an unknown action.
- The parent directory of the output XLSX path must already exist; the pipeline does not create intermediate directories.
