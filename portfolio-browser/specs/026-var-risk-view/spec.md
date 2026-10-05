# Feature Specification: Value at Risk View (Risk Page)

**Feature Branch**: `026-var-risk-view`
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "Add a 'Value at Risk' view to the Risk page alongside the existing return histogram (e.g. as a second tab), using the shared account selector, date range controls and shortcut buttons. Controls: confidence levels (95%, 97.5%, 99%, multi-select, populated from GET /v1/risk/var/methods), look-back (1Y/2Y/5Y, default 2Y), units (GBP or % of market value), PnL basis (ladder or hypothetical) and a toggle to hide degraded-quality dates. The main chart shows daily realised PnL as bars plotted on each outcome date, overlaid with the negative VaR line for each selected confidence level taken from the previous business day's estimate, with exceptions (losses beyond VaR) highlighted in red; ES can be shown as dashed lines. Beneath it, a smaller linked chart shows total market value and the proxied/rescaled share of market value so changes in portfolio construction are visible. A side panel shows the backtest summary for the visible range from GET .../risk/var/backtest: exceptions versus expected, Kupiec and conditional-coverage p-values, traffic-light zone, mean VaR and VaR stability. Changing confidence, units or PnL basis must re-render from already-fetched data without a new request; changing account, dates or look-back refetches. When VaR has not been computed for the account, show an empty state explaining how to run it (using GET .../risk/var/status); when the store is behind the ladder, show a banner with the number of missing dates. Periodicity controls do not apply to this view."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See Daily Risk Against Realised Outcomes (Priority: P1)

Someone reviewing an account's risk wants to see, at a glance, each day's realised profit or loss
next to the Value-at-Risk forecast that applied to it, with days where the loss actually exceeded
the forecast clearly called out, so they can judge whether the model's risk estimate has been
keeping pace with what actually happened.

**Why this priority**: This chart is the entire reason the view exists — every other capability
(switching confidence levels, changing units, the backtest panel) refines or explains this one
picture.

**Independent Test**: Open the Risk page's "Value at Risk" tab for an account with a completed VaR
calculation and verify a chart renders with one bar per business day (realised profit/loss) and an
overlaid line for the selected confidence level's Value-at-Risk forecast, with any day whose loss
exceeded that forecast visually distinguished from the rest.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The Value at Risk tab exists alongside the return histogram
  Given I am on the Risk page
  Then there is a "Value at Risk" tab next to the existing histogram tab
  When I select it
  Then the shared account selector, date range and shortcut buttons remain visible and unchanged

Scenario: Opening the tab shows realised PnL bars with a VaR overlay
  Given I am on the Value at Risk tab for an account with a completed calculation
  Then a chart shows one bar per business day for that day's realised profit or loss
  And a line overlays the chart showing the negative of the selected confidence level's forecast
  And the line's point for a given day is drawn from the previous business day's forecast

Scenario: A day whose loss exceeded its forecast is visually distinguished
  Given the chart is showing a day whose realised loss was larger than that day's VaR forecast
  Then that day's bar is visually distinguished (e.g. coloured differently) from non-exceeding days

Scenario: Expected Shortfall can optionally be shown
  Given I am on the Value at Risk tab
  When I turn on the Expected Shortfall display
  Then a second, visually distinct line (e.g. dashed) appears showing each selected confidence
    level's Expected Shortfall forecast
```

---

### User Story 2 - Judge Whether the Model Can Be Trusted (Priority: P1)

Someone who has just looked at the chart wants a quick, quantified answer to "is this risk model
actually reliable for this account?" — how many times losses exceeded the forecast versus how
many were expected, whether those exceedances cluster suspiciously, and a simple pass/fail-style
rating — without needing to understand the underlying statistics.

**Why this priority**: This is the second half of the view's core value; the chart shows the
picture, this panel turns it into an assessment. It depends only on data already fetched for User
Story 1.

**Independent Test**: With the chart showing a date range and confidence level, verify a panel
alongside it reports the number of exceedances against the number expected, two reliability
p-values, a simple pass/fail-style rating, the average forecast level, and how stable the forecast
has been, all for the currently displayed range and confidence level.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The backtest panel reports the headline reliability figures
  Given I am on the Value at Risk tab with data loaded for one confidence level
  Then a panel shows the number of exceedances observed and the number expected
  And it shows two reliability p-values and a simple pass/fail-style rating
  And it shows the average forecast level and a measure of how stable the forecast has been

Scenario: The panel reflects the same range and confidence level as the chart
  Given the chart is showing a particular date range and confidence level
  Then the panel's figures are computed over that same date range and confidence level
```

