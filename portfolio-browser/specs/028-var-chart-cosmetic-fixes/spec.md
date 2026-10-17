# Feature Specification: Value at Risk Chart Cosmetic Fixes

**Feature Branch**: `028-var-chart-cosmetic-fixes`
**Created**: 2026-10-17
**Status**: Draft
**Input**: User description: "Apply further cosmetic changes to the UI. For the 'Value at Risk' section rather than have up to 3 separate tables for the confidence interval (95, 97.5, 99%) have a single table with 1-3 value columns, shown/hidden depending on whether the metric is displayed. Currently this statistic table is off the right of the display due to the graph legend positioning; move the graph legend to be below the chart. For the VaR chart the percentage option doesn't render effectively as the 'realized PnL' remains in £ amounts thus the relatively small % values are too close to zero and render as a seemingly flat line. If the % VaR option is enabled then either realized PnL needs to become realized return or if not available, hidden so the graph scale effectively. The two VaR charts are missing captions so it isn't clear what they represent. Add captions ahead of each graph indicating what it represents."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the Backtest Summary Without It Being Pushed Off-Screen (Priority: P1)

Someone reviewing the Value at Risk section's reliability summary currently finds the
statistics panel pushed off the right edge of the display, because the chart's legend
renders inside the same horizontal space the panel needs. They want the legend moved out
of the way so the summary panel is always visible.

**Why this priority**: This is an outright visibility bug — the information the backtest
panel exists to show is currently inaccessible without scrolling or resizing, which is more
severe than any purely decorative issue in this feature.

**Independent Test**: Open the Risk page's Value at Risk section with any account that has
a completed calculation; verify the chart's legend appears below the chart (not beside or
inside the plot area) and the backtest summary panel is fully visible within the page's
normal width.

**Acceptance Scenarios**:

```gherkin
Scenario: The chart legend no longer overlaps the summary panel's space
  Given I am viewing the Value at Risk section's main chart
  Then the chart's legend is positioned below the chart, not to its right or overlapping it

Scenario: The backtest summary panel is fully visible
  Given I am viewing the Value at Risk section at a normal desktop window width
  Then the backtest summary panel is entirely visible without horizontal scrolling
```

---

### User Story 2 - One Backtest Table Instead of Up to Three (Priority: P1)

Someone comparing the reliability of the 95%, 97.5%, and 99% confidence levels currently
sees up to three separate small tables, one per selected level, each repeating the same row
labels. They want one table whose rows are the reliability statistics and whose columns are
the selected confidence levels, so the same figure is easy to compare across levels at a
glance.

**Why this priority**: This is the main structural change requested and materially improves
how comparable the figures are — equal in importance to fixing the legend-overlap bug,
since both are needed before the panel is genuinely usable.

**Independent Test**: With two or three confidence levels selected, verify a single table
renders with one row per reliability statistic and one column per selected confidence
level; deselecting a level removes its column without leaving an empty table or any other
visual artifact.

**Acceptance Scenarios**:

```gherkin
Scenario: One table shows every selected confidence level as a column
  Given two confidence levels are selected
  Then one table is shown with one column per selected level and one row per statistic
  And no separate table exists per confidence level

Scenario: Columns follow the current selection
  Given the backtest table is showing three confidence-level columns
  When I deselect one confidence level
  Then that level's column no longer appears in the table
  And the remaining columns' values are unchanged

Scenario: A single selected level still renders as a one-column table
  Given only one confidence level is selected
  Then the table shows exactly one value column for that level
```

---

### User Story 3 - A Readable Chart When Viewing Value at Risk as a Percentage (Priority: P2)

Someone switches the Value at Risk chart's units from money to percentage, expecting to
see the risk forecast line clearly against the realised outcome. Instead, the realised
profit/loss bars — still plotted in pounds — dwarf the percentage-scale forecast line,
compressing it into what looks like a flat line at zero.

**Why this priority**: This makes an entire display mode of the chart effectively useless,
but the page is still usable in its default (money) mode, so it ranks below the two
outright display-breaking issues above.

**Independent Test**: Open the Value at Risk chart in its default money view, then switch
units to percentage; verify the realised profit/loss bars either convert to a matching
percentage scale or are removed from view, and the percentage forecast line is clearly
readable against the chart's y-axis (not compressed near zero by a mismatched series).

**Acceptance Scenarios**:

```gherkin
Scenario: Switching to percentage units no longer flattens the forecast line
  Given the chart is showing realised profit/loss in money alongside the forecast line
  When I switch the chart's units to percentage
  Then the realised profit/loss series is either shown on the same percentage scale as the
    forecast line, or removed from the chart entirely
  And the percentage forecast line's shape is clearly readable, not compressed near zero

Scenario: Switching back to money restores the original view
  Given the chart is in percentage units with realised profit/loss hidden or rescaled
  When I switch the chart's units back to money
  Then the realised profit/loss bars reappear in money terms exactly as before
```

---

### User Story 4 - Know What Each Chart Represents (Priority: P3)

