# Feature Specification: Income Dividend Action Mappings

**Feature Branch**: `009-income-dividend-mappings`
**Created**: 2026-06-18
**Status**: Draft
**Input**: User description: "Additional action mappings for income journals are missing: ST DIV, OVR CR, UTC CR and LOYALTYU references should all be mapped to an action type of 'dividend'. The sub account for these should be taken from the description field but strip various suffixes to arrive at a standard account name."

## Clarifications

### Session 2026-06-18

- Q: For a `"LOYALTYU"` row whose description doesn't match the expected `" MM YY Gross Loyalty"` regex pattern, should the row raise a parse error (dropped) or fall back silently to using the full description as sub-account? → A: Raise a row-level parse error. The row is dropped and the error reported in the summary. FR-009's fallback applies only when the expected suffix IS matched but leaves an empty fund name — not when the LOYALTYU regex fails to match entirely.

### Session 2026-06-18 (post-analysis fixes)

- FR-001 wording updated: "case-sensitive as observed in real data" → "case-insensitive via uppercase normalisation" to align with plan.md and research.md Decision 3.
- SC-002 scoped: added parenthetical to clarify that LOYALTYU rows with non-standard suffixes are out of scope per FR-008A and do not violate the "100% retained" criterion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — ST DIV Dividend Payment Mapping (Priority: P1)

When processing an HL Stocks and Shares ISA *Income Account* fragment, rows with reference `"ST DIV"` represent UK stock dividend payments. These currently cause parse errors and are dropped from the consolidated journal. A user running the pipeline must be able to process these rows, have them categorised as `dividend` events, and have the sub-account derive the holding name by stripping the trailing `" Dividend Payment"` suffix from the description field.

**Why this priority**: UK dividends (ST DIV) are the most frequent income-type row in the ISA income account files. Every dropped dividend row silently understates income and produces an incomplete ledger.

**Independent Test**: Parse a single HL income CSV fragment containing a `"ST DIV"` row (e.g., `"Barclays plc Ordinary 25p Dividend Payment"`). The row must produce a `dividend` event with sub-account `"Barclays plc Ordinary 25p"` and no parse error.

**Acceptance Scenarios**:

1. **Given** an HL income fragment containing a row with reference `"ST DIV"` and description `"Barclays plc Ordinary 25p Dividend Payment"`, **When** the parser processes the file, **Then** the row produces a `dividend` event and the sub-account is `"Barclays plc Ordinary 25p"`.
2. **Given** the same row, **When** the sub-account is inspected, **Then** the trailing `" Dividend Payment"` suffix has been stripped and the remaining text matches the holding name used in the capital account data.
3. **Given** an HL income fragment containing only `"ST DIV"` rows, **When** `consolidate_journals` is run, **Then** zero parse errors are reported.

---

### User Story 2 — OVR CR Overseas Dividend Mapping (Priority: P1)

Rows with reference `"OVR CR"` represent overseas dividend payments. These are currently unmapped and dropped. A user must be able to process these rows as `dividend` events, with the sub-account derived by stripping the trailing `" Overseas Dividend Payment"` suffix from the description.

**Why this priority**: Equal priority to ST DIV — overseas dividends appear regularly in the income account history and their omission understates income from international holdings.

**Independent Test**: Parse a single HL income CSV fragment containing an `"OVR CR"` row (e.g., `"Man Group plc ORD USD0.0342857142 Overseas Dividend Payment"`). The row must produce a `dividend` event with sub-account `"Man Group plc ORD USD0.0342857142"` and no parse error.

**Acceptance Scenarios**:

1. **Given** an HL income fragment containing a row with reference `"OVR CR"` and description `"Man Group plc ORD USD0.0342857142 Overseas Dividend Payment"`, **When** the parser processes the file, **Then** the row produces a `dividend` event and the sub-account is `"Man Group plc ORD USD0.0342857142"`.
2. **Given** the same row, **When** the sub-account is inspected, **Then** the trailing `" Overseas Dividend Payment"` suffix has been stripped.
3. **Given** an HL income fragment containing only `"OVR CR"` rows, **When** `consolidate_journals` is run, **Then** zero parse errors are reported.

---

### User Story 3 — UTC CR Unit Trust Cash Payment Mapping (Priority: P2)

Rows with reference `"UTC CR"` represent unit trust (fund) income distributions. These appear with two description suffix variants: `" Eql - UT Cash Payment"` and `" UT Cash Payment"`. Both are currently unmapped and dropped. A user must be able to process these rows as `dividend` events with the sub-account derived by stripping the relevant suffix, leaving the fund name.

**Why this priority**: Lower frequency than direct dividends but represents meaningful income from fund holdings. Both suffix variants must be handled.

**Independent Test**: Parse HL income CSV fragments containing `"UTC CR"` rows with each suffix variant. Each must produce a `dividend` event with sub-account equal to the fund name (the portion before the suffix), and no parse error.

**Acceptance Scenarios**:

