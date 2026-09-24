# Feature Specification: Periodicity Control for the Projection Page

**Feature Branch**: `023-projection-periodicity-controls`
**Created**: 2026-09-24
**Status**: Draft
**Input**: User description: "the 'Projection' page should have the periodicity controls included and enabled for usage in the same way as the 'Overview' and 'Position' screen have it configured. The same defaults behavior should apply."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose How Densely the Projection Is Plotted (Priority: P1)

Someone looking at the Projection chart currently has no say in how many points are plotted: the
page silently picks an interval from the length of the combined historical-plus-projected span.
They want to see the same "Periodicity" control they already use on Overview and Positions, pick
a different interval, and have the historical line and every projected line redraw at it, keeping
the same account, start date, projection target and selected returns.

**Why this priority**: The control is the whole feature; defaults (Story 2) merely decide what it
shows before the user touches it.

**Independent Test**: Open Projection for an account with several years of history, choose a
20-year target, note the interval shown, select "month", and verify the historical and projected
series all redraw with one point per calendar month while account, start date, target date and
return toggles are unchanged.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The Periodicity control is present and matches the other pages
  Given I am on the Projection page
  When the parameters bar has loaded
  Then a control labelled "Periodicity" is shown alongside the existing Account controls
  And its options are exactly "day", "week", "month", "quarter" and "year", in that order

Scenario: Selecting an interval redraws historical and projected series
  Given I am on the Projection page with a 10Y target and the "5Y" return selected
  When I select "quarter" in the Periodicity control
  Then the historical series and the projected series are each plotted at one point per calendar quarter
  And the account, start date, target date and selected returns are unchanged

Scenario: Selecting "day" plots one point per business day
  Given I am on the Projection page with a 1Y target
  When I select "day" in the Periodicity control
  Then the chart shows one point per business day in the plotted span

Scenario: The control is disabled while the chart refreshes
  Given I am on the Projection page
  When a chart refresh is in progress
  Then the Periodicity control is disabled until the refresh completes
```

---

### User Story 2 - Sensible Default Interval, Shown in the Control (Priority: P2)

Someone who opens Projection and clicks "20Y" should get a readable chart without knowing the
control exists. Unless they choose otherwise, the interval is derived from the length of the plotted
span using the same thresholds as Overview and Positions, and the control always shows the interval
in effect.

**Why this priority**: Refines the default experience; the control works without it. Today the
page already derives an interval invisibly — this story makes that visible and overridable.

**Independent Test**: With no interval ever chosen by hand, select targets that make the plotted
span roughly six months, two years, four years and ten years and verify the chart and control show
day, month, quarter and year respectively.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario Outline: The interval is derived from the plotted span
  Given I am on the Projection page and have not chosen a periodicity myself
  When the plotted span, from the account's earliest record to the projection target, is <span>
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

Scenario: Clicking a longer horizon button derives a coarser interval automatically
  Given I am on the Projection page and have not chosen a periodicity myself
  And the chart is currently plotted at "month"
  When I click the "20Y" horizon button
  Then the chart is plotted at "year" without any further action from me
  And the Periodicity control shows "year"

Scenario: "week" is never chosen automatically
  Given I am on the Projection page and have not chosen a periodicity myself
  When the plotted span is any length from one day to forty years
  Then the interval in effect is never "week"
  And "week" remains selectable at all times

Scenario: An explicit choice is not overridden by later changes
  Given I am on the Projection page and have explicitly selected "month"
  When I click the "20Y" horizon button
  Then the chart is still plotted at "month"
  And the Periodicity control still shows "month"

Scenario: An explicit choice survives an account switch
  Given I am on the Projection page and have explicitly selected "quarter"
  When I switch to a different account
  Then the chart is plotted at "quarter" for the new account
  And no interval is derived from the new account's history
```

---

### Edge Cases

- **Boundary spans**: exactly one year → "day", exactly three years → "month", exactly five years →
  "quarter"; each boundary belongs to the finer interval (same as Overview/Positions).
- **Span definition**: on Projection the span is the full plotted span — the account's earliest
  recorded date through the projection target date — which is what the page already uses to pick
  its interval today. The Start Date input does not shorten it.
- **Explicit choice vs. derivation**: only a user interaction with the control makes a choice
  explicit; a derived value written into the control never becomes sticky.
- **Explicit choice is per page**: a choice made on Overview or Positions does not carry to
  Projection, and vice versa (consistent with the existing per-page behaviour).
