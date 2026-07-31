# Feature Specification: Performance Page

**Feature Branch**: `020-performance-page-chart`
**Created**: 2026-07-30
**Status**: Draft
**Input**: User description: "Populate the 'performance' content page by creating a line-graph output from the portfolio-analysis-service endpoint /v1/accounts/{account_name}/performance. The controls section at the top of the page should mirror the 'Overview' controls with a drop-down for all accounts, the from & to date pickers and ITD, 1Y, 3Y, 5Y, ALL shortcut buttons but no option for enabling a stacked area graph. The /v1/performance/attributes endpoint should drive the selectable measures/attributes that can be graphed. Reuse existing code and templates from the 'Overview' and 'Positions' pages where possible."

## Clarifications

### Session 2026-07-30

- Q: "ITD, 1Y, 3Y, 5Y, ALL" shortcut buttons were requested, but ITD
  (inception-to-date) and ALL (full account history) resolve to the same
  date. Should the shortcut row keep both, drop the redundant one, or keep
  the existing "YtD" wording? → A: Keep all five buttons, relabel the
  first one from "YtD" to "ITD" — ITD and All remain functionally
  identical (both resolve to the account's earliest recorded date), only
  the label changes.
- Q: Should the Performance page pair its chart with a start/end
  comparison table, like the Positions page does? → A: No — the chart and
  its controls are the entire scope of this feature, matching how the
  Overview page's own account-level chart has no accompanying table.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See account performance the moment the page opens (Priority: P1)

A user clicks "Performance" in the navigation menu and, without
configuring anything, immediately sees a chart of an account's return
measures over its full recorded history.

**Why this priority**: This is the page's core value — today it shows
only placeholder text. Landing on a fully populated, sensible default
view is what turns the menu entry into a usable feature at all.

**Independent Test**: Navigate to the Performance page from the menu on a
fresh session and verify a chart appears showing return data for the
alphabetically-first account over its full recorded history, with no
manual interaction required.

**Acceptance Scenarios**:

1. **Given** the user navigates to the Performance page for the first
   time in a session, **When** the page finishes loading, **Then** the
   Account selector shows the first available account selected, and the
   date range covers that account's full recorded history through the
   most recently completed business day.
2. **Given** the default view has loaded, **When** the user looks at the
   chart, **Then** it displays a line for the default performance measure
   across the full resolved date range.
3. **Given** the selected account has no recorded performance data,
   **When** the page loads, **Then** a clear "no data" message is shown
   instead of an empty or broken chart.

---

### User Story 2 - Explore a different account or time period (Priority: P2)

A user changes the selected account and/or adjusts the date range —
either via the "From"/"To" fields or the "ITD"/"1Y"/"3Y"/"5Y"/"All"
shortcut buttons — to look at a different account's performance or a
different reporting period.

**Why this priority**: Essential for the page to be useful beyond the
initial default view, and it reuses interaction patterns users already
know from the Overview page.

**Independent Test**: With the Performance page loaded, switch to a
different account, then click each shortcut button in turn and verify
the "From"/"To" fields and the chart update correctly each time, matching
the same behavior already available on the Overview page.

**Acceptance Scenarios**:

1. **Given** the Performance page is displayed, **When** the user selects
   a different account, **Then** the date range resets to that account's
   own full recorded history and the chart refreshes accordingly.
2. **Given** the Performance page is displayed, **When** the user clicks
   "ITD" (or "1Y", "3Y", "5Y", "All"), **Then** the "From" date updates to
   the correct computed date (clamped to the account's earliest recorded
   date where applicable), the "To" date updates to the most recently
   completed business day, and the chart refreshes to the new range.
3. **Given** a chart refresh triggered by an account switch, date edit, or
   shortcut click is in progress, **When** the user attempts to click
   another control that would trigger a new refresh, **Then** that
   control has no effect until the current refresh finishes.

---

### User Story 3 - Choose which return measures to display (Priority: P2)

A user toggles specific performance measures (e.g. ITD, 1Y, 5Y) on or off
to focus the chart on exactly the return metrics they want to see,
including more than one at once.

**Why this priority**: Without this, the page can only ever show one
fixed measure — the ability to compare multiple return measures at a
glance is core to the page's analytical purpose.

**Independent Test**: With the Performance page loaded, toggle a second
measure on and verify the chart updates to show an additional line for
that measure without affecting the others.

**Acceptance Scenarios**:

1. **Given** the Performance page is displayed, **When** the user toggles
   a measure on or off, **Then** the chart refreshes to include or
   exclude that measure's line.
2. **Given** more than one measure is toggled on, **When** the chart
   renders, **Then** each toggled measure is shown as its own
   distinguishable line on the same chart.
3. **Given** the user has deselected every measure, **When** the page
   would otherwise refresh, **Then** a prompt to select at least one
   measure is shown instead of an empty chart.

---

### Edge Cases

- What happens when the selected account has no ingested position-ladder
  data at all (performance is derived from it)? A clear "no data" message
  is shown in place of the chart, consistent with how the Overview page
  handles a similarly data-less account.
- What happens when a toggled-on measure (e.g. "5Y") has insufficient
  history to be computed for some of the earlier dates in the resolved
  range? Those dates are simply absent from that measure's line — no
  error, no broken chart, and the other toggled measures are unaffected.
- What happens when a computed shortcut date (e.g. "5Y") falls before the
  selected account's earliest recorded position-ladder date? The "From"
  date is clamped to the account's earliest recorded date, matching the
  existing Overview shortcut behavior.
- What happens when the backing data service is unavailable or returns an
  error, for either the performance data or the measure metadata? The
  same error-state messaging already used on the Overview page is shown.
- What happens if the user manually edits "From"/"To" after clicking a
  shortcut, or switches measures mid-refresh? All controls behave as
  ordinary edits — there is no "locked-in" shortcut or stale in-flight
  state to reconcile; controls are simply disabled for the duration of
  any in-flight refresh (User Story 2, Acceptance Scenario 3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Performance page MUST replace its current placeholder
  content with a live view driven by real account performance data when
  navigated to from the menu.
- **FR-002**: The Performance page MUST present an Account selector
  populated from the same set of accounts available to the Overview page.
- **FR-003**: The Performance page MUST present "From"/"To" date controls,
  presented and behaving identically to the equivalent controls on the
  Overview page.
- **FR-004**: The Performance page MUST present five reporting-period
  shortcut buttons — "ITD", "1Y", "3Y", "5Y", "All" — where "ITD" and
  "All" both compute the account's full recorded history (the same value)
  and the other three match the Overview page's own computation. "ITD"
  takes the position and role of Overview's "YtD" button but with
  different behavior (full history, not year-to-date).
- **FR-005**: The Performance page MUST NOT present a "Stacked area
  graph" toggle or any other chart-mode control — it always renders a
  standard line chart.
- **FR-006**: The Performance page MUST present a toggle control for each
  performance measure returned by the measure-metadata endpoint,
  presented and behaving identically in style to the Overview page's own
  attribute toggles, even though this page's measure list comes from its
  own data source.
- **FR-007**: Users MUST be able to toggle more than one performance
  measure on at the same time, with each toggled-on measure rendered as
  its own distinguishable line on the chart.
- **FR-008**: On first navigating to the Performance page in a session,
  the system MUST default the Account selector to the first account
  returned, the date range to that account's full recorded history
  ("ITD"), and exactly one performance measure toggled on.
- **FR-009**: Switching the selected Account MUST reset the date range to
  the newly selected account's own full recorded history ("ITD") and
  refresh the chart.
- **FR-010**: Every change to the Account, "From" date, "To" date, a
  reporting-period shortcut, or a measure toggle MUST trigger a refreshed
  chart reflecting the new selection.
- **FR-011**: If zero performance measures are toggled on, the Performance
  page MUST show the same "select at least one" empty-state guidance
  pattern used by the Overview page, in place of the chart.
- **FR-012**: If no performance data is available for the selected
  account and date range, the Performance page MUST show the same
  "no data" empty-state messaging pattern used by the Overview page.
- **FR-013**: If the backing data service is unavailable or returns an
  error — whether fetching performance data or measure metadata — the
  Performance page MUST show the same error-state messaging pattern used
  by the Overview page.
- **FR-014**: A performance measure with insufficient history to be
  computed for a given date within the resolved range MUST simply be
  absent from that measure's line at that date, without causing an error
  or preventing the rest of the chart from rendering.
- **FR-015**: The "From" date picker MUST NOT allow selecting a date
  later than the current "To" date, matching the equivalent behavior on
  the Overview and Positions pages.
- **FR-016**: Performance measure values shown on the chart (axis labels,
  hover text) MUST be formatted as percentage returns, distinguishing
  this chart from the Overview and Positions pages' currency-formatted
  values.
- **FR-017**: Every control capable of triggering a new chart request
  (Account, "From", "To", shortcuts, measure toggles) MUST be disabled
  for the duration of any refresh already in flight, matching the
  equivalent behavior on the Positions page.

### Key Entities

- **Performance Measure**: A named, chartable return metric for an
  account (e.g. ITD, ITD (Ann.), 1Y, 3Y, 5Y), each with a human-readable
  description, sourced from the measure-metadata endpoint.
- **Performance Entry**: A single date plus the value of each requested
  performance measure on that date; a measure is simply absent from an
  entry when it is not yet computable for that date.
- **Account**: A named investment account, the same entity already used
  by the Overview and Positions pages.
- **Reporting Period Shortcut (Performance variant)**: A named, fixed
  date-range calculation ("ITD", "1Y", "3Y", "5Y", "All") that computes a
  concrete "From" date for the currently selected account; shares its
  computation logic with the Overview/Positions pages' own shortcuts,
  except "ITD" (in place of "YtD") always resolves to the account's full
  recorded history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user navigating to the Performance page for the first
  time sees a fully populated chart — first account, full recorded
  history, one default return measure — with zero configuration steps.
- **SC-002**: A user can display any combination of the available return
  measures on the same chart with one toggle interaction per measure.
- **SC-003**: Switching accounts or adjusting the date range (via typed
  dates or a shortcut button) updates the displayed chart with no
  additional configuration steps, matching the interaction cost already
  familiar from the Overview page.
- **SC-004**: An account or period with no computable performance data
  shows a clear "no data" message instead of a blank or broken chart,
  100% of the time.
- **SC-005**: A user already familiar with the Overview page's Account
  and date-range controls needs no new learning to operate the
  equivalent controls on the Performance page.

## Assumptions

- The Performance page's Account selector draws from the same accounts
  list already used by the Overview page (no separate "has performance
  data" filtering beyond what the selected account's own data returns).
- "First account returned" follows the same alphabetical/as-returned
  ordering convention already used for Overview's default-account
  selection.
- The default performance measure shown on first load is the first
  measure returned by the measure-metadata endpoint (expected to be
  "ITD"), mirroring Overview's single-default-toggle convention.
- Because the Account/From/To/shortcut controls and the toggle-based
  measure-selection control must look and behave similarly to their
  Overview/Positions counterparts despite being sourced from a different
  endpoint, they are expected to reuse the existing shared implementation
  (configurable per page) rather than being maintained as a separate
  copy — consistent with the same assumption already recorded for the
  Positions page.
- The Performance page has no accompanying data table, multi-select
  filter, or stacked-area/chart-mode control — its scope is the line
  chart and its controls only (per Clarifications).
- "ITD" and "All" are two labeled buttons that intentionally compute the
  same date (the account's full recorded history) — this redundancy is
  accepted as-is per Clarifications, not resolved by removing either
  button.
- If the measure-metadata endpoint were ever to return zero measures (not
  expected — its own contract fixes five named measures), FR-008's
  "exactly one performance measure toggled on" default simply has nothing
  to toggle on; the page falls back to the same "select at least one
  measure" empty state FR-011 already defines, rather than being treated
  as an error.
