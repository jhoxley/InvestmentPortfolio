# Feature Specification: HL Lodgement Action Mapping

**Feature Branch**: `012-hl-lodgement-action`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "Add logic to handle lodgements in journals. For the 'HL' mode a reference starting with 'L' and a numeric value indicates the 'action' should be 'Lodgement'. Similar to how buy/sell identification works. The sub-account is taken from the description where the prefix of 'Lodgement ' is removed and the remainder of the description becomes the sub-account name."

## Overview

Hargreaves Lansdown (HL) capital account journals include "lodgement" transactions — in-specie transfers of securities into the account. These appear with a reference in the format `L` followed by digits (e.g., `L003538235`) and a description prefixed with `"Lodgement "` followed by the security name. The pipeline currently fails to recognise these rows and raises an "Unknown action" parse error. This feature adds correct recognition and mapping of lodgement transactions so they are processed without errors and classified with the accurate action type and sub-account.

## User Scenarios & Testing

### User Story 1 — HL Lodgement Rows Are Correctly Classified (Priority: P1)

When processing an HL capital account journal that contains lodgement transactions, the pipeline correctly identifies them by their L-prefixed reference, assigns them a `lodgement` action type, and derives the security name as the sub-account by stripping the leading `"Lodgement "` prefix from the description.

**Why this priority**: Without this, any capital account journal that includes lodgement transactions fails to parse entirely (or produces errors for each lodgement row), meaning historical journals cannot be processed. This is the only functional gap.

**Independent Test**: Run `consolidate_journals` against a CSV fragment containing one or more lodgement rows (reference `L` + digits, description `Lodgement <security name>`). Verify: exit code 0, output journal contains one row per lodgement with action `lodgement`, sub_account equals the description with `"Lodgement "` stripped, and no parse errors are reported.

**Acceptance Scenarios**:

1. **Given** an HL CSV file where a row has reference `L003538235` and description `Lodgement Barclays plc Ordinary 25p`, **When** `consolidate_journals` is run, **Then** the output journal contains a row with `action = lodgement` and `sub_account = "Barclays plc Ordinary 25p"`.

2. **Given** an HL CSV file with a lodgement row whose description contains no strippable suffix (the full description after removing `"Lodgement "` is the security name), **When** the journal is processed, **Then** the sub-account is the exact remainder of the description after the `"Lodgement "` prefix.

3. **Given** an HL CSV file containing a mix of buy, sell, deposit, and lodgement rows, **When** `consolidate_journals` is run, **Then** the output journal contains all row types correctly classified, and the total event count matches the number of data rows in the CSV.

4. **Given** an HL CSV file with a row whose reference does not start with `L` followed only by digits (e.g., `LOYALTYU`, `L-invalid`), **When** the journal is processed, **Then** that row is NOT classified as a lodgement — existing action mapping for that reference is used unchanged.

5. **Given** a journal that previously failed to parse due to an unknown lodgement reference, **When** it is re-processed after this change, **Then** all lodgement rows are inserted without error.

---

### Edge Cases

- What happens when the description does not start with the `"Lodgement "` prefix despite an L-prefixed reference? The description is used as-is as the sub-account (no crash; partial prefix match is not stripped).
- What happens when the description is exactly `"Lodgement "` with nothing after the prefix? The sub-account falls back to the reference (avoids empty sub-account).
- What if a reference matches the L-digit pattern but the description does not begin with `"Lodgement "`? The action is still `lodgement` (action is determined solely by the reference pattern); the sub-account is the full description.
- References like `LOYALTYU` already have established mappings — these must NOT be affected by the new lodgement rule (the lodgement regex requires digits immediately after `L`, so `LOYALTYU` is not matched).

## Requirements

### Functional Requirements

- **FR-001**: The HL journal parser MUST recognise any reference that consists of the letter `L` followed by one or more digits (and no other characters) as a lodgement transaction.
- **FR-002**: Rows identified as lodgements MUST be assigned the action type `lodgement`.
- **FR-003**: For lodgement rows, the sub-account MUST be derived from the description by stripping the literal prefix `"Lodgement "` (capital L, the word "Lodgement", one space). If the prefix is absent, the full description is used.
- **FR-004**: If stripping the `"Lodgement "` prefix results in an empty string, the sub-account MUST fall back to the reference value.
- **FR-005**: The new lodgement action MUST be added as a recognised action type in the system's action enumeration.
- **FR-006**: Lodgement transactions MUST NOT be treated as cash transactions — the sub-account is the security name, not `"Cash"`.
- **FR-007**: No existing action mappings (buy, sell, deposit, income, dividend, fee, etc.) MUST be affected by this change.
- **FR-008**: References that begin with `L` but are followed by non-digit characters (e.g., `LOYALTYU`) MUST NOT be matched as lodgements.

### Key Entities

- **Lodgement transaction**: An in-specie transfer of a named security into the account. Identified by an `L`+digits reference. Has a security name as sub-account and a monetary value representing the market value transferred.
- **Action type**: The classification of a journal event (buy, sell, deposit, income, dividend, fee, lodgement, etc.). Lodgement is a new distinct value in this enumeration.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All lodgement rows in existing historical HL CSV files (e.g., the 2018 ISA capital account lodgements journal) are processed without any parse errors — 0 error rows reported for valid lodgement inputs.
- **SC-002**: The existing passing test suite continues to pass in full — 0 regressions introduced.
- **SC-003**: A pipeline run against a journal containing only lodgement rows produces an output journal with one row per lodgement, each correctly classified.
- **SC-004**: The lodgement action appears as a distinct, queryable value in the output journal (`action = "lodgement"`), enabling downstream reporting to distinguish lodgements from purchases.

## Assumptions

- The lodgement reference pattern is always `L` followed by one or more digits with no other characters — this is consistent with the buy (`B`+digits) and sell (`S`+digits) patterns already in use.
- The description prefix to strip is always exactly `"Lodgement "` (capital L, one trailing space) — based on all observed examples in the sample data.
- Lodgements carry a monetary value (the market value of transferred securities at the time of transfer) and a quantity — both are recorded in the output journal in the same way as buy/sell rows.
- The value in lodgement rows is negative in the raw CSV (representing an outflow/cost-basis assignment) and is stored as-is without sign adjustment, consistent with buy transactions.
- Lodgements occur only in capital account journals (not income account journals), but the parser change applies to all HL-mode processing — income account journals simply do not produce lodgement rows.
- No new pipeline modes or output formats are required; this is a parser-only enhancement to the existing `consolidate_journals` HL mode.
