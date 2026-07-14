# Feature Specification: Account Performance Chart on Overview

**Feature Branch**: `016-link-real-portfolio`
**Created**: 2026-07-14
**Status**: Draft
**Input**: User description: "Link up real data from the portfolio-analysis-service to the portfolio-browser. This feature creates the first chart in the 'Overview' content page from the Dash App navigation; it should be a line-chart that is populated by the /v1/accounts/{account_name}/timeseries GET endpoint on portfolio-analysis-service. The 'Account' drop-down should list the responses from GET /v1/accounts where the text is the 'account_name' field in each element of the 'accounts' array in the response. The 'Date range' parameter should be two date pickers UI elements, a 'from' and 'to' populated by default from the same payload where 'from' is the earliest 'from_date' in the response array for the selected account. The 'to' field should default to the last business date before today. There should be an additional UI control/parameter that maps to GET /v1/timeseries/attributes (but only shown when on the 'Overview' page. This UI section should have a toggle box on/off for each available attribute with a hover tooltip of the description from the response. Once an account is selected, a valid from/to date and one or more attributes then a call to GET/v1/accounts/{account_name}/timeseries can be made mapping the chosen arguments. The response is mapped to a large line chart in the content area. The X-axis is all of the "date" fields for each element of the "entries" array; The Y-axis is a £GBP amount. There should be a legend below the graph indicating which line series and colour maps to which attribute as echoed back in the 'attributes' response array. The styling of the chart should be bold, clear and professional. Ideally with hover-over on the rendered line-chart showing a tooltip of specific date/series/value at that point."

## Clarifications

### Session 2026-07-14

- Q: Should the Overview page auto-select a default account and default attribute(s) so a chart renders immediately on load, or should it start empty/unconfigured until the user makes an explicit choice? → A: Auto-select — the first account alphabetically, with "market_value" as the default metric, so a chart renders immediately on load.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See account performance at a glance (Priority: P1)

A user opens the Overview page and immediately sees a populated performance
chart — the first account alphabetically is pre-selected with "market
value" shown by default — showing how that account has changed over time,
without needing to understand the underlying data model or make any
selection first.

**Why this priority**: This is the reason the feature exists — turning the
placeholder Overview page into a real, informative view. Nothing else in
this feature has value without this working first.

**Independent Test**: Load the Overview page and verify a line chart
renders showing real account performance data, with a legend identifying
each plotted line, and that hovering over the chart reveals the exact
date/metric/value at that point.

**Acceptance Scenarios**:

1. **Given** the user navigates to the Overview page for the first time in
   a session, **When** the page has finished fetching data, **Then** a line
   chart is displayed automatically — with no selection required — showing
   the "market value" metric for the alphabetically-first account.
2. **Given** the chart is displayed, **When** the user looks below the
   chart, **Then** a legend lists each plotted line with a distinct color
   and the name of the metric it represents.
3. **Given** the chart is displayed, **When** the user hovers over any
   point on any line, **Then** a tooltip appears showing that point's date,
   metric name, and value.
4. **Given** the chart is displayed, **When** the user views the vertical
   axis, **Then** values are presented as GBP amounts.

---

### User Story 2 - Switch which account is being viewed (Priority: P2)

A user selects a different account from the Account control and sees the
chart, date range, and attribute options update to reflect that account's
own data.

**Why this priority**: Most users have more than one account (e.g. an ISA
and a SIPP); comparing/switching between them is a core part of using a
portfolio dashboard, though the feature already delivers value for a single
account without this (P1).

**Independent Test**: Select a different account from the Account control
and verify the chart re-renders with that account's data, and that the
default date range updates to match that account's own available history.

**Acceptance Scenarios**:

1. **Given** the Overview page is showing one account's chart, **When** the
   user selects a different account, **Then** the chart updates to show
   that account's performance data instead.
2. **Given** an account has just been selected, **When** the date range
   controls are checked, **Then** the "from" date defaults to the earliest
   date for which that account has recorded data, and the "to" date
   defaults to the most recent completed business day.
3. **Given** the Account control is displayed, **When** the user opens it,
   **Then** every account available to the user is listed, identified by
   its account name.

---

### User Story 3 - Narrow or widen the date range (Priority: P3)

A user adjusts the "from" and/or "to" date to focus on a specific period of
an account's history.

**Why this priority**: Refines an already-working view (P1/P2); valuable
for drill-down analysis but not required for the feature to deliver its
core value.

**Independent Test**: Change the "from" or "to" date to a narrower window
within the account's available history and verify the chart re-renders
showing only that period.

**Acceptance Scenarios**:

1. **Given** a chart is displayed, **When** the user changes the "from" or
   "to" date to a valid date within the account's available history,
   **Then** the chart updates to show only data within the new range.
2. **Given** the date controls are displayed, **When** the user attempts to
   set a "to" date after today, or a "from" date after the "to" date,
   **Then** the system prevents the invalid selection or clearly indicates
   the range is invalid without breaking the displayed chart.

---

### User Story 4 - Choose which metrics to compare (Priority: P4)

A user turns individual metrics on or off to compare only the ones they
care about, using a tooltip to understand what each metric means before
deciding.

**Why this priority**: Adds analytical flexibility on top of an already
useful single-metric or default-metric chart; the most refined/optional
capability of the four.

**Independent Test**: Toggle a metric off and verify its line disappears
from the chart and its entry disappears from the legend; toggle it back on
and verify it reappears. Hover over a metric's toggle and verify a tooltip
describing that metric appears.

**Acceptance Scenarios**:

1. **Given** the metric toggle controls are displayed, **When** the user
   hovers over one, **Then** a tooltip describing what that metric
   represents is shown.
