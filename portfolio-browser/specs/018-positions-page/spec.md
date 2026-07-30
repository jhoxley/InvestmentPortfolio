# Feature Specification: Positions Page

**Feature Branch**: `018-positions-page`
**Created**: 2026-07-17
**Status**: Draft
**Input**: User description: "Populate the content displayed when navigating to the "Positions" page from the menu. This page has its data driven from the portfolio-analysis-service endpoints /v1/api/accounts/{account_name}/position, /v1/api/accounts/{account_name}/positions and /v1/api/positions/attributes. ... The controls/filters section of the 'Positions' page shares similarities to the existing 'Overview' page in how the 'Account', 'From' and 'To' drop-downs are populated. The shortcut buttons for "YtD", "1Y", "3Y", "5Y" and "All" should be replicated. ... the new page also needs the toggle buttons for each attribute to display on the graph ... and this should also be shared with the 'Overview' page ... a toggle button for "Stacked area graph" ... a multi-select drop-down list ... of position names ... if "Stacked area graph" is toggled to on/true then ONLY a single attribute can be selected ... colour palette ... high contrast/variability across up to 50 series ... default to showing only "YtD" range for the first account returned ... and all positions in the account ... a compact rendered data table ... one row for every position that has data returned and one column for each selected attribute ... paired with a 2nd column ... " (prev)" suffix ... pastel background colour depending on the ratio between the numbers on the 'from' and 'to' date."

## Clarifications

### Session 2026-07-17

- Q: When multiple attributes and multiple positions are selected
  simultaneously in line-chart mode, how should the chart differentiate
  the resulting lines, given color already encodes position (FR-015)? →
  A: Color encodes position only; each trace's legend/hover label includes
  both position and attribute name so attribute is distinguished by text,
  not a second visual channel.
- Q: Should a reporting-period shortcut's "From"-date clamp use the whole
  account's earliest recorded date, or only the earliest date among the
  positions currently selected in the position filter? → A: The whole
  account's earliest recorded date, independent of the current position
  filter — the same value Overview's own "All" shortcut already uses.
- Q: Should each position have a stable color that persists across
  selection/date-range changes, or can a position's color shift depending
  on what else is currently plotted? → A: Stable per position — each
  position is deterministically mapped to the same color everywhere it
  appears, regardless of the current selection or date range.

`/speckit-analyze` remediation (2026-07-17) resolved the following
additional issues found during cross-artifact review, without a new
interactive session:

- **Default date range on account switch (was ambiguous)**: FR-012 ties
  "YtD" explicitly to the page's default view, but FR-014/US2's "that
  account's own default range" was undefined — it could have meant "YtD
  again" or Overview's own "full recorded history" default. Resolved:
  Positions' own definition of "default date range" is **"YtD", always**
  — on first load and on every subsequent account switch alike — computed
  via the same Reporting Period Shortcut logic the "YtD" button itself
  uses (clamped to the account's earliest recorded date the same way).
  This is intentionally different from Overview's own default (full
  history), since reusing Overview's default here would silently discard
  the user's year-to-date context on every account switch, which is not
  what FR-012's "sensible default view" intent calls for on a page whose
  own explicit default *is* "YtD".
- **FR-016a's dual-label condition (was under-scoped)**: previously
  required *both* more than one attribute *and* more than one position to
  be selected before showing a "Position — Attribute" label. Corrected:
  the same color-collision ambiguity exists whenever more than one
  attribute is selected, regardless of position count (a single selected
  position with two attributes produces two same-colored, unlabeled lines
  otherwise) — see the corrected FR-016a below.
- **Attribute-aware value formatting (was unaddressed for the chart)**:
  the original Assumptions section only addressed currency-vs-plain
  formatting for the comparison table, not the chart itself, even though
  both display the same non-monetary `quantity` attribute alongside
  monetary ones. Promoted to a testable requirement — see new FR-008a
  below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See position-level performance the moment the page opens (Priority: P1)

A user clicks "Positions" in the navigation menu and, without configuring
anything, immediately sees a chart of every position's performance for the
first available account over the current year to date.

**Why this priority**: This is the page's core value — today it shows only
placeholder text. Landing on a fully populated, sensible default view is
what turns the menu entry into a usable feature at all.