---

### User Story 3 - Explore Confidence Levels, Units and PnL Basis Instantly (Priority: P2)

Someone wants to compare how the picture changes at a stricter confidence level, in percentage
terms instead of money, or using the account's actual trading activity instead of a frozen
model portfolio — without waiting for the page to reload each time.

**Why this priority**: This turns a static picture into an exploratory tool, which is valuable but
secondary to the picture and the assessment already existing (User Stories 1 and 2).

**Independent Test**: With the tab already loaded, change the confidence-level selection, the
units toggle, and the PnL-basis toggle one at a time, and verify the chart and backtest panel each
update immediately, with no loading indicator and no new data request.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Changing the selected confidence levels updates instantly
  Given the tab has already loaded data for an account
  When I add or remove a confidence level from the selection
  Then the chart's overlay lines and the backtest panel update immediately
  And no new network request is made for this change

Scenario: Changing units updates the displayed scale instantly
  Given the tab has already loaded data
  When I switch the units control between money and percentage of market value
  Then the chart's bars and overlay lines redraw in the newly selected unit
  And no new network request is made for this change

Scenario: Changing PnL basis updates which days are exceedances instantly
  Given the tab has already loaded data, and a day's two PnL bases disagree on whether it is an
    exceedance
  When I switch the PnL-basis control
  Then that day's bar reflects the newly selected basis's figure
  And whether that day is flagged as an exceedance changes accordingly
  And no new network request is made for this change
```

---

### User Story 4 - Change Account, Dates or Look-back (Priority: P2)

Someone wants to look at a different account, a different time window, or a longer/shorter
historical look-back used to forecast each day's risk, using the same controls they already use
elsewhere in the product.

**Why this priority**: Consistency with every other page's navigation controls; without it the
view would be a dead end, but it is a smaller addition than the view's own chart and panel.

**Independent Test**: Change the selected account, then the date range (via typing or a shortcut
button), then the look-back selector, and verify the chart and panel each refresh with newly
fetched data after every change.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Changing the account refetches the view
  Given I am on the Value at Risk tab for one account
  When I select a different account from the shared selector
  Then new data is fetched for the newly selected account
  And the chart and backtest panel refresh to reflect it

Scenario: Changing the date range refetches the view
  Given I am on the Value at Risk tab
  When I change the date range directly or via a shortcut button
  Then new data is fetched for the new range
  And the chart and backtest panel refresh to reflect it

Scenario: Changing the look-back refetches the view
  Given I am on the Value at Risk tab with the default 2-year look-back
  When I select a different look-back
  Then new data is fetched using that look-back
  And the chart and backtest panel refresh to reflect it

Scenario: Periodicity controls have no effect on this view
  Given I am on the Value at Risk tab
  Then no periodicity control (day/week/month/quarter/annual) is shown or has any effect
```

---

### User Story 5 - Understand Missing or Stale Risk Data (Priority: P2)

Someone opens the tab for an account whose risk has never been calculated, or whose calculation
is behind the account's trading activity, and needs to understand that immediately rather than
mistaking a blank chart for "no risk" or stale data for current data.

**Why this priority**: Without this, the view's failure mode is confusing or misleading, which
undermines trust in every other capability — but it is only encountered for accounts in these
states, not on the primary happy path.

**Independent Test**: Open the tab for an account with no calculated risk data and verify an
explanatory empty state appears instead of a blank or broken chart; separately, open it for an
account whose risk data lags its trading activity and verify a banner states how many dates are
missing.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: An account with no calculated risk data shows an explanatory empty state
  Given I open the Value at Risk tab for an account with no calculated risk data
  Then no chart, overlay or backtest panel is shown
  And an explanatory message appears describing why, and how risk calculation is triggered

Scenario: An account whose risk data lags its trading activity shows a banner
  Given I open the Value at Risk tab for an account whose risk data is behind its trading activity
  Then a banner appears stating how many dates are missing
  And the chart and panel still render using whatever data has been calculated so far
