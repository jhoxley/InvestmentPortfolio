# Feature Specification: Periodicity Control for Overview & Positions

**Feature Branch**: `021-periodicity-controls`
**Created**: 2026-09-22
**Status**: Draft
**Input**: User description: "With reference to the 008 feature just completed on the 'portfolio-analysis-service' integrate these changes with the portfolio browser. For both the 'overview' and 'positions' pages add a common, shared control UI at the top (in-line with current designs) labeled 'Periodicity' and having options of 'day', 'week', 'month', quarter' and 'year'. These should map to the periodicity options on the API and render graphs appropriately. Further amend the default behavior such that, unless specified by the user, a date range of one year or less is 'daily', between 1-3 years is 'monthly' and 3-5 years is 'quarterly' and anything longer than 5 years defaults to annually."

## Clarifications

### Session 2026-09-22

- Q: Once the user has explicitly picked a periodicity, what happens when they then change the
  date range — does their choice persist, or does the system resume deriving one? → A: The
  explicit choice wins and persists across date-range changes, shortcut clicks and account
  switches until they change it again. Automatic derivation applies only while the user has made
  no explicit choice. A deliberate "day" on a ten-year range therefore still yields a dense chart
  — which is exactly today's behaviour, so it is not a regression, merely not auto-rescued.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose How Densely a Chart Is Plotted (Priority: P1)

Someone looking at the Overview chart over a multi-year range currently gets one point per
business day — thousands of points that obscure the trend they are trying to see. They pick a
coarser interval from a new "Periodicity" control at the top of the page and the chart redraws
with one point per calendar period, keeping the same account, date range and selected metrics.

**Why this priority**: This is the feature's core value and the only part that must exist for any
other part to be useful — the control is what everything else reads from or writes to. It is
independently valuable even with no change to default behaviour.

**Independent Test**: Open Overview for an account with several years of history, set a
multi-year date range, then select "year" in the Periodicity control. Verify the chart redraws
with one point per calendar year, that the account/date range/metric selections are untouched,
and that selecting "day" returns the chart to its previous per-business-day appearance.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The Periodicity control is present and offers the five documented intervals
  Given I am on the Overview page
  When the parameters bar has loaded
  Then a control labelled "Periodicity" is shown alongside the existing Account and date-range controls
  And its options are exactly "day", "week", "month", "quarter" and "year", in that order

Scenario: Selecting a coarser periodicity redraws the chart at that interval
  Given I am on the Overview page for an account with data from 2016 through 2025
  And the date range covers 2016-01-04 to 2025-12-31
  When I select "year" in the Periodicity control
  Then the chart redraws with exactly one point per calendar year in the range
  And the selected account, date range and metrics are unchanged

Scenario: Each interval option maps to the matching aggregation on the data service
  Given I am on the Overview page with a date range covering several years
  When I select each of "week", "month", "quarter" and "year" in turn
  Then the chart redraws each time with one point per calendar week, month, quarter and year respectively

Scenario: Selecting "day" reproduces the pre-existing per-business-day chart
  Given I am on the Overview page with a date range of one month
  When I select "day" in the Periodicity control
  Then the chart shows one point per business day in the range
  And the chart is identical to the one shown before this feature existed
```

---

### User Story 2 - The Same Control, Behaving the Same Way, on Positions (Priority: P2)

Someone comparing individual positions needs the same choice of interval, working the same way,
so that a Positions chart can be read alongside an Overview chart at a matching interval without
re-learning a different control.

**Why this priority**: Consistency across the two pages is what makes the control trustworthy,
but Overview alone already delivers the value. It depends on nothing from User Story 1 beyond the
shared control itself, so it can be built and tested on its own.

**Independent Test**: Open Positions for an account with two or more positions and a multi-year
range, select "quarter", and verify every position's series is plotted at one point per calendar
quarter, with the position filter and attribute toggles unaffected.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Positions offers an identical Periodicity control
  Given I am on the Positions page
  When the parameters bar has loaded
  Then a control labelled "Periodicity" is shown with the same five options in the same order as on Overview

Scenario: Selecting a periodicity aggregates every plotted position
  Given I am on the Positions page for an account holding two positions with data across 2025
  When I select "quarter" in the Periodicity control
  Then each position's series is plotted at one point per calendar quarter
  And the positions plotted, the selected attributes and the date range are unchanged

Scenario: Periodicity and the stacked-area view work together
  Given I am on the Positions page with the stacked area graph enabled
  When I select "month" in the Periodicity control
  Then the stacked chart redraws with one band segment per calendar month
  And no error or empty state is shown

Scenario: Switching pages keeps each page's own periodicity behaviour intact
  Given I have selected "year" on the Overview page
  When I navigate to the Positions page
  Then the Positions page shows its own Periodicity control in a valid state
  And its chart renders without error
```

---