**Independent Test**: Navigate to the Positions page from the menu on a
fresh session and verify a chart appears showing year-to-date data for the
alphabetically-first account, covering all of that account's positions,
with no manual interaction required.

**Acceptance Scenarios**:

1. **Given** the user navigates to the Positions page for the first time in
   a session, **When** the page finishes loading, **Then** the Account
   selector shows the first available account selected, the date range
   shows "YtD" (1st January of the current year through the most recently
   completed business day), and the position filter shows every position
   recorded for that account selected.
2. **Given** the default view has loaded, **When** the user looks at the
   chart, **Then** it displays a line for the default attribute across all
   of the account's positions within the year-to-date range.
3. **Given** the selected account has no recorded position data,
   **When** the page loads, **Then** a clear "no data" message is shown
   instead of an empty or broken chart.

---

### User Story 2 - Explore a different account or time period (Priority: P2)

A user changes the selected account and/or adjusts the date range — either
via the "From"/"To" fields or the "YtD"/"1Y"/"3Y"/"5Y"/"All" shortcut
buttons — to look at a different account's positions or a different
reporting period.

**Why this priority**: Essential for the page to be useful beyond the
initial default view, and it reuses interaction patterns users already
know from the Overview page.

**Independent Test**: With the Positions page loaded, switch to a
different account, then click each shortcut button in turn and verify the
"From"/"To" fields and the chart update correctly each time, matching the
same behavior already available on the Overview page.

**Acceptance Scenarios**:

1. **Given** the Positions page is displayed, **When** the user selects a
   different account, **Then** the position filter resets to every
   position recorded for the newly selected account, the date range resets
   to "YtD" for that account (the same default FR-012 establishes for
   initial load, clamped to the account's earliest recorded date where
   applicable), and the chart and table refresh accordingly.
2. **Given** the Positions page is displayed, **When** the user clicks
   "1Y" (or "3Y", "5Y", "All"), **Then** the "From" date updates to the
   correct computed date (clamped to the account's earliest recorded date
   where applicable), the "To" date updates to the most recently completed
   business day, and the chart and table refresh to the new range.
3. **Given** a chart refresh triggered by an account switch, date edit, or
   shortcut click is in progress, **When** the user attempts to click
   another control that would trigger a new refresh, **Then** that control
   has no effect until the current refresh finishes.

---

### User Story 3 - Choose which measures and positions to compare (Priority: P2)

A user toggles specific attributes (e.g. market value, income) on or off,
and narrows the position filter down to a subset of positions, to focus
the chart and table on exactly what they want to compare.

**Why this priority**: Without this, the page can only ever show every
position and one fixed measure — the ability to focus the view is core to
the page's analytical purpose, on par with the account/date controls.

**Independent Test**: With the Positions page loaded, toggle a second
attribute on and select a subset of positions in the multi-select filter,
and verify the chart and table update to reflect exactly the toggled
attributes and selected positions.

**Acceptance Scenarios**:

1. **Given** the Positions page is displayed, **When** the user toggles an
   attribute on or off, **Then** the chart and table refresh to include or
   exclude that attribute's data.
2. **Given** the Positions page is displayed, **When** the user selects a
   subset of positions in the multi-select filter, **Then** the chart and
   table refresh to show only the selected positions.
3. **Given** the user has deselected every attribute, **When** the page
   would otherwise refresh, **Then** a prompt to select at least one
   attribute is shown instead of an empty chart.
4. **Given** the user has deselected every position, **When** the page
   would otherwise refresh, **Then** a prompt to select at least one
   position is shown instead of an empty chart.

---

### User Story 4 - Compare each position's start and current values at a glance (Priority: P2)

A user scans a compact table below the chart to see, for every position
currently displayed, its most recent value against its value at the start
of the selected date range for each selected attribute, with a color cue
showing whether it went up or down.

**Why this priority**: Delivers a distinct, immediately useful piece of
analysis (which positions moved up vs. down over the period) that a line
chart alone doesn't make easy to scan across many positions at once.

