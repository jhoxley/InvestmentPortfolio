# Feature Specification: Projection Start Alignment

**Feature Branch**: `010-projection-start-alignment`  
**Created**: 2026-09-24  
**Status**: Draft  
**Input**: User description: "The projection endpoint always includes the projection start date as the first entry of each projected time series regardless of the selected periodicity. This creates an irregular, gapped response when the start date lies between periodicity dates (e.g. periodicity=month, start=2026-09-22 yields 2026-09-22 and 2026-10-01 entries). For non-daily periodicities the start-date-aligned record should be omitted and the projection should begin at the next periodicity boundary."

## Clarifications

### Session 2026-09-24

- Q: Should the projected series include a final `projection_date` entry when it is not a periodicity boundary? → A: No. Boundary-dated points only; the last entry is the last boundary on or before `projection_date`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Regular projection points for non-daily periodicity (Priority: P1)

A consumer requests an account projection with a non-daily periodicity (e.g. monthly) and a start date that falls part-way through a period. The projected series should contain only points on the periodicity boundaries, starting at the first boundary after the start date, so the series is evenly spaced and can be charted or tabulated without special handling of a leading odd-dated point.

**Why this priority**: This is the defect being fixed; without it the projected series is irregular for every non-daily request whose start date is off-boundary.

**Independent Test**: Request a monthly projection with a start date of 2026-09-22 and confirm the projected series begins at 2026-10-01 with no 2026-09-22 entry, and all subsequent entries are on month boundaries.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Monthly projection with mid-month start date omits the start-date record
  Given account "HL-ISA" with data up to 2026-09-22
  When the projection is requested with projection_date=2026-12-31, return=3Y, start=2026-09-22 and periodicity=month
  Then the 3Y projected series does not contain an entry dated 2026-09-22
  And the first entry of the 3Y projected series is dated 2026-10-01
  And each subsequent entry falls on the next month boundary

Scenario: Historical series is unaffected
  Given the same request as above
  When the response is returned
  Then the historical series still ends with the latest data point at the start date, as before this change

Scenario: Quarterly projection begins at next quarter boundary
  Given a projection request with periodicity=quarter and a start date that is not a quarter boundary
  When the response is returned
  Then the first projected entry is the first quarter boundary after the start date
  And no entry is dated at the start date
```

---

### User Story 2 - Start date on a boundary or daily periodicity is unchanged (Priority: P2)

When the start date already coincides with a periodicity boundary, or the periodicity is daily, the projected series continues to begin at the start date exactly as it does today.

**Why this priority**: Guards against regressions; the existing behaviour is correct in these cases.

**Independent Test**: Request a monthly projection with start=2026-10-01 and a daily projection with any start date; confirm the first projected entry equals the start date.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Start date on a month boundary is retained
  Given a projection request with periodicity=month and start=2026-10-01
  When the response is returned
  Then the first projected entry is dated 2026-10-01

Scenario: Daily periodicity retains the start date
  Given a projection request with periodicity=day and start=2026-09-22
  When the response is returned
  Then the first projected entry is dated 2026-09-22
```

---

### Edge Cases

- Start date is a non-business day or the period boundary falls on a non-business day: the first entry follows the same boundary-dating convention already used for later entries in that periodicity.
- The next boundary after the start date is later than the projection date: the projected series is empty rather than containing a start-date entry.
- Off-boundary `projection_date` (e.g. 2026-12-31 with monthly periodicity): no end entry is added; the series ends at the last boundary on or before it (2026-12-01).
- Multiple return scenarios are requested: every projected series is aligned in the same way.
- Start date omitted (defaults to latest data date): the same alignment rule applies to the defaulted start date.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For any non-daily periodicity, the system MUST omit the start-date entry from each projected series when the start date is not itself a periodicity boundary.
- **FR-002**: In that case, each projected series MUST begin at the first periodicity boundary after the start date.
- **FR-003**: When the start date coincides with a periodicity boundary, the system MUST include it as the first projected entry.
- **FR-004**: For daily periodicity, the system MUST continue to include the start date as the first projected entry.
- **FR-005**: Entries after the first MUST remain on consecutive periodicity boundaries with no gaps or irregular intervals.
- **FR-006**: The historical series MUST be unchanged, including its final data point at the start date.
- **FR-007**: Projected values at the retained boundary dates MUST be identical to those produced before this change; only the presence of the off-boundary start-date entry changes.
- **FR-008**: The alignment rule MUST apply uniformly to all projected series in a response.
- **FR-009**: For any non-daily periodicity, the projected series MUST contain boundary-dated entries only: no entry is added at `projection_date` unless it is itself a boundary, and the last entry is the last boundary on or before `projection_date`.

### Key Entities

- **Projected series**: Ordered set of dated projected values for a given return scenario, dated on periodicity boundaries.
- **Projection start date**: Date from which projection begins; anchors the calculation but is only shown as an entry when it is a boundary (or periodicity is daily).
- **Periodicity boundary**: A date that closes/opens a period for the selected periodicity (e.g. first of the month for monthly).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of non-daily projection requests, the interval between consecutive projected entries is a single, consistent period.
- **SC-002**: For the reference request (monthly, start 2026-09-22, projection date 2026-12-31), the first projected entry is 2026-10-01 and no entry is dated 2026-09-22.
- **SC-003**: Daily-periodicity and on-boundary requests return identical projected series to those before the change.
- **SC-004**: Projected values on retained dates are unchanged versus prior behaviour in 100% of regression comparisons.

## Assumptions

- "Non-daily periodicities" means every periodicity currently supported other than daily (e.g. month, quarter, year).
- The projection calculation itself still starts from the start date's position; only the output is trimmed.
- Boundary dating follows the convention already used by the existing periodic timeseries responses.
- No change to request parameters or to the response structure is required.