- **Fine interval on a long horizon**: an explicit "day" with a 20Y target yields a dense chart;
  accepted, as on the other pages.
- **No target date chosen / no account**: the existing empty-state prompt still appears; the control
  remains visible and usable.
- **Calendar-picked target**: an explicit calendar date changes the derived interval by the same
  rules as a horizon button.
- **Invalid target (not after start date)**: existing validation message behaviour is unchanged and
  no redraw at a new interval is triggered by it.
- **Data service unavailable**: the existing error state still appears, and the control remains
  usable so the user can retry.
- **Projected series semantics**: changing the interval changes point density, not the projected
  values at any given date.
- **No returns selected**: only the historical line is plotted, at the chosen interval.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Projection page MUST present a "Periodicity" control in the top parameters bar,
  visually consistent with, and placed as it is on, the Overview and Positions pages.
- **FR-002**: The control MUST offer exactly "day", "week", "month", "quarter" and "year", in that
  order, and MUST NOT allow any other value.
- **FR-003**: Each option MUST map to the same aggregation interval on the data service as on
  Overview and Positions ("year" → annual).
- **FR-004**: Changing the interval MUST redraw the chart — historical series and every projected
  series — at the new interval without altering the account, start date, target date, or selected
  returns.
- **FR-005**: When the user has not chosen an interval, the system MUST derive one from the plotted
  span using the same thresholds as Overview/Positions: one year or less → "day"; over one year up
  to three → "month"; over three up to five → "quarter"; over five → "year".
- **FR-006**: "week" MUST never be derived automatically and MUST remain selectable at all times.
- **FR-007**: A derived interval MUST be recomputed whenever the plotted span changes — horizon
  button click, calendar pick, start-date change, or account switch.
- **FR-008**: The control MUST always display the interval currently in effect, derived or chosen,
  so the chart is never plotted at an interval the control does not show.
- **FR-009**: Once the user has explicitly chosen an interval, it MUST persist across subsequent
  horizon clicks, calendar picks, start-date changes and account switches until changed again;
  derivation applies only while no explicit choice has been made.
- **FR-010**: With no explicit choice, the interval used for any given account, start date and
  target MUST be the same as the page uses today, so existing behaviour is unchanged until the user
  interacts with the control.
- **FR-011**: The control MUST be disabled while a chart refresh is in flight, consistent with the
  other pages' controls.
- **FR-012**: Existing empty-state, validation-message and error-state behaviour MUST be unchanged
  at every interval.
- **FR-013**: The Projection page's periodicity selection MUST be independent of the selections on
  Overview and Positions.

### Key Entities *(include if feature involves data)*

- **Periodicity Selection**: The interval the Projection chart is plotted at — one of day, week,
  month, quarter, year — held for this page, always shown in the control, either derived or chosen.
- **Plotted Span**: The length of time from the account's earliest recorded date to the projection
  target date; the basis for deriving an interval when none has been chosen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Changing the interval requires exactly one interaction and leaves every other
  selection on the page untouched.
- **SC-002**: 100% of Projection views with no explicit interval choice plot at the same interval
  as before this feature.
- **SC-003**: The interval shown in the control matches the interval the chart is plotted at in
  100% of observed states, including immediately after a horizon click or account switch.
- **SC-004**: An explicitly chosen interval survives 100% of subsequent horizon clicks, calendar
  picks, start-date changes and account switches, and changes only by another explicit choice.
- **SC-005**: The Periodicity control offers the same five options in the same order on Overview,
  Positions and Projection.
- **SC-006**: A user who clicks "20Y" sees a readable, annually plotted chart without interacting
  with the Periodicity control.

## Assumptions

- "Same defaults behaviour" means the same duration thresholds (one/three/five years), the same
  "week is never automatic" rule, and the same explicit-choice-persists rule specified for
  Overview and Positions in feature 021.
- The span used for derivation stays as the Projection page already defines it (earliest record to
  target date), because that is the span actually plotted; this preserves today's default charts.
- Only the control and its wiring are in scope; no new aggregation logic is introduced. The data
  service already accepts an interval for projections and decides period boundaries.
- The Performance page remains out of scope.
- The control's labels, ordering and thresholds continue to come from the existing shared
  periodicity configuration, so no separate Projection-specific configuration is introduced.
- Existing account selector, start-date input, horizon buttons, calendar picker and return toggles
  are otherwise unchanged.
