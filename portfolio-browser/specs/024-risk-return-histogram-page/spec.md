# Feature Specification: Risk Page (Return Histogram)

**Feature Branch**: `024-risk-return-histogram-page`
**Created**: 2026-09-27
**Status**: Draft
**Input**: User description: "Create a new page in the portfolio-browser called 'risk' that starts with the 'account' drop-down, along with a start/end date and fixed buttons for 1Y/3Y/5Y/10Y/ALL history. Similar to the input controls on other pages, sharing as much default behavior and implementation logic as possible. The initial display will be a single row on the screen split 60% to a bar chart and 40% to a table. Both sections use the new portfolio-analysis-service endpoint for /risk/return-histogram. For example: http://127.0.0.1:8000/v1/accounts/HL-ISA/risk/return-histogram?start=2020-01-01&end=2026-09-01. The bar chart should have the key of each pair (basis points) as the X-axis and the Y-axis height as the value in the pair. The table next to this barchart output should have two columns, headed with \"statistic\" and \"value\". This is the contents of the 'statistics' part of the payload but NOT the 'std_dev_bands' array."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the Return Distribution for an Account (Priority: P1)

Someone wants to understand how volatile an account's daily returns have been. They open the new
"Risk" page, see an account already selected with a sensible default date range, and immediately
see a bar chart of how many days fell into each return bucket (in basis points) alongside a table
of the underlying summary statistics (count, mean, median, mode, min, max, standard deviation,
skewness, kurtosis).

**Why this priority**: This is the entire reason the page exists — every other capability
(switching accounts, changing the date range) is a refinement of this one view.

**Independent Test**: Open the Risk page for an account with recorded return history and verify a
bar chart renders with basis-point buckets on the X-axis and day-counts on the Y-axis, and a
two-column table headed "statistic" and "value" renders the account's return statistics.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The Risk page exists and is reachable from navigation
  Given I am looking at the navigation menu
  Then there is a "Risk" entry
  When I select it
  Then I land on a page with an account selector, a date range, and preset range buttons

Scenario: Opening the page shows a histogram and a statistics table
  Given I am on the Risk page
  And an account is selected with a default date range applied
  Then a bar chart is shown whose X-axis values are basis-point buckets and whose bar heights are
    the number of days observed in that bucket
  And a table headed "statistic" and "value" is shown next to the chart
  And the table's rows are exactly: count, mean, median, mode, minimum, maximum, std_dev,
    skewness, kurtosis — in that order, with no "std_dev_bands" row or column

Scenario: The chart and table sit side by side in a single row
  Given I am on the Risk page with data loaded
  Then the bar chart and the statistics table appear in the same row
  And the bar chart occupies the majority (60%) of that row's width
  And the table occupies the remainder (40%) of that row's width
```

---

### User Story 2 - Quickly Change the Observation Window with Preset Buttons (Priority: P2)

Someone wants to compare recent volatility against longer-term volatility without typing dates.
They click "1Y", "3Y", "5Y", "10Y" or "ALL" and see the chart and table update to reflect only
that trailing window.

**Why this priority**: This is the fastest, most common way users adjust the window on every
comparable page in the product (Overview, Positions, Performance); it multiplies the value of
User Story 1 but isn't required for the page to already be useful with its default range.

**Independent Test**: Open the Risk page for an account with several years of history, click "1Y",
and verify the chart and table refresh to reflect only the trailing one year of returns; click
"ALL" and verify they refresh to reflect the account's full recorded history.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Each preset button resolves to the matching trailing window
  Given I am on the Risk page for an account with over ten years of recorded history
  When I click each of "1Y", "3Y", "5Y", "10Y" and "ALL" in turn
  Then the start date shown updates to 1, 3, 5, and 10 years before the end date respectively,
    and to the account's earliest recorded date for "ALL"
  And the chart and table refresh to reflect only that window after each click

Scenario: A preset window with too little history still renders without error
  Given I am on the Risk page for an account with two years of recorded history
  When I click "10Y"
  Then the start date is clamped to the account's earliest recorded date
  And the chart and table render using the available history, with no error shown
```

---

### User Story 3 - Fine-Tune the Exact Date Range (Priority: P3)

Someone wants to inspect a specific, non-standard window — for example, a market event that
doesn't line up with a round trailing period. They edit the start and/or end date directly instead
of using a preset button.

**Why this priority**: This is a refinement available on every comparable page; most visits are
served by User Stories 1 and 2 alone, but this unlocks arbitrary windows for closer inspection.

**Independent Test**: Open the Risk page, manually set the start and end dates to a custom range
narrower than any preset, and verify the chart and table refresh to reflect exactly that range.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Manually editing either date refreshes the view
  Given I am on the Risk page with data loaded
  When I change the start date, the end date, or both, to a custom range
  Then the chart and table refresh to reflect exactly that custom range
  And no preset button appears selected once a manually-edited range no longer matches any preset

Scenario: Switching accounts resets the range to that account's own default
  Given I have a custom or preset date range applied
  When I select a different account
  Then the date range resets to the newly selected account's own default range
  And the chart and table refresh for the newly selected account