2. **Given** a chart is displayed with one metric plotted, **When** the
   user turns on a second metric, **Then** a second line and matching
   legend entry appear, in a distinct color from the first.
3. **Given** a chart is displayed with two or more metrics plotted, **When**
   the user turns one off, **Then** its line and legend entry disappear and
   the remaining metric(s) continue to display correctly.
4. **Given** the metric toggle controls, **When** the user navigates away
   from the Overview page to a different section, **Then** the metric
   toggle controls are no longer shown.

---

### Edge Cases

- What happens when the selected account has no recorded data at all (no
  history to chart)? Such an account SHOULD NOT be selectable, since there
  is nothing to show.
- What happens when zero metrics are toggled on? The system MUST NOT
  attempt to show a chart with no data; it MUST show a clear
  prompt/empty-state instead, consistent with the source description ("one
  or more attributes" is a precondition for fetching data).
- What happens when the chosen account/date-range/attribute combination
  produces no data points (e.g. a gap in history)? The system MUST show a
  clear empty-state message rather than a blank or broken chart area.
- What happens when the backing data service is unavailable or returns an
  error while loading accounts, metrics, or chart data? The system MUST
  show a clear error state rather than a blank or indefinitely loading page.
- What happens to a previously-chosen custom date range when the user
  switches accounts? The date range resets to the newly-selected account's
  own default range, since date ranges are specific to each account's
  available history.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Overview page MUST display an Account selector listing
  every account available to the user, identified by account name.
- **FR-001a**: On first load of the Overview page in a session, the Account
  selector MUST default to the alphabetically-first available account, and
  the "market_value" metric toggle MUST default to on, so a chart renders
  without requiring any user selection.
- **FR-002**: The Overview page MUST display a "from" date control and a
  "to" date control representing the reporting period to chart.
- **FR-003**: When an account is selected, the "from" date MUST default to
  the earliest date for which that account has any recorded history.
- **FR-004**: The "to" date MUST default to the most recently completed
  business day (i.e. not today, and not a weekend).
- **FR-005**: The Overview page MUST display a set of toggle controls, one
  per available performance metric, allowing the user to turn each metric's
  display on or off independently.
- **FR-006**: Each metric toggle MUST show a tooltip, on hover, describing
  what that metric represents.
- **FR-007**: The metric toggle controls MUST be visible only while viewing
  the Overview page, and MUST NOT appear on any other navigation section.
- **FR-008**: The system MUST retrieve and display performance data only
  once an account, a valid "from"/"to" date range, and at least one metric
  are all selected.
- **FR-009**: The performance chart MUST plot each toggled-on metric as its
  own line, with dates along the horizontal axis and GBP amounts along the
  vertical axis.
- **FR-010**: The chart MUST include a legend, positioned below the chart,
  identifying which color corresponds to which metric.
- **FR-011**: Hovering over any point on any plotted line MUST show the
  exact date, metric name, and value at that point.
- **FR-012**: The chart's visual styling MUST present a bold, clear,
  professional appearance suitable for reviewing financial data.
- **FR-013**: If the selected date range, account, or metric combination
  yields no data, the system MUST show a clear empty-state message instead
  of an empty or broken chart.
- **FR-014**: If the underlying data cannot be retrieved (service
  unavailable or returns an error), the system MUST show a clear error
  message instead of a blank or indefinitely loading page.
- **FR-015**: The system MUST NOT allow a "to" date later than today, nor a
  "from" date later than the "to" date.

### Key Entities

- **Account**: A user's investment account, identified by an account name;
  has an earliest available history date used to default the reporting
  period.
- **Performance Metric**: A named, describable financial measure (e.g.
  capital invested, market value, profit/loss) that can be toggled on or
  off for charting; carries a human-readable description shown on hover.
- **Performance Entry**: A single data point for a given date, carrying one
  value per currently-selected metric, used to plot the chart.
- **Chart Series**: The rendered representation of one metric's values over
  the selected date range, associated with a consistent color used in both
  the chart lines and the legend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view a populated performance chart immediately
  upon loading the Overview page, without performing any selection action.
- **SC-002**: A user can switch to viewing a different account's
  performance in a single interaction (one selection).
- **SC-003**: A user can determine the exact value of any plotted metric on
  any charted date by hovering over it, without leaving the Overview page.
- **SC-004**: A user can learn what a given performance metric means by
  hovering over its toggle, without navigating away from the Overview page.
- **SC-005**: 100% of metrics currently toggled on are represented in both
  the chart and the legend, each with a distinct, consistent color.
- **SC-006**: When a user changes the account, date range, or toggled
  metrics, the chart reflects the new selection without a full page reload.

## Assumptions

- Performance metric values returned for charting are already expressed in
  GBP (pounds, not pence); this feature does not perform any currency
  conversion or unit scaling — it displays exactly what is returned.
- An account with no recorded history at all is excluded from the Account
  selector, since there would be nothing to chart for it.
- Each performance metric is assigned a fixed, consistent color used
  everywhere it appears (chart line, legend), so the same metric always
  looks the same across sessions.
- This feature only displays already-computed performance data; no
  financial calculations (totals, deltas, aggregates) are performed
  client-side, consistent with the project's principle that calculations
  belong in the backing API, not the UI.
- "Most recently completed business day" follows a standard Monday-Friday
  business-day definition with no public-holiday calendar, consistent with
  how the backing service resolves its own default reporting period.
- Only one chart (this account performance chart) is in scope for this
  feature; additional charts, tables, or drill-down detail views for
  Overview or other sections are out of scope here.