**Independent Test**: With the Positions page loaded and a chart rendered,
verify a table appears below it with one row per plotted position, a pair
of columns per selected attribute (current value and a "(prev)" starting
value), and that the current-value column is shaded light green, light
red, or left unshaded depending on whether the value rose, fell, or held
steady over the period.

**Acceptance Scenarios**:

1. **Given** the chart is displaying data for a set of positions and
   attributes, **When** the user looks below the chart, **Then** a table
   shows one row per position that has data, with a column pair — the
   attribute's value on the "To" date, and an adjacent "(prev)" column with
   its value on the "From" date — for each selected attribute.
2. **Given** a position's "To"-date value for an attribute is higher than
   its "From"-date value, **When** the table renders, **Then** that
   attribute's current-value cell has a light green background.
3. **Given** a position's "To"-date value for an attribute is lower than
   its "From"-date value, **When** the table renders, **Then** that
   attribute's current-value cell has a light red background.
4. **Given** a position's "To"-date and "From"-date values for an
   attribute are equal, **When** the table renders, **Then** that
   attribute's current-value cell has no background shading.
5. **Given** the account, date range, attributes, or position filter
   changes, **When** the chart refreshes, **Then** the table refreshes to
   match the same data exactly — the two are never out of sync.

---

### User Story 5 - Switch between a line chart and a stacked area view (Priority: P3)

A user toggles "Stacked area graph" on to see how a single attribute is
composed across positions (e.g. how much of total market value each
position contributes), instead of viewing each position as a separate
line.

**Why this priority**: A valuable alternative visualization for
composition analysis, but the page is already useful without it (via User
Stories 1-4), and it only applies to the single-attribute case.

**Independent Test**: With exactly one attribute selected, toggle "Stacked
area graph" on and verify the chart changes from a line chart to a stacked
area chart of the same data; toggle it off and verify it reverts to a line
chart.

**Acceptance Scenarios**:

1. **Given** exactly one attribute is currently selected, **When** the
   user turns "Stacked area graph" on, **Then** the chart re-renders as a
   stacked area chart using that attribute across the selected positions.
2. **Given** "Stacked area graph" is on, **When** the user turns it off,
   **Then** the chart reverts to a standard line chart of the same data.
3. **Given** "Stacked area graph" is currently on with one attribute
   selected, **When** the user selects a second attribute, **Then**
   "Stacked area graph" is automatically turned off and the chart renders
   as a line chart with both attributes — the second attribute's selection
   is never blocked.
4. **Given** more than one attribute is currently selected, **When** the
   user looks at the "Stacked area graph" toggle, **Then** it cannot be
   switched on until only one attribute remains selected.

---

### Edge Cases

- What happens when the selected account has no ingested position data at
  all? A clear "no data" message is shown in place of the chart and table,
  consistent with how the Overview page handles a similarly data-less
  account.
- What happens when a position included in the current filter has no data
  points within the resolved date range (e.g. it was sold before the
  "From" date, or opened after the "To" date)? It is silently excluded
  from both the chart and the table — the table's row set is exactly
  "positions with data returned," not "positions selected in the filter."
- What happens when a computed shortcut date (e.g. "5Y") falls before the
  selected account's earliest recorded position data? The "From" date is
  clamped to the account's earliest recorded date, matching the existing
  Overview shortcut behavior.
- What happens when "Stacked area graph" is on and the user switches
  account or clears the position filter down to zero? The single-attribute
  constraint is unaffected by account/position changes — only the number
  of *selected attributes* controls whether the toggle may be on.
- What happens when the backing data service is unavailable or returns an
  error? The same error-state messaging already used on the Overview page
  is shown.