```

---

### Edge Cases

- **No account has any recorded return history**: the page shows the same "no data" treatment
  already used elsewhere in the product rather than an error.
- **The selected account/range has too few observations for a statistic to be defined** (e.g.
  fewer than 2 observations for standard deviation, fewer than 3 for skewness, fewer than 4 for
  kurtosis): the table still shows a row for that statistic, with its value shown as not
  available, rather than omitting the row or erroring.
- **The histogram has no observations in the selected range**: the page shows the same "no data"
  treatment used elsewhere, and the statistics table is not shown alongside an empty chart.
- **The end date is not strictly after the start date**: an inline validation message is shown and
  the previously valid chart/table remain displayed, consistent with date-range validation
  elsewhere in the product.
- **The portfolio-analysis-service is unavailable**: the same error treatment already used on
  every other page applies; the page does not silently show stale or partial results.
- **A very wide range produces many distinct basis-point buckets**: the chart remains readable
  (e.g., through horizontal scrolling or axis scaling consistent with other charts in the
  product) rather than becoming unusably dense.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST add a "Risk" navigation entry leading to a new page.
- **FR-002**: The Risk page MUST let the user choose an account, using the same account selector
  behavior (including default account selection) already used on the other account-scoped pages.
- **FR-003**: The Risk page MUST offer start-date and end-date controls, defaulting to the
  selected account's full recorded history, consistent with the default range used on comparable
  pages (Overview/Performance).
- **FR-004**: The Risk page MUST offer five preset range buttons labelled "1Y", "3Y", "5Y", "10Y"
  and "ALL", each resolving the start date to that many years before the end date (or, for "ALL",
  to the account's earliest recorded date), reusing the same preset-button behavior already used
  on the other pages wherever the same trailing-window logic applies.
- **FR-005**: A preset window that extends earlier than the account's earliest recorded date MUST
  be clamped to that earliest date rather than producing an error.
- **FR-006**: Manually editing the start date and/or end date MUST refresh the page's data to
  reflect exactly the edited range, independent of the preset buttons.
- **FR-007**: An end date that is not strictly after the start date MUST be rejected with an
  inline validation message, and the page MUST continue showing its most recently valid data.
- **FR-008**: Switching the selected account MUST reset the date range to that newly selected
  account's own default range, consistent with account-switch behavior on other pages.
- **FR-009**: The Risk page MUST display, for the current account and date range, a bar chart
  whose X-axis is the basis-point bucket (the first element of each histogram pair) and whose bar
  height is the number of observations in that bucket (the second element of each pair).
- **FR-010**: The Risk page MUST display, alongside the bar chart, a table with exactly two
  columns headed "statistic" and "value", containing one row per field of the response's
  statistics data **excluding** the standard-deviation-bands data.
- **FR-011**: The bar chart and the statistics table MUST be laid out in a single row, with the
  bar chart occupying approximately 60% of the row's width and the table occupying the remaining
  approximately 40%.
- **FR-012**: Every statistic whose value is not defined for the current observations (e.g. too
  few observations for standard deviation, skewness, or kurtosis) MUST still appear as a row in
  the table, with its value shown as not available rather than being omitted.
- **FR-013**: When the current account and date range have no observations to show, the page MUST
  show the same "no data" treatment already used elsewhere in the product, without rendering an
  empty chart or table.
- **FR-014**: The Risk page's error and "service unavailable" treatment MUST be consistent with
  every other page's existing treatment of the same conditions.
- **FR-015**: The bar chart and the statistics table MUST both refresh together whenever the
  selected account, start date, or end date changes.

### Key Entities *(include if feature involves data)*

- **Return Histogram Request**: An account and a date range (start, end) for which to compute the
  distribution of daily returns.
- **Histogram Bucket**: One basis-point value paired with the count of observed days that rounded
  to that value. The full set of buckets for a request forms the bars of the chart.
- **Return Statistics**: The summary figures describing the distribution over the same
  observations as the histogram — count, mean, median, mode, minimum, maximum, standard
  deviation, skewness, and kurtosis. Does not include the standard-deviation-bands data, which is
  out of scope for this page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see an account's return distribution and its summary statistics within
  two interactions or fewer (open the page, optionally pick an account) from landing on the
  product.
- **SC-002**: A user can switch between the 1Y, 3Y, 5Y, 10Y and ALL trailing windows in a single
  click each, with the chart and table always reflecting the clicked window.
- **SC-003**: A user can identify, without scrolling or hovering, both the shape of the return
  distribution (via the bar chart) and its key summary figures (via the table) in the same view.
- **SC-004**: An account or range with insufficient history for some statistics still produces a
  fully readable page (a chart with the available buckets, and a complete table with "not
  available" placeholders) rather than an error or a blank page.
- **SC-005**: 100% of the statistics fields returned by the endpoint (other than the
  standard-deviation bands) are visible in the table with no manual configuration required.

## Assumptions

- The Risk page's account selector and date-range controls (start/end date pickers and preset
  buttons) reuse the same default behaviors already established by the Overview, Positions, and
  Performance pages — this is what "similar to the input controls on other pages, sharing as much
  default behavior and implementation logic as possible" in the feature request means.
- The default date range is the selected account's full recorded history, matching the default
  already used by Overview and Performance, since no page-specific default was specified.
- The "10Y" preset button is a new trailing-window option not previously used elsewhere in the
  product (existing pages use "YTD"/"ITD" in that slot); introducing it is in scope for this
  feature and does not affect the preset buttons on any other existing page.
- "Not available" placeholder text/formatting for undefined statistics follows the same
  convention already used for missing values elsewhere in the product; no new convention is
  introduced.
- The `/risk/return-histogram` endpoint already exists in the portfolio-analysis-service (recent
  work has added a first version of it) and returns, per the feature request's example, an
  `account_name`, resolved `from_date`/`to_date`, a `histogram` array of `[basis_points, count]`
  pairs, and a `statistics` object (count, mean, median, mode, minimum, maximum, std_dev,
  std_dev_bands, skewness, kurtosis) — this feature only needs to consume it, not build it.
- This feature does not change or remove any existing page; it adds a new, independent page.
