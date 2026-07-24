# Feature Specification: Overview Position Visualizations

**Feature Branch**: `019-overview-position-visuals`
**Created**: 2026-07-17
**Status**: Draft
**Input**: User description: "Create additional visualizations on the 'Overview' page in the UI. On a row below the current 'Account Performance' line chart split it into a 50:50 horizontal layout where the left-hand side would be a pie-chart rendering of the position-level data for the given account and as-of the chosen 'To' date. The data comes from the /v1/api/account/{account_name}/position end point setting the start/end date to the same date and the attribute is 'market_value' with no position elements specified. The pie chart rendering should therefore give a % weight for the positions as of the most recent date in the line chart. The right-hand side of the same row in the content area should show a compact table of 10 rows, the first 5 being the highest 'pnl' positions for the same, 'to' date and the bottom 5 rows being the lowest 'pnl' positions for the same date. There should be a gradient fill where the first row is bright, full green fading towards very pale green on row 5; row 6 is a very pale blue progressing to a full, bright blue on row-10 for the lowest pnl position. This table should be captioned as "Biggest winners and losers". Alongside the pnl for each row also include the "book_cost" to quantify the pnl relative to position sizing"

## Clarifications

### Session 2026-07-17

- Q: How does a user identify which pie slice belongs to which position,
  given accounts can have up to ~50 positions? → A: Hybrid — direct
  on-slice text labels for the largest slices (any slice representing at
  least 5% of the account's total market value), plus a hover tooltip on
  every slice (including small, unlabeled ones) showing its exact position
  name, market value, and percentage.
- Q: Should the pie chart and winners/losers table always stay
  side-by-side, or stack vertically at narrow (tablet) viewport widths? →
  A: Stack vertically (pie chart above table) below a tablet-width
  breakpoint, matching the same responsive-grid convention already used
  elsewhere in the app shell, rather than squeezing both side-by-side down
  to an illegible width.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See portfolio composition at a glance (Priority: P1)

A user viewing the Overview page's account performance chart wants to see
how their account's value is currently divided across its individual
holdings, as of the same "To" date already shown above, without navigating
to another page.

**Why this priority**: Composition ("what am I holding, and how much of
each?") is one of the most fundamental questions a portfolio dashboard
answers, and today the Overview page shows performance over time but never
a snapshot of current makeup.

**Independent Test**: With the Overview page's account performance chart
already showing data, verify a pie chart appears below it showing each
position's share of the account's total market value as of the currently
selected "To" date, and that changing the account or the "To" date updates
the pie chart's slices accordingly.

**Acceptance Scenarios**:

1. **Given** the Overview chart is displaying an account's performance,
   **When** the user looks at the row below it, **Then** a pie chart is
   shown with one slice per position, sized by that position's share of
   the account's total market value on the currently selected "To" date,
   with the position name labeled directly on any slice of at least 5%
   share, and every slice's exact name/value/percentage available on
   hover.
2. **Given** the pie chart is displayed, **When** the user changes the
   selected account, **Then** the pie chart refreshes to show that
   account's own position weights as of its own current "To" date.
3. **Given** the pie chart is displayed, **When** the user changes the
   "To" date, **Then** the pie chart refreshes to show position weights as
   of the newly selected date.
4. **Given** the selected account has no recorded position data as of the
   "To" date, **When** the page renders, **Then** a clear "no data"
   message is shown in place of the pie chart.

---

### User Story 2 - Identify the biggest winners and losers (Priority: P2)

A user wants to quickly see which of their positions have gained the most
and which have lost the most, as of the same "To" date, without manually
scanning every position.

**Why this priority**: This is a distinct, high-value analytical question
("what's driving my results?") that the composition view (User Story 1)
doesn't answer — valuable on its own, but naturally the second half of the
same row once the pie chart exists.

**Independent Test**: With the Overview page's account performance chart
already showing data, verify a 10-row table captioned "Biggest winners and
losers" appears to the right of the pie chart, listing the 5
highest-profit and 5 lowest-profit (most-loss) positions as of the "To"
date, each showing its profit/loss and book cost, with the row background
shading from bright green (biggest winner) through pale green, then pale
blue through bright blue (biggest loser).

**Acceptance Scenarios**:

1. **Given** the Overview chart is displaying an account's performance,
   **When** the user looks at the row below it, **Then** a table captioned
   "Biggest winners and losers" is shown to the right of the pie chart,
   with up to 10 rows.
2. **Given** the account has 10 or more positions with a recorded
   profit/loss value on the "To" date, **When** the table renders,
   **Then** the first 5 rows are that date's 5 highest profit/loss
   positions in descending order, and the last 5 rows are that date's 5
   lowest profit/loss positions in ascending-badness order (the single
   worst position last), with no position appearing twice.
3. **Given** the table is displaying its 10 rows, **When** the user looks
   at the row backgrounds, **Then** row 1 is bright/full green, shading
   progressively paler through row 5, row 6 is pale blue, and shading
   progressively brighter/fuller through row 10.
4. **Given** a row in the table, **When** the user looks at it, **Then**
   it shows that position's name, its profit/loss value, and its book
   cost for the same "To" date, so the profit/loss can be judged relative
   to the size of the position.
5. **Given** the account has fewer than 10 positions with a recorded
   profit/loss value on the "To" date, **When** the table renders,
   **Then** every such position appears exactly once (no row is left
   blank and no position is duplicated to pad the table to 10 rows).
6. **Given** the user changes the selected account or the "To" date,
   **When** the change is applied, **Then** the table refreshes to reflect
   the newly selected account/date's own biggest winners and losers.

---

### Edge Cases

- What happens when the account's total market value on the "To" date is
  zero or the account holds no positions at all? Both the pie chart and
  the winners/losers table show a "no data" message instead of an empty or
  broken visualization (consistent with the existing chart's own
  empty-state handling).
- What happens when a position's market value on the "To" date is zero or
  negative (e.g., a data anomaly)? It is excluded from the pie chart's
  slices, since a non-positive share cannot be meaningfully drawn as a
  slice of a whole.
- What happens when a position exists in the account but has no recorded
  profit/loss (or book cost) value on the "To" date (e.g., it was sold
  before, or opened after, that date)? It is excluded from the
  winners/losers table, the same way a position without data is already
  excluded elsewhere in this dashboard.
- What happens when two or more positions are tied on profit/loss right at
  the boundary between the top 5 and bottom 5? Ties are broken
  consistently (e.g., alphabetically by position name) so the same 10 (or
  fewer) positions and their order do not change from one refresh to the
  next without an underlying data change.
- What happens if the account has so few positions that the same position
  would otherwise qualify for both the "highest" and "lowest" groups (very
  small accounts)? Each position appears exactly once — never twice (see
  Acceptance Scenario 5 above). The qualifying positions are split as
  evenly as possible between the two groups; if the total is odd, the
  extra position joins the "highest profit/loss" (winners) group, so the
  higher-`pnl` half is never smaller than the lower-`pnl` half.
- What happens while the user is on a different section of the app
  (Positions, Performance, Income) or before the account performance chart
  has finished its own initial load? Neither new visualization is shown
  until the Overview chart's own account/"To" date are known, consistent
  with how the existing chart itself only renders once that data is ready.
- What happens if the user has deselected every performance-chart metric,
  so the chart above shows its own "select at least one metric" prompt?
  The pie chart and winners/losers table are unaffected and continue to
  render normally — they depend only on the selected account and "To"
  date, never on which metrics are toggled (FR-010).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Overview page MUST display a new row below the existing
  account performance chart, split into two equal-width halves (pie chart
  left, winners/losers table right) at desktop widths.
- **FR-001a**: Below a tablet-width breakpoint, the two halves MUST stack
  vertically (pie chart above the winners/losers table) instead of
  remaining side-by-side, consistent with the project's existing
  responsive-layout convention and its requirement that pages stay usable
  at common desktop and tablet widths.
- **FR-002**: The left half of the new row MUST show a pie chart with one
  slice per position held by the selected account, sized by that
  position's market value as a share of the account's total market value
  on the currently selected "To" date.
- **FR-002a**: Every slice representing at least 5% of the account's
  total market value MUST show its position name directly on (or
  immediately next to) the slice. Every slice, regardless of size, MUST
  reveal its exact position name, market value, and percentage share on
  hover (or the equivalent touch interaction), so smaller/unlabeled slices
  remain individually identifiable on demand.
- **FR-003**: The pie chart MUST use the account's market value on the
  "To" date only (a single-date snapshot), not a range — it is unaffected
  by the "From" date.
- **FR-004**: The pie chart MUST refresh whenever the selected account or
  the selected "To" date changes.
- **FR-005**: The right half of the new row MUST show a table captioned
  "Biggest winners and losers".
- **FR-006**: The winners/losers table MUST list, for the selected
  account and the currently selected "To" date, the 5 positions with the
  highest profit/loss (rows 1-5, highest first) and the 5 positions with
  the lowest profit/loss (rows 6-10, closest-to-zero-or-best-of-the-losers
  first, worst last) — 10 rows in total when at least 10 qualifying
  positions exist.
- **FR-007**: Each row of the winners/losers table MUST show the
  position's name, its profit/loss value, and its book cost for the same
  "To" date.
- **FR-008**: The winners/losers table's row backgrounds MUST follow a
  gradient: row 1 the brightest/fullest green, fading progressively paler
  through row 5; row 6 the palest blue, strengthening progressively
  through row 10, the brightest/fullest blue.
- **FR-009**: The winners/losers table MUST refresh whenever the selected
  account or the selected "To" date changes.
- **FR-010**: Neither the pie chart nor the winners/losers table is
  affected by the "From" date or by which performance-chart metrics are
  currently toggled on — both are always based on market value (pie) or
  profit/loss and book cost (table) as of the "To" date, regardless of
  those other controls.
- **FR-011**: If the selected account has no recorded position data as of
  the "To" date, both the pie chart and the winners/losers table MUST show
  a "no data" message instead of an empty or broken visualization.
- **FR-012**: A position with no recorded market value on the "To" date
  MUST be excluded from the pie chart; a position with no recorded
  profit/loss value on the "To" date MUST be excluded from the
  winners/losers table.
- **FR-013**: If fewer than 10 positions qualify for the winners/losers
  table, it MUST show exactly one row per qualifying position (no blank
  rows, no position listed twice), splitting them as evenly as possible
  between the winners and losers groups (an odd leftover position joins
  the winners group), and applying the same gradient direction across
  however many rows are shown.
- **FR-014**: If the backing data service is unavailable or returns an
  error while loading either visualization, the affected visualization
  MUST show the same error-state messaging pattern already used elsewhere
  on the Overview page.

### Key Entities

- **Position Weight Slice**: One pie-chart slice, representing a single
  position's market value as a percentage of its account's total market
  value on the selected "To" date — labeled directly when its share is at
  least 5%, otherwise identifiable via hover.
- **Position Performance Rank Row**: One row of the winners/losers table,
  holding a position's name, its profit/loss value, its book cost value,
  its rank (1st highest through 5th highest, or worst through 5th-worst),
  and the resulting gradient shade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see their account's current position weights and
  its 5 biggest winners and 5 biggest losers without leaving the Overview
  page or performing any additional navigation.
- **SC-002**: Both new visualizations always reflect the exact same
  account and "To" date as the performance chart above them — switching
  either never leaves one visualization showing stale data.
- **SC-003**: A user can distinguish winning from losing positions in the
  table purely by row color (green vs. blue), and gauge relative rank
  purely by shade intensity, without reading any numbers.
- **SC-004**: An account with no position data, or a "To" date before any
  position existed, shows a clear message rather than a blank or broken
  area, 100% of the time.

## Assumptions

- Both new visualizations are scoped to the Overview page only — no
  change to the Positions, Performance, or Income pages.
- "Position-level data" for both visualizations includes every holding the
  account has recorded for the "To" date, including a cash balance where
  one is tracked as its own position (consistent with how positions are
  already modeled elsewhere in this dashboard).
- The winners/losers table ranks strictly by each position's absolute
  profit/loss value on the "To" date (not profit/loss as a percentage of
  book cost) — book cost is shown alongside purely as context for judging
  the profit/loss figure's significance, not used to determine rank or
  which 10 positions are shown.
- Specific colors (exact shades of green/blue) are a visual-design detail;
  the requirement is the ordinal gradient behavior described (brightest
  winner → palest winner, palest loser → brightest loser), not particular
  color values.
- Ties in profit/loss at the top-5/bottom-5 boundary are broken by
  position name so results are stable and reproducible between refreshes
  of the same underlying data.
- The pie chart shows every qualifying position as its own slice, however
  small its share — it does not group small positions into a combined
  "Other" slice. This matches the literal request (no position filter is
  applied) and keeps the chart a direct, complete picture of composition;
  accounts with many small holdings may show correspondingly many thin
  slices, which is an accepted visual trade-off rather than a functional
  gap.