- What happens if the user manually edits "From"/"To" after clicking a
  shortcut, or switches attributes/positions mid-refresh? All controls
  behave as ordinary edits — there is no "locked-in" shortcut or stale
  in-flight state to reconcile; controls are simply disabled for the
  duration of any in-flight refresh (User Story 2, Acceptance Scenario 3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Positions page MUST replace its current placeholder
  content with a live view driven by real account and position data when
  navigated to from the menu.
- **FR-002**: The Positions page MUST present an Account selector
  populated from the same set of accounts available to the Overview page.
- **FR-003**: The Positions page MUST present "From"/"To" date controls
  and the five reporting-period shortcut buttons ("YtD", "1Y", "3Y", "5Y",
  "All"), presented and behaving identically to the equivalent controls on
  the Overview page, including clamping a shortcut's computed "From" date
  to the selected account's own earliest recorded date (the whole
  account's earliest date, independent of the current position filter —
  the same value Overview's own "All" shortcut already uses).
- **FR-004**: The Positions page MUST present a toggle control for each
  attribute available for positions, presented and behaving identically to
  the Overview page's own attribute toggles, even though each page's
  attribute list comes from its own data source.
- **FR-005**: The Positions page MUST present a multi-select control
  listing every position recorded for the currently selected account
  (supporting at least 50 entries), allowing the user to select any subset
  of positions, including all of them.
- **FR-006**: The Positions page MUST present a "Stacked area graph"
  toggle, unique to this page, defaulting to off.
- **FR-007**: When "Stacked area graph" is on, the chart MUST render as a
  stacked area chart of the single selected attribute across the selected
  positions.
- **FR-008**: When "Stacked area graph" is off, the chart MUST render as a
  line chart, matching the Overview page's own line-chart presentation
  style, subject to FR-008a's attribute-aware value formatting.
- **FR-008a**: Numeric values shown on the chart (axis labels, hover text)
  and in the comparison table MUST be formatted appropriately to their
  attribute's unit — currency-style (e.g. a "£" prefix, thousands
  separators) for monetary attributes (`market_value`, `income`,
  `book_cost`, `pnl`, `close_price`), and plain numeric formatting (no
  currency symbol) for `quantity`.
- **FR-009**: The "Stacked area graph" toggle MUST only be switchable on
  while exactly one attribute is currently selected.
- **FR-010**: If "Stacked area graph" is on and the user selects a second
  attribute, the system MUST automatically turn "Stacked area graph" off
  rather than blocking the attribute selection.
- **FR-011**: The "Stacked area graph" toggle MUST be disabled (not
  switchable on) at any time more than one attribute is selected.
- **FR-012**: On first navigating to the Positions page in a session, the
  system MUST default the Account selector to the first account returned,
  the date range to "YtD", and the position filter to every position
  recorded for that account.
- **FR-013**: Every change to the Account, "From" date, "To" date, a
  reporting-period shortcut, an attribute toggle, or the position filter
  MUST trigger a refreshed chart and a refreshed data table reflecting the
  new selection.
- **FR-014**: Switching the selected Account MUST reset the position
  filter to every position recorded for the newly selected account and
  reset the date range to "YtD" for that account — the same default
  FR-012 establishes for initial load (not Overview's own "full recorded
  history" default), computed via the same Reporting Period Shortcut logic
  as the "YtD" button.
- **FR-015**: The chart MUST assign each plotted position a visually
  distinct color from a palette designed for high contrast across up to 50
  concurrent series, so that no two positions are easily confused for one
  another. Color encodes position only — it does not vary by attribute.
  Each position's color MUST be stable and deterministic (e.g. derived
  from its name), so the same position keeps the same color everywhere it
  appears, regardless of the current selection or date range.
- **FR-016**: The chart MUST provide a legend mapping each color to its
  position name, remaining legible and unambiguous with up to 50
  concurrent series.
- **FR-016a**: Whenever more than one attribute is selected — regardless
  of how many positions are selected, since even a single selected
  position produces one same-colored trace per attribute — each resulting
  line's legend entry and hover label MUST identify both its position and
  its attribute (e.g. "Apple Inc — market_value") so same-colored lines
  remain distinguishable from one another by attribute, without a second
  visual encoding (e.g. line style).
- **FR-017**: Below the chart, the Positions page MUST render a data table
  with exactly one row per position for which data was returned in the
  current chart response.
- **FR-018**: For each currently selected attribute, the data table MUST
  show a pair of adjacent columns: the position's value for that attribute
  on the current "To" date, and — immediately to its right — a column
  labeled with the same attribute name plus a " (prev)" suffix, showing
  the position's value for that attribute on the current "From" date.
- **FR-019**: The "To"-date column of each attribute pair MUST be shaded
  light green when its value is greater than the paired "(prev)" value,
  light red when it is less than the paired "(prev)" value, and left
  unshaded when the two values are equal.
