# Feature Specification: Risk Page Cosmetic Cleanup

**Feature Branch**: `027-risk-page-cleanup`
**Created**: 2026-10-17
**Status**: Draft
**Input**: User description: "Various cosmetic changes are needed for the 'Risk' page. Firstly, the tabbed browsing element should be removed and a single, longer page adopted that has the histogram features first then the 'Value at Risk' section. Secondly for the histogram section the graph and the statistics table should align. If the graph is in % then so should the table - is 8.08 mean for the 3Y HL-ISA really 0.0808%? Thirdly, For the graph the median is evident enough by the visual display so remove the line annotation for it and retain only the one for the mean. They tend to be close enough that they overlap and are unclear. Fourthly, ensure the horizontal scale on the graph is consistent with the median/mean/min/max statistics - are the graph with -1%,-2%,-3% the absoluate values or are they -1% from the mean (if that were 0.08% and 1SD were 1.07% then the mark should be at -0.99%). Fifthly, make the range 1Y/3Y/5Y controls for the histogram sync with the VaR display. Do not have two overlapping sets of parameter controls, Sixth, follow a consistent visual style for the statistics table and summary under the 'Value at Risk' section and the histogram."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One Continuous Risk Page Instead of Tabs (Priority: P1)

Someone reviewing an account's risk currently has to click between a "Return Histogram" tab and
a "Value at Risk" tab to see the two related views, and can easily miss that the second one
exists. They want a single page where scrolling down reveals the histogram first, followed by the
Value at Risk content, so both are visible as one continuous story without extra clicks.

**Why this priority**: This is the structural change every other change in this feature sits on
top of — the unit fix, the control sync, and the shared visual style all assume a single page
rather than two independently-rendered tab panels.

**Independent Test**: Open the Risk page and verify there is no tab control; the return histogram
section is visible first, and scrolling down reveals the Value at Risk section below it on the
same page, both backed by live data.

**Acceptance Scenarios**:

```gherkin
Scenario: The tabbed layout is gone
  Given I am on the Risk page
  Then there is no tab control separating the histogram and the Value at Risk content
  And both sections are present on the same page

Scenario: The histogram appears before the Value at Risk section
  Given I am on the Risk page with data loaded
  Then the return histogram chart and its statistics appear above the Value at Risk content
  When I scroll down
  Then the Value at Risk chart and backtest summary come into view below the histogram section

Scenario: Shared page-level controls still apply to both sections
  Given I am on the Risk page
  Then the account selector remains visible and continues to apply to both sections
```

---

### User Story 2 - Statistics Table Matches the Chart's Units (Priority: P1)

Someone reading the histogram's statistics table sees a "mean" value of, for example, "808" next
to a chart whose x-axis is labelled in percent, where that same mean appears at the "8.08%" mark.
They want the table to show "8.08%" so the two numbers agree and the figures are not
misinterpreted (e.g. mistaking 808 for 0.0808%).

**Why this priority**: This is a correctness/trust problem, not just a styling one — the two
numbers currently disagree about the same statistic, which can lead to a wrong read of how
volatile an account actually is.

**Independent Test**: Open the Risk page for an account with a non-zero mean return; verify the
statistics table shows the mean (and every other return-based statistic) as a percentage value
matching the chart's x-axis scale, with a "%" shown so the unit is unambiguous.

**Acceptance Scenarios**:

```gherkin
Scenario: Table values are shown in percent, matching the chart
  Given the histogram chart's x-axis is labelled in percent
  And the chart draws its mean reference line at a given x-axis position, e.g. "8.08%"
  Then the statistics table's "mean" row shows "8.08%", not an unlabeled raw number
  And every other return-based row (median, minimum, maximum, standard deviation) is likewise
    shown in percent with a visible "%" unit

Scenario: Non-return statistics are unaffected
  Given the statistics table includes rows that are not return values (e.g. count, skewness,
    kurtosis)
  Then those rows continue to display without a "%" suffix, since they are not percentages
```

---

### User Story 3 - One Set of Range Controls, Not Two (Priority: P2)

Someone changing the look-back period currently has to use a different control depending on
which half of the old tabbed page they're looking at: the histogram responds to the page's
shared date-range shortcut buttons, while the Value at Risk section has its own separate
look-back dropdown offering a similar but distinct set of choices. They want one range control
that drives both sections consistently.