### User Story 3 - Long Ranges Are Legible Without Touching the Control (Priority: P3)

Someone who opens a page with a long date range — or who clicks a "5Y"/"All" shortcut — should
see a readable chart immediately, without having to know that a periodicity control exists. The
interval is chosen for them based on how long the range is, and the control shows which interval
is in effect so nothing is hidden.

**Why this priority**: This is a refinement of the default experience rather than a new
capability; the control is fully usable without it. It is last because it depends on the control
existing to display the chosen interval.

**Independent Test**: With no interval ever selected by hand, set date ranges of six months, two
years, four years and ten years in turn and verify the chart is plotted at day, month, quarter
and year respectively, with the control reflecting each.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario Outline: The interval is derived from the length of the date range
  Given I am on the Overview page and have not chosen a periodicity myself
  When the date range spans <span>
  Then the chart is plotted at "<interval>"
  And the Periodicity control shows "<interval>" as the interval in effect

  Examples:
    | span      | interval |
    | 6 months  | day      |
    | 1 year    | day      |
    | 2 years   | month    |
    | 3 years   | month    |
    | 4 years   | quarter  |
    | 5 years   | quarter  |
    | 10 years  | year     |

Scenario: Clicking a long-range shortcut derives a coarser interval automatically
  Given I am on the Overview page and have not chosen a periodicity myself
  And the chart is currently plotted at "day" over a 6-month range
  When I click the "5Y" date-range shortcut
  Then the date range covers the trailing five years
  And the chart is plotted at "quarter" without any further action from me

Scenario: Switching to an account with a much longer history derives a coarser interval
  Given I am on the Overview page and have not chosen a periodicity myself
  When I switch to an account whose full recorded history spans more than five years
  Then the date range resets to that account's full history
  And the chart is plotted at "year"

Scenario: "week" is never chosen automatically
  Given I am on the Overview page and have not chosen a periodicity myself
  When the date range spans any length from one day to twenty years
  Then the interval in effect is never "week"
  And "week" remains selectable at all times

Scenario: An explicit choice is not overridden by a later date-range change
  Given I am on the Overview page
  And I have explicitly selected "month"
  When I click the "All" date-range shortcut on an account with more than five years of history
  Then the chart is still plotted at "month"
  And the Periodicity control still shows "month"

Scenario: An explicit choice survives an account switch
  Given I am on the Overview page
  And I have explicitly selected "quarter"
  When I switch to a different account
  Then the chart is plotted at "quarter" for the new account
  And no interval is derived from the new account's date range