- **FR-020**: If zero attributes are selected, the Positions page MUST
  show the same "select at least one" empty-state guidance pattern used by
  the Overview page, in place of the chart and table.
- **FR-021**: If zero positions are selected in the position filter, the
  Positions page MUST show an equivalent "select at least one position"
  empty-state guidance, in place of the chart and table.
- **FR-022**: If the backing data service is unavailable or returns an
  error, the Positions page MUST show the same error-state messaging
  pattern used by the Overview page.
- **FR-023**: Every control capable of triggering a new chart/table
  request (Account, "From", "To", shortcuts, attribute toggles, position
  filter, "Stacked area graph") MUST be disabled for the duration of any
  refresh already in flight.
- **FR-024**: The position filter MUST remain efficient to operate with up
  to 50 listed entries (e.g. allowing the user to narrow the list by
  typing, rather than requiring them to scroll a flat list of 50 names).
- **FR-025**: A position with no data points within the resolved date
  range and current filter MUST be excluded from both the chart and the
  data table.

### Key Entities

- **Position**: A named holding (sub-account) within a selected account —
  e.g. an individual stock, fund, or "Cash" — that has its own recorded
  history of attribute values.
- **Position Attribute**: A named, chartable/tabulable measure for a
  position (e.g. market value, income, book cost, profit/loss, close
  price, quantity), each with a human-readable description.
- **Reporting Period Shortcut**: A named, fixed date-range calculation
  ("YtD", "1Y", "3Y", "5Y", "All") shared with the Overview page, that
  computes a concrete "From" date for the currently selected account.
- **Chart Visualization Mode**: A local, page-only display setting — line
  chart or stacked area chart — constrained to stacked area only when
  exactly one attribute is selected.
- **Position Comparison Row**: One data-table row for a position with
  data, holding — for each selected attribute — its "To"-date value, its
  "From"-date value, and the resulting up/down/unchanged shading.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user navigating to the Positions page for the first time
  sees a fully populated chart and table — first account, year-to-date,
  all positions — with zero configuration steps.
- **SC-002**: A user can narrow the chart and table to any combination of
  attributes and positions in at most two direct interactions (open the
  position filter and pick entries; toggle the desired attributes).
- **SC-003**: An invalid "Stacked area graph" + multi-attribute
  combination can never be produced through the UI — it is prevented or
  automatically corrected before any chart request is made, 100% of the
  time.
- **SC-004**: Users can tell, without reading any numbers, whether a
  position's value rose, fell, or held steady over the selected period,
  purely from the table's cell shading.
- **SC-005**: With up to 50 positions plotted at once, a user can still
  match any chart line to its position name via the legend without
  confusing it for a similarly colored line.
- **SC-006**: The chart and the data table always reflect the exact same
  account, date range, attribute, and position selection — they never show
  inconsistent data after any control change.

## Assumptions

- The Positions page's Account selector draws from the same accounts list
  already used by the Overview page (no separate "has position data"
  filtering beyond what the selected account's own data returns).
- The default attribute shown on first load is the same attribute Overview
  defaults to today (market value), since it is common to both pages'
  attribute sets.
- "First account returned" and "every position recorded for that account"
  follow the same alphabetical/as-returned ordering convention already
  used for Overview's default-account selection.
- Because the Account/From/To/shortcut controls and the attribute-toggle
  controls must look and behave identically between the Overview and
  Positions pages despite being sourced from different endpoints, they are
  expected to share one underlying implementation (configurable by
  endpoint per page) rather than being maintained as two separate copies.
- A position selected in the filter but with no data in the resolved date
  range (sold before "From", or opened after "To") is simply omitted from
  the chart and table, not shown with blank/zero values.
- "Stacked area graph" is local, presentation-only state — it is never
  sent to the backing data service as a query parameter.
- The `position` query parameter is always sent as the explicit list of
  currently selected positions, even when every position happens to be
  selected — the upstream API treats an explicit full list and an omitted
  parameter identically (per its own contract), so no client-side "is
  everything selected" comparison is needed purely as a query-string-size
  optimization.