**Why this priority**: With both sections now on one page, two separate, overlapping sets of
range controls sitting close to each other would be confusing and visually redundant — this is
the next thing a viewer would notice after the merge.

**Independent Test**: On the merged Risk page, change the range selection once and verify both
the histogram and the Value at Risk content update to reflect the new range, with no second range
control visible anywhere on the page.

**Acceptance Scenarios**:

```gherkin
Scenario: Only one range control exists on the page
  Given I am on the Risk page
  Then there is exactly one set of range controls (e.g. 1Y/3Y/5Y and any other existing options)
  And no separate "look-back" control is shown for the Value at Risk section

Scenario: Changing the range updates both sections
  Given I am on the Risk page with a range selected
  When I change the selected range
  Then the histogram chart and statistics refresh for the new range
  And the Value at Risk chart and backtest summary refresh for the same new range

Scenario: A range unsupported by Value at Risk data is handled gracefully
  Given I select a range for which Value at Risk has not been computed or has insufficient data
  Then the histogram section still renders normally for that range
  And the Value at Risk section shows its existing explanatory empty/insufficient-data state
    rather than an error or stale figures
```

---

### User Story 4 - A Clear Chart With One Reference Line and a Trustworthy Scale (Priority: P2)

Someone studying the histogram currently sees two vertical reference lines — mean and median —
that are often close enough to overlap, making both hard to read. They also cannot easily tell
whether the chart's horizontal axis values (e.g. "-1%", "-2%") are absolute returns or offsets
from the mean. They want a single, unambiguous mean line, and confidence that a given axis
position means what the summary statistics say it means.

**Why this priority**: This is a readability and trust refinement on top of the already-merged,
unit-corrected page — it matters, but less than having a single coherent page with correct units.

**Independent Test**: Open the Risk page for an account whose mean and median differ; verify only
one reference line (the mean) is drawn on the chart, and verify that the statistics table's
minimum and maximum values line up with the leftmost and rightmost populated bars on the chart's
percent-labelled x-axis.

**Acceptance Scenarios**:

```gherkin
Scenario: Only the mean reference line is shown
  Given the histogram chart renders for an account with distinct mean and median returns
  Then exactly one vertical reference line is drawn, labelled as the mean
  And no separate line or label is drawn for the median

Scenario: The axis scale is absolute, matching the statistics
  Given the statistics table reports a minimum and a maximum return value in percent
  Then the chart's x-axis spans a range consistent with those minimum and maximum values
  And a bar's horizontal position represents its own absolute return value, not its distance
    from the mean
```

---

### User Story 5 - Matching Visual Style for Both Statistics Summaries (Priority: P3)

Someone scrolling from the histogram's statistics table down to the Value at Risk section's
backtest summary currently sees two unrelated-looking presentations of similar information — one
a bordered grid, the other plain stacked text. They want both to look like part of the same page.

**Why this priority**: This is a finishing polish item — it improves cohesion but depends on
every structural and correctness change above already being in place.

**Independent Test**: Open the merged Risk page and compare the histogram's statistics table with
the Value at Risk backtest summary; verify both use the same typography, labelling style, and
structural presentation (e.g. both read as a labelled table/grid rather than one being a table and
the other plain prose).

**Acceptance Scenarios**:

```gherkin
Scenario: Both summaries share a consistent presentation
  Given I am looking at the histogram's statistics table
  And I am looking at the Value at Risk section's backtest summary
  Then both present their labelled values using the same visual treatment (e.g. consistent
    headers, borders/spacing, and label/value styling)
```

---

### Edge Cases

- **Mean and median are equal**: with the median line removed, this no longer produces an
  overlapping-line readability problem; only the single mean line is shown.
- **An account/range combination with no histogram data at all**: the histogram section shows its
  existing empty/no-data state; the Value at Risk section below it is unaffected and shows its own
  state independently.
- **A range selection the Value at Risk section cannot support** (e.g. insufficient computed
  history): the shared control still applies the range to the histogram; the Value at Risk section
  falls back to its existing explanatory empty state rather than showing mismatched or stale data.
- **Very small or very large statistic values** (e.g. a mean very close to 0.00%, or a maximum
  return far from the bulk of the distribation): percent formatting still applies consistently,
  and the axis still reflects the true absolute value even at the extremes.