```

---

### Edge Cases

- **Exact boundary spans**: a range of exactly one year resolves to "day", exactly three years to
  "month", and exactly five years to "quarter" — each boundary belongs to the *finer* interval.
- **Very short range at a coarse interval**: explicitly selecting "year" with a one-week range
  yields a single plotted point rather than an error or an empty chart.
- **Periods with no data**: a calendar period containing no observation is simply absent from the
  chart (the data service omits it) — no gap markers, no nulls, no error.
- **Return-type attributes on Positions**: under any interval other than "day", per-position
  return attributes report the **last single-day return** within each period, not a compounded
  period return. This is the data service's documented behaviour and is not recalculated here, so
  the chart must not imply otherwise.
- **No metrics selected**: the existing empty-state prompt still appears, regardless of the
  interval chosen.
- **Data service unavailable**: the existing error state still appears, and the Periodicity
  control remains usable so the request can be retried.
- **In-flight refresh**: the Periodicity control is disabled while a chart refresh is in progress,
  consistent with the existing account and date-range controls.
- **Pages without support**: the control does not appear on pages whose underlying data source
  offers no interval choice, so it never appears in a state where changing it does nothing.
- **A deliberate fine interval on a very long range**: a user who explicitly selects "day" and
  then widens the range to ten years gets a dense chart. This is accepted (FR-012) and matches
  today's behaviour; the system does not second-guess an explicit choice.
- **What counts as "explicitly chosen"**: only a user interaction with the Periodicity control
  makes a choice explicit. The system writing a derived interval into the control does not, so a
  derived value never becomes sticky by being displayed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Overview and Positions pages MUST each present a control labelled "Periodicity"
  at the top of the page, alongside the existing Account and date-range controls and visually
  consistent with them.
- **FR-002**: The control MUST offer exactly five options — "day", "week", "month", "quarter" and
  "year" — presented in that order, and MUST NOT allow any other value to be submitted.
- **FR-003**: Each option MUST map to the corresponding aggregation interval offered by the
  portfolio analysis data service, with the option labelled "year" mapping to that service's
  annual interval.
- **FR-004**: Changing the interval MUST redraw the chart at the new interval without altering the
  selected account, date range, metric/attribute selections, position filter, or chart mode.
- **FR-005**: A chart at an interval other than "day" MUST plot one observation per calendar
  period, dated at the start of that period, using the value the data service returns for it.
- **FR-006**: Both pages MUST offer the same options in the same order and MUST apply a chosen
  interval identically, differing only in what their charts already plot.
- **FR-007**: The control MUST appear only on the Overview and Positions pages, and MUST NOT be
  added to pages whose data source does not accept an interval.
- **FR-008**: When the user has not chosen an interval, the system MUST derive one from the length
  of the effective date range: one year or less → "day"; more than one year up to and including
  three years → "month"; more than three years up to and including five years → "quarter"; more
  than five years → "year".
- **FR-009**: "week" MUST never be derived automatically; it MUST be reachable only by explicit
  selection, and MUST remain selectable at all times.
- **FR-010**: A derived interval MUST be recomputed whenever the effective date range changes —
  including a manual date edit, a date-range shortcut click, and an account switch that resets the
  range.
- **FR-011**: The control MUST always display the interval currently in effect, whether that
  interval was derived or chosen by the user, so the chart is never plotted at an interval the
  control does not show.
- **FR-012**: Once the user has explicitly chosen an interval, that choice MUST persist across
  subsequent date-range changes, shortcut clicks and account switches until they change it again;
  automatic derivation MUST apply only while the user has made no explicit choice. A deliberate
  choice MUST NOT be silently overridden, even where the derived interval would differ.
- **FR-013**: A date range of one year or less with no explicit choice MUST produce the same chart
  the page produced before this feature existed, so nothing changes for short-range users.
- **FR-014**: On Positions, a chosen interval MUST apply to every plotted position independently
  and MUST work in both the standard and stacked-area chart modes.
- **FR-015**: Existing empty-state and error-state behaviour MUST be unchanged by this feature, at
  every interval.
- **FR-016**: The control MUST be disabled while a chart refresh is in flight, consistent with the
  existing account and date-range controls.

### Key Entities *(include if feature involves data)*

- **Periodicity Selection**: The interval a chart is currently plotted at. One of five values —
  day, week, month, quarter, year. Held per page, always visible in that page's control, and
  either derived from the date range or chosen by the user.
- **Date Range Span**: The length of the effective date range, used to derive an interval when the
  user has not chosen one. Measured from the effective start and end dates shown in the existing
  date controls, and mapped to an interval by fixed duration thresholds of one, three and five
  years.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A ten-year Overview chart can be reduced from roughly 2,600 plotted points to about
  10 in a single interaction with the Periodicity control.
- **SC-002**: Changing the interval requires exactly one interaction and leaves every other
  selection on the page untouched.
- **SC-003**: Someone who opens a ten-year range, or clicks the "All" shortcut on an account with
  more than five years of history, sees an annually plotted chart without interacting with the
  Periodicity control at all.
- **SC-004**: 100% of views with a date range of one year or less and no explicit interval choice
  render exactly as they did before this feature.
- **SC-005**: Both pages present the same five options in the same order, and a given interval
  produces the same period boundaries on both.
- **SC-006**: A multi-year chart at "month", "quarter" or "year" renders no slower than the same
  range at "day", and transfers less data.
- **SC-007**: The interval shown in the control matches the interval the chart is plotted at in
  100% of observed states, including immediately after an account switch or shortcut click.
- **SC-008**: An explicitly chosen interval survives 100% of subsequent date-range changes,
  shortcut clicks and account switches, and is only ever changed by another explicit choice.

## Assumptions

- The option labelled "year" corresponds to the data service's `annual` interval; the other four
  labels match its interval names directly. The label "year" is used in the UI because it reads
  more naturally beside "day", "week", "month" and "quarter".
- Duration thresholds are inclusive at their lower interval: exactly one year is "day", exactly
  three years is "month", exactly five years is "quarter". This keeps the finer, more detailed
  interval whenever a span sits precisely on a boundary.
- "week" is deliberately absent from the derived-interval rules because the user's stated
  thresholds do not mention it; it remains available for explicit selection.
- Span is measured against the effective date range shown in the existing date controls — the same
  dates the chart is already drawn from — rather than the account's full recorded history.
- The Performance page is out of scope: its underlying performance measures are not offered at a
  choice of intervals by the data service, so a control there would have nothing to change. The
  Income page is likewise out of scope as it has no chart of this kind.
- This feature adds no new aggregation logic of its own. Period boundaries, the choice of which
  observation represents a period, and the omission of empty periods are all decided by the data
  service; the pages only ask for an interval and plot what comes back.
- Requires the portfolio analysis service's periodicity capability (its feature 008) to be
  deployed and reachable. Against a service without it, the pages would continue to behave as they
  do today.
- Per-position return attributes are not re-derived by this feature; at coarser intervals they
  carry the data service's documented last-observation semantics.
- No change is made to the existing account selector, date pickers, date-range shortcuts, metric
  toggles, position filter, or stacked-area toggle beyond their being disabled during a refresh as
  they already are.