```

---

### User Story 6 - Focus on Reliable Observations Only (Priority: P3)

Someone comparing look-backs or confidence levels wants to set aside days where the forecast was
flagged as lower quality, so a run of degraded data doesn't distort their reading of the chart.

**Why this priority**: A refinement for careful analysis; the view is fully usable without it.

**Independent Test**: With a range containing both normal and degraded-quality days, toggle "hide
degraded-quality dates" on and verify those days' bars and overlay points disappear from the
chart, then toggle it off and verify they return.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Hiding degraded-quality dates removes them from the chart
  Given the displayed range includes at least one degraded-quality date
  When I turn on "hide degraded-quality dates"
  Then that date's bar and overlay point no longer appear on the chart
  And the backtest panel's figures are recomputed excluding that date

Scenario: Turning the toggle off restores degraded-quality dates
  Given "hide degraded-quality dates" is turned on
  When I turn it off
  Then previously hidden degraded-quality dates reappear on the chart
```

---

### Edge Cases

- **No confidence level selected**: the control never allows every level to be deselected at
  once — removing the last remaining selection has no effect, so the chart and panel always have
  at least one confidence level to show.
- **A date with no VaR value** (quality flagged as insufficient, e.g. early in a long look-back
  before enough price history exists): its overlay line has a gap at that point, but its realised
  PnL bar still appears (realised outcomes don't depend on quality).
- **The newest date's outcome is still pending**: its PnL bar is omitted (there is nothing
  realised yet to show), but its VaR overlay point still appears.
- **Switching PnL basis changes which days are exceedances**: a day can be an exceedance under one
  basis and not the other; the chart and panel always reflect only the currently selected basis.
- **An account with calculated risk data that doesn't cover the whole selected date range**: the
  chart and panel show whatever is available within the range; the missing-data banner (User
  Story 5) covers the "behind the ladder" case specifically.
- **Very short selected ranges** (e.g. a single day): the chart renders with as few bars/points as
  the range produces; the backtest panel shows "not enough observations" rather than a misleading
  statistic for anything that needs more than one observation to compute.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Risk page MUST present the existing return-histogram view and this new Value at
  Risk view as two separate, independently selectable tabs (or an equivalent switch), sharing one
  account selector, date range control and shortcut-button set across both.
- **FR-002**: The Value at Risk tab MUST offer: a multi-select confidence-level control populated
  from the available-methods description (not hard-coded); a single-select look-back control
  (1 year / 2 years / 5 years, defaulting to 2 years); a units control (money or percentage of
  market value); a PnL-basis control (ladder or hypothetical); and a toggle to hide
  degraded-quality dates.
- **FR-003**: The confidence-level control MUST default to every available level selected, and
  MUST always retain at least one selected level (Edge Cases).
- **FR-004**: The main chart MUST show one bar per business day for that day's realised
  profit/loss (per the selected PnL basis), positioned at that day's outcome date.
- **FR-005**: The main chart MUST overlay, for each selected confidence level, a line showing the
  negative of that level's Value-at-Risk forecast, with each point drawn from the forecast made as
  of the previous business day.
- **FR-006**: Any day whose realised loss (per the selected PnL basis) exceeded that day's
  Value-at-Risk forecast, for at least one selected confidence level, MUST be visually
  distinguished from non-exceeding days.
- **FR-007**: The view MUST offer a way to optionally show each selected confidence level's
  Expected Shortfall forecast as a visually distinct overlay (e.g. a dashed line), separate from
  the Value-at-Risk overlay; this MUST default to off.
- **FR-008**: Beneath the main chart, a second, smaller chart MUST show the account's total market
  value and the proxied/rescaled share of that market value over the same date range, visually
  linked to the main chart (e.g. sharing its horizontal axis) so changes in portfolio construction
  can be related to changes in the risk picture above it.
- **FR-009**: A panel alongside the charts MUST show, for the currently displayed date range and
  each selected confidence level: the number of exceedances observed and expected, two
  reliability p-values (one for frequency, one combining frequency and clustering), a simple
  pass/fail-style rating, the average forecast level, and a measure of how stable the forecast has
  been.
- **FR-010**: Changing the confidence-level selection, the units control, or the PnL-basis control
  MUST update the chart and the backtest panel immediately from data already retrieved, without
  making a new data request.
- **FR-011**: Changing the selected account, the date range, or the look-back MUST retrieve new
  data for the chart and backtest panel.