1. **Given** an HL income fragment with reference `"UTC CR"` and description `"HSBC FTSE 250 Index Class S - Income (GBP) Eql - UT Cash Payment"`, **When** parsed, **Then** the event action is `dividend` and sub-account is `"HSBC FTSE 250 Index Class S - Income (GBP)"`.
2. **Given** an HL income fragment with reference `"UTC CR"` and description `"HSBC FTSE 250 Index Class S - Income (GBP) UT Cash Payment"`, **When** parsed, **Then** the event action is `dividend` and sub-account is `"HSBC FTSE 250 Index Class S - Income (GBP)"`.
3. **Given** a file containing both `"UTC CR"` suffix variants, **When** `consolidate_journals` is run, **Then** zero parse errors are reported and both rows appear in the output.

---

### User Story 4 — LOYALTYU Gross Loyalty Payment Mapping (Priority: P2)

Rows with reference `"LOYALTYU"` represent gross loyalty (platform loyalty bonus) payments. The description includes a month-year element of the form `" MM YY Gross Loyalty"` (e.g., `" 04 26 Gross Loyalty"` for April 2026). This dynamic suffix must be stripped to leave the fund name. These rows must be categorised as `dividend` events.

**Why this priority**: Loyalty payments occur monthly across all qualifying fund positions. Without mapping, every loyalty row is dropped, silently reducing reported income.

**Independent Test**: Parse a single HL income CSV fragment containing a `"LOYALTYU"` row (e.g., `"JPMorgan Emerging Markets Class C - Accumulation (GBP) 04 26 Gross Loyalty"`). The row must produce a `dividend` event with sub-account `"JPMorgan Emerging Markets Class C - Accumulation (GBP)"` and no parse error.

**Acceptance Scenarios**:

1. **Given** an HL income fragment with reference `"LOYALTYU"` and description `"JPMorgan Emerging Markets Class C - Accumulation (GBP) 04 26 Gross Loyalty"`, **When** parsed, **Then** the event action is `dividend` and sub-account is `"JPMorgan Emerging Markets Class C - Accumulation (GBP)"`.
2. **Given** the same row, **When** the sub-account is inspected, **Then** the trailing `" 04 26 Gross Loyalty"` portion (two-digit month, two-digit year, then `" Gross Loyalty"`) has been stripped.
3. **Given** a `"LOYALTYU"` row from a different month, e.g. `" 01 26 Gross Loyalty"`, **When** parsed, **Then** the same fund name is produced — the month-year digits are not hard-coded.

---

### User Story 5 — End-to-End No Dropped Rows on Income Account Fragments (Priority: P3)

After adding all four new reference mappings, a user who runs `consolidate_journals` against the full set of HL ISA Income Account fragment files must see zero dropped rows. Every income event (dividend, loyalty, fee, transfer) must map to a known action type and produce a valid journal event.

**Why this priority**: This is the integration acceptance signal. It confirms that the four new mappings together cover every reference that appears in the real income account history.

**Independent Test**: Run `consolidate_journals` against all fragment files in the HL Stocks and Shares ISA Income Account directory; the summary must report zero errors and the output row count must match the total non-header, non-preamble input rows.

**Acceptance Scenarios**:

1. **Given** all HL ISA Income Account fragment CSV files, **When** `consolidate_journals` is run, **Then** zero parse errors are reported and no rows are dropped.
2. **Given** the consolidated journal from the above step, **When** the `action` column is inspected, **Then** every row has a known action value (`buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal`, `trading`, or `dividend`) and no `null` or unknown values appear.

---

### Edge Cases