- **Narrow/mobile viewport**: with tabs removed, the page becomes a single longer scroll; both
  sections must remain individually usable (chart and its statistics still legible) when stacked
  vertically rather than relying on a tab to hide one section at a time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Risk page MUST present the return histogram and the Value at Risk content as
  sections of a single continuous page, with no tab control separating them.
- **FR-002**: The return histogram section MUST appear before the Value at Risk section in the
  page's visual order.
- **FR-003**: Every return-based row in the histogram's statistics table (at minimum: mean,
  median, minimum, maximum, standard deviation) MUST be displayed in the same unit as the chart's
  x-axis (percent), with a visible unit indicator, rather than as an unlabeled raw value.
- **FR-004**: Non-return statistics (e.g. observation count, skewness, kurtosis) MUST continue to
  display without a percent suffix, since they are not percentage values.
- **FR-005**: The histogram chart MUST draw exactly one labelled reference line, for the mean
  return; the separate median reference line and its label MUST be removed.
- **FR-006**: The histogram chart's horizontal axis MUST represent absolute return values on the
  same scale as the statistics table's mean/median/minimum/maximum figures, not values offset
  from the mean, and this correspondence MUST remain true after any future change to the chart's
  bucketing or labelling.
- **FR-007**: The Risk page MUST offer exactly one set of range-selection controls that applies to
  both the histogram and the Value at Risk sections; any previously separate, overlapping range
  control MUST be removed.
- **FR-008**: Changing the shared range selection MUST refresh both the histogram section and the
  Value at Risk section to reflect the newly selected range.
- **FR-009**: If the Value at Risk section cannot produce data for a range selected via the shared
  control, it MUST show its existing explanatory empty/insufficient-data state rather than an
  error, stale data, or mismatched figures, while the histogram section continues to render
  normally for that same range.
- **FR-010**: The histogram's statistics table and the Value at Risk section's statistics/summary
  presentation MUST share a consistent visual style (typography, labelling convention, and
  structural treatment) so they read as part of one cohesive page.
- **FR-011**: This feature MUST NOT change the underlying return, histogram, or Value at Risk
  calculations themselves — only how the existing figures are laid out, labelled, and controlled.

### Key Entities

- **Return Histogram Statistic**: A labelled statistic (count, mean, median, mode, minimum,
  maximum, standard deviation, skewness, kurtosis) shown in the histogram's statistics table;
  return-based statistics carry a percent unit matching the chart.
- **Shared Range Selection**: The single range choice (e.g. 1Y/3Y/5Y and any other existing
  options) that governs the date window used by both the histogram and the Value at Risk section.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view both the return histogram and the Value at Risk content for an
  account by scrolling a single page, without clicking any tab or navigation control.
- **SC-002**: For any account and range, the value shown in the statistics table for a
  return-based statistic matches the position of that same statistic on the chart's percent-based
  axis (e.g. a chart position at "8.08%" is shown in the table as "8.08%", never "808").
- **SC-003**: The histogram chart shows exactly one labelled reference line (mean) in 100% of
  renders, regardless of account or range.
- **SC-004**: Selecting a range value once updates both the histogram and the Value at Risk
  content, and at no point does the page show two independently-selectable range controls.
- **SC-005**: The histogram's statistics table and the Value at Risk backtest summary both present
  their labelled values using the same underlying presentation (e.g. both rendered as a bordered,
  labelled table/grid with matching header and cell styling), verifiable by inspecting each
  section's rendered output rather than by subjective comparison alone.

## Assumptions

- The merged page reuses the existing shared account selector and top-of-page date-range
  controls (including its shortcut buttons) as the single range-selection control; the Value at
  Risk section's previously separate look-back dropdown is removed, and the Value at Risk section
  instead reacts to the shared control's selection.
- Where the shared range control offers an option the Value at Risk section does not support
  (e.g. a range outside what has been computed), the Value at Risk section falls back to its
  existing "not yet computed" / insufficient-data messaging rather than requiring new backend
  capability as part of this change.
- "Consistent visual style" (User Story 5 / FR-010) means shared typography, spacing, and a
  structured label/value presentation (e.g. both rendered as a labelled table or grid); it does
  not require the two sections to show identical data or merge into a single table.
- No new data or calculations are introduced; all values already exist in the histogram and
  Value at Risk responses described in prior Risk-page features — this feature only changes
  layout, labelling, unit display, and control wiring.