- **FR-012**: Turning on "hide degraded-quality dates" MUST remove degraded-quality dates from the
  chart and exclude them from the backtest panel's figures; turning it off MUST restore them.
- **FR-013**: When an account has no calculated risk data at all for the selected look-back, the
  view MUST show an explanatory empty state instead of an empty or broken chart, describing why
  there is nothing to show and how risk calculation for an account is triggered.
- **FR-014**: When an account's calculated risk data does not yet cover its full recorded trading
  history, the view MUST show a banner stating how many dates are missing, without preventing the
  chart and panel from rendering whatever data is available.
- **FR-015**: No periodicity control (day/week/month/quarter/annual) MUST be shown on, or have any
  effect on, this view.

### Key Entities

- **Daily Risk Point**: One business day's realised profit/loss (per PnL basis), its
  Value-at-Risk and Expected Shortfall forecasts at each confidence level, whether it was an
  exceedance at each level, and its data-quality flag.
- **Portfolio Construction Point**: One business day's total market value and the proportion of
  that value that was proxied or rescaled rather than directly observed.
- **Backtest Summary**: Per confidence level, over the displayed range: exceedances observed and
  expected, the two reliability p-values, the pass/fail-style rating, the average forecast level,
  and the forecast-stability measure.
- **Available Methods**: The confidence levels and look-backs the view's controls may offer,
  discovered rather than hard-coded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening the Value at Risk tab for an account with calculated risk data shows the
  chart, the portfolio-construction chart and the backtest panel together, with no further action
  needed, every time.
- **SC-002**: Changing the confidence-level selection, units, or PnL basis updates the chart and
  panel with no network round-trip and no visible loading state, every time.
- **SC-003**: Every exceedance day within the displayed range is visually distinguishable from
  non-exceedance days, 100% of the time.
- **SC-004**: Opening the tab for an account with no calculated risk data shows explanatory
  guidance rather than an error or a blank chart, 100% of the time.
- **SC-005**: Opening the tab for an account whose risk data lags its trading activity shows a
  missing-date count that matches the account's own status figure exactly, every time.
- **SC-006**: Changing account, date range, or look-back always results in the chart and panel
  reflecting the newly selected data, with no stale data left on screen from a prior selection.

## Assumptions

- The view is strictly read-only: it never triggers a risk calculation itself. The empty state
  (FR-013) explains how a calculation is run (e.g. via the existing pipeline/API already used to
  populate risk data), but does not add a button to trigger one from this page — an in-browser
  trigger is a reasonable later enhancement, out of scope here.
- "The visible range" for the backtest panel (User Story 2) means the same date range currently
  selected for the chart (via the shared date controls), not a separately zoomable/pannable
  sub-range — the two stay in lock-step.
- When multiple confidence levels are selected, a day is visually distinguished as an exceedance
  (FR-006) if it exceeded the forecast at *any* selected level; the backtest panel reports its
  figures per level (User Story 2), so a user comparing levels can still see which level(s) that
  day's loss actually exceeded.
- The units control (money vs. percentage of market value) rescales the chart's bars and overlay
  lines; it has no effect on the two reliability p-values, the pass/fail-style rating, or the
  forecast-stability measure, since those are already scale-independent. The backtest panel's
  average forecast level ("mean VaR") is always shown in money terms regardless of the units
  control: no percentage equivalent is available, and computing one would require weighting each
  day's forecast by that day's market value — a calculation, not a presentational transform.
- The look-back control's default (FR-002: "2 years") is realized as whichever look-back the
  available-methods description marks as the headline one, not a hardcoded value — the same
  discovery-based approach the confidence-level control already uses, so both controls stay
  correct if the service's own default ever changes.
- The confidence-level control's "always at least one selected" guarantee (FR-003) is an
  interaction constraint on the control itself (reverting an attempted clear-to-empty), not a
  property of the data it displays.
- "The previous business day's estimate" (FR-005) is a restatement of how the underlying risk
  data already associates a forecast date with the business day whose outcome it predicts; this
  view does not change that association, only plots it.
- Degraded-quality dates are hidden by User Story 6's toggle; dates with no forecast value at all
  (Edge Cases) are never plotted on the overlay regardless of this toggle, since there is nothing
  to plot.
- This view depends on the read-only risk-series, backtest and methods capabilities already
  exposed by the portfolio-analysis-service; no changes to that service are required by this
  feature.