Someone looking at the Value at Risk section's two charts — the main profit/loss-versus-
forecast chart and the linked market-value chart beneath it — currently has no on-screen
explanation of what each one shows. They want a short caption above each chart telling them
what it represents.

**Why this priority**: This is a pure comprehension aid on top of charts that already work
once the issues above are fixed — valuable, but the least urgent of the four.

**Independent Test**: Open the Value at Risk section; verify a short caption appears above
the main chart describing it as the realised profit/loss versus the risk forecast, and a
second caption appears above the linked chart describing it as the account's market value
and proxy/rescaling share over the same period.

**Acceptance Scenarios**:

```gherkin
Scenario: Each chart has an explanatory caption above it
  Given I am viewing the Value at Risk section
  Then a caption appears directly above the main chart explaining that it shows realised
    profit/loss against the Value at Risk (and, if shown, Expected Shortfall) forecast
  And a caption appears directly above the linked chart explaining that it shows the
    account's total market value and its proxied/rescaled share over the same period
```

---

### Edge Cases

- **No confidence level selected**: cannot occur — an existing safeguard always keeps at
  least one confidence level selected, so the combined backtest table always has at least
  one column.
- **A statistic that is "not enough observations" for one confidence level but defined for
  another**: each column shows its own value or placeholder independently; one column's
  placeholder does not affect another column's figure.
- **Percentage units with Expected Shortfall also shown**: the Expected Shortfall overlay
  line is already percentage-scaled when units are percentage, so it is unaffected by this
  change; only the realised profit/loss series is hidden or rescaled.
- **Percentage units when no percentage-equivalent of realised profit/loss is available**:
  the realised profit/loss series is hidden entirely (per the user's own stated fallback)
  rather than shown at a misleading or arbitrary scale.
- **Very narrow (tablet-width) viewports**: the legend's new position and the combined
  table must remain readable without overlapping other content, consistent with this
  project's existing tablet-width usability standard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Value at Risk section's main chart MUST render its legend below the
  chart rather than beside or overlapping the plot area.
- **FR-002**: The backtest summary panel MUST be fully visible within the page's normal
  width once FR-001 is applied, with no part of it pushed outside the visible area.
- **FR-003**: The Value at Risk section MUST present its reliability statistics (exceptions
  observed/expected, both p-values, the pass/fail zone, mean VaR, and VaR stability) as a
  single table whose columns are the currently selected confidence levels, rather than one
  separate table per confidence level.
- **FR-004**: Changing which confidence levels are selected MUST add or remove that level's
  column from the combined table immediately, without requiring a page reload.
- **FR-005**: When the chart's units are set to percentage, the realised profit/loss series
  MUST be shown on a percentage scale consistent with the forecast line, or hidden entirely
  if no percentage-equivalent value is available, rather than remaining in money terms
  alongside a percentage-scaled forecast line.
- **FR-006**: Switching the chart's units back to money MUST restore the realised
  profit/loss series in money terms exactly as it appeared before switching to percentage.
- **FR-007**: A caption MUST appear directly above the main chart describing it as showing
  realised profit/loss against the Value at Risk forecast (and Expected Shortfall, when
  shown).
- **FR-008**: A caption MUST appear directly above the linked chart describing it as
  showing the account's total market value and its proxied/rescaled share over the same
  period.
- **FR-009**: This feature MUST NOT change the underlying Value at Risk, backtest, or
  market-value calculations — only how the existing figures are laid out, combined, and
  labelled.

### Key Entities

- **Combined Backtest Table**: The single table replacing the former one-table-per-
  confidence-level layout; one row per reliability statistic, one column per currently
  selected confidence level.
- **Chart Caption**: The short, static explanatory text shown above each of the Value at
  Risk section's two charts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view the full backtest summary panel, including every selected
  confidence level's figures, without any part of it being hidden or requiring horizontal
  scrolling.
- **SC-002**: Comparing the same reliability statistic across two or three confidence
  levels requires reading one table, not switching between separate tables.
- **SC-003**: When viewing the chart in percentage units, a user can visually distinguish
  the forecast line's shape without it being compressed by a mismatched-scale series.
- **SC-004**: Each of the two Value at Risk charts has a caption, directly above it,
  containing specific descriptive text about what that chart shows — verifiable by
  inspection, rather than relying on a subjective read of whether a user "understood" it.

## Assumptions

- The "up to 3" tables referred to correspond to the three confidence levels the service
  currently reports (95%, 97.5%, 99%); the combined table's column count simply tracks
  however many levels the service reports and the user has selected, so this remains
  correct if that set ever changes.
- No percentage-equivalent of realised profit/loss is currently available from the
  underlying data; the realised profit/loss series is therefore hidden (not rescaled) when
  percentage units are selected, per the user's own stated fallback. If a percentage-return
  figure becomes available from the underlying service in the future, showing it instead of
  hiding the series would be a reasonable enhancement, but is out of scope here.
- The chart's legend moves to a horizontal, centered position below the chart, consistent
  with the legend placement already used by this project's other charts (Performance,
  Projection, Positions).
- Captions are short, static, descriptive text (not interactive), consistent with how
  explanatory text is already used elsewhere on this page (e.g. empty-state messages).