- A `"LOYALTYU"` row whose month-year element uses a single-digit month padded with a space (e.g. `" 4 26 Gross Loyalty"` rather than `" 04 26 Gross Loyalty"`) — the suffix matching must correctly handle the zero-padded two-digit form; if the `" MM YY Gross Loyalty"` regex pattern does not match, the parser MUST raise a row-level parse error (row dropped, error reported in summary) rather than silently producing a wrong sub-account.
- A `"UTC CR"` row whose description contains both `" Eql - UT Cash Payment"` and `" UT Cash Payment"` as nested substrings — the longer `" Eql - UT Cash Payment"` variant must be tried first so it is stripped cleanly without leaving `" Eql -"` in the sub-account.
- A description field that equals exactly the suffix with no fund name prefix — the result should fall back to the reference string rather than produce an empty sub-account.
- A reference string with leading or trailing whitespace — whitespace trimming must occur before reference comparison, consistent with existing parser behaviour.
- Multiple reference types mixed in the same income fragment file — all must parse correctly in a single pass.
- A `"ST DIV"` row where the description does not end with `" Dividend Payment"` (unexpected format) — the full unmodified description should be used as the sub-account rather than silently discarding data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The parser MUST recognise reference `"ST DIV"` (exact match after whitespace trim, case-insensitive via uppercase normalisation) and map it to action `dividend`.
- **FR-002**: The parser MUST recognise reference `"OVR CR"` (exact match after whitespace trim) and map it to action `dividend`.
- **FR-003**: The parser MUST recognise reference `"UTC CR"` (exact match after whitespace trim) and map it to action `dividend`.
- **FR-004**: The parser MUST recognise reference `"LOYALTYU"` (exact match after whitespace trim) and map it to action `dividend`.
- **FR-005**: For `"ST DIV"` events, the sub-account MUST be the description field with the trailing suffix `" Dividend Payment"` removed.
- **FR-006**: For `"OVR CR"` events, the sub-account MUST be the description field with the trailing suffix `" Overseas Dividend Payment"` removed.
- **FR-007**: For `"UTC CR"` events, the sub-account MUST be the description field with the longer suffix `" Eql - UT Cash Payment"` tried first; if not present, strip `" UT Cash Payment"`. The resulting text is the sub-account.
- **FR-008**: For `"LOYALTYU"` events, the sub-account MUST be the description field with the trailing pattern `" MM YY Gross Loyalty"` removed, where `MM` and `YY` are exactly two decimal digits each.
- **FR-008A**: For `"LOYALTYU"` events where the description does NOT end with the `" MM YY Gross Loyalty"` pattern (two-digit month, two-digit year, literal `" Gross Loyalty"`), the parser MUST raise a row-level parse error. The row MUST be dropped and the error included in the consolidation summary. The description fallback defined in FR-009 does NOT apply when the LOYALTYU regex fails to match.
- **FR-009**: If suffix stripping for `"ST DIV"`, `"OVR CR"`, or `"UTC CR"` results in an empty string (the expected suffix is found but nothing precedes it), or if the suffix is absent from the description, the system MUST use the unstripped description (or the reference as a last resort) as the sub-account, rather than storing an empty value. This fallback does NOT apply to `"LOYALTYU"` (see FR-008A).
- **FR-010**: The `dividend` action type MUST be a formally recognised value within the pipeline's action type vocabulary, not a freeform string.
- **FR-011**: The new reference mappings MUST NOT affect the action or sub-account assignment of any currently recognised reference type.
- **FR-012**: Running `consolidate_journals` against all files in the HL Stocks and Shares ISA Income Account fragment directory MUST produce zero parse errors and zero dropped rows.

### Key Entities

- **Reference**: The string value from the `"Reference"` column of an HL CSV fragment row. The primary signal for action type classification, matched after whitespace trimming.
- **Action Type**: The classification of a transaction event. The value `dividend` must be added as a recognised action type alongside existing values (`buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal`, `trading`).
- **Sub-account**: The holding name derived from the `"Description"` column by stripping a reference-specific suffix. Must match the holding names used in the capital account data so cross-account analysis joins correctly.
- **Description Suffix**: A reference-specific trailing string that identifies the payment type. For `LOYALTYU` the suffix includes a dynamic month-year component rather than a fixed string.
- **HL Income Account Fragment**: A CSV file exported from the HL platform for the ISA Income Account (distinct from the ISA Stocks & Shares Capital Account). Contains dividend, loyalty, fee, and transfer events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero parse errors are produced when processing any HL ISA Income Account fragment file containing `"ST DIV"`, `"OVR CR"`, `"UTC CR"`, or `"LOYALTYU"` references.
- **SC-002**: 100% of rows across all historical HL ISA Income Account fragment files are retained in the consolidated journal output (zero dropped rows; applies to in-scope rows — LOYALTYU rows with non-standard suffix patterns are out of scope per FR-008A and the Assumptions section).
- **SC-003**: Sub-accounts produced for all four new reference types exactly match the corresponding holding names from the capital account data — verified by visual inspection against known holdings.
- **SC-004**: The `"LOYALTYU"` sub-account stripping correctly handles at least three distinct month-year values (e.g., `" 04 26 Gross Loyalty"`, `" 01 26 Gross Loyalty"`, `" 07 25 Gross Loyalty"`), each yielding the same fund name.
- **SC-005**: All four new reference types have automated unit tests covering correct action mapping and correct sub-account derivation, passing with zero failures.
- **SC-006**: No regressions — all pre-existing action mapping and sub-account tests continue to pass after the change.

## Assumptions

- The four reference strings (`ST DIV`, `OVR CR`, `UTC CR`, `LOYALTYU`) appear in the real income account data exactly as uppercase strings with no casing variants — the assumption of case-sensitive matching is based on observed file contents; if mixed-case variants are discovered during testing they should be treated as an unmapped reference and reported.
- The `dividend` action type does not yet exist in the `ActionType` enum and must be added as part of this feature.
- Dividend events must NOT be treated as cash-only actions — the sub-account carries the holding name so that downstream ledger and analysis steps can join dividend income back to the correct investment position.
- The description suffix for `LOYALTYU` always follows the pattern `" DD DD Gross Loyalty"` where both `DD` are exactly two decimal digits (zero-padded month and two-digit year). Variants that do not match this pattern are out of scope and MUST raise a row-level parse error (row dropped; error reported in the consolidation summary).
- The real HL ISA Income Account fragment files are available at `C:\Users\jhoxl\OneDrive\Investments\Journals\HL Stocks and Shares ISA - Income Account` for integration acceptance testing (US5), but are not checked into the repository.
- Sub-account values derived from income descriptions must match holdings in the capital account data. This match is based on the fund/stock name portion of the description and is assumed to be consistent across both account types in HL's export format.
- No changes to the deduplication key columns or journal schema columns are required; `dividend` maps naturally to the existing `action` field.
