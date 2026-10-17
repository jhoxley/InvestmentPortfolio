# Feature Specification: Projection Page (replaces Income)

**Feature Branch**: `022-projection-page`
**Created**: 2026-09-22
**Status**: Draft
**Input**: User description: "remove the 'income' page from the 'portfolio-browser' and replace it with a 'projection' entry instead. It follows similar models to the existing 'performance' page but has new controls to project returns forward in time. Add buttons for \"1Y\", \"5Y\", \"10Y\" and \"20Y\". Also add a drop-down calendar picker to project forward to an explicit date chosen by the user. The data for the main graph should render the same as on the 'performance' tab with the 'Ann. ITD', '1Y', '3Y' and '5Y options. No 'ITD' should be available. A new entry point into the 'portfolio-analysis-service' should exist to provide data for this new page. It should accept the start date and projection date as inputs; the UI should default the 'start date' to be the most recent record (leaving this input blank on the API should also default to the most recent date that has data for the given account. the projection buttons '1Y, '5Y', '10Y' or '20Y' should be resolved to an explicit date that many years into the future. The API does not take these as direct inputs, it must have a date. Therefore the 'explicit date' option is a simple pass-through to the API. The payload response from the API is the same structure as the 'positions' and 'overview' page - utilizing 'periodicity' but only a single attribute ('market value') and returning a time series of historical market value up until the latest observation (with correct periodicity buckets) and then using the input attributes to select out and project the latest market value forward using the appropriate returns, each future projection should be a new series of data so that it can be clearly rendered in the Dash App. As an example, if market_value data goes from 2016-2026 with a monthly periodicity the response will have 120 data points for a single series. If the projection was set using the '10Y' button and the '3Y' and '5Y' returns then two series start at the 2026 date and run for 120 monthly results out to 2036. Take the annualized 3Y or 5Y return, multiple by sqrt(260) to get the daily return, then project forward the last market_value daily by this return, applying periodicity buckets as an overlay afterwards."

## Clarifications

### Session 2026-09-22

- Q: With zero returns currently selected, should the chart show the historical line alone, or
  an empty-state prompt (matching Overview/Positions/Performance's own "select at least one
  metric" pattern)? -> A: The historical line alone -- no empty-state message. This is not a
  special case bolted on afterward; it reflects that the historical line is meaningful on its
  own, unlike a genuinely empty chart. Confirms FR-013 as originally specified.
- Q: Should the "start date" (defaulting to the account's most recent record) be a visible,
  user-editable control, or an internal-only default with no UI control? -> A: A visible,
  editable control -- a UI default implies a UI control to default, and it lets a user ask "what
  if I'd started projecting from an earlier date." Confirms FR-007 as originally specified.
- Q: When an attempted projection date is not strictly later than the start date, how should
  that be communicated? -> A: An inline validation message MUST be shown alongside the calendar
  control (not a silent revert with no feedback) -- reverses the original draft's silent-revert
  assumption. FR-014 updated accordingly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a Preset Future Projection of Portfolio Value (Priority: P1)

Someone planning ahead wants a quick sense of where their portfolio could be years from now if it
kept growing the way it has. They open the page that used to be called "Income" — now called
"Projection" — pick a return they trust (say, their 5-year return), click "10Y", and see their
account's actual market-value history followed by a clearly distinguished projected line running
ten years into the future.

**Why this priority**: This is the entire reason the page exists. Every other capability builds on
this one working correctly, and it delivers value entirely on its own.

**Independent Test**: Open the Projection page for an account with several years of history,
select the "5Y" return, click "10Y", and verify the chart shows the account's historical
market-value line followed by a single projected line running from today to ten years from now,
visually distinct from the historical portion.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The Income page no longer exists and Projection takes its place
  Given I am looking at the navigation menu
  Then there is no "Income" entry
  And there is a "Projection" entry in the position "Income" used to occupy

Scenario: A preset horizon button projects forward from today
  Given I am on the Projection page for an account with over five years of recorded history
  And I have selected the "5Y" return
  When I click the "10Y" horizon button
  Then the chart shows the account's historical market value up to today
  And a single projected line continues from today's value to ten years from today
  And the historical and projected portions are visually distinguishable from one another

Scenario: Each preset horizon button projects to the matching number of years ahead
  Given I am on the Projection page for an account with over twenty years of recorded history
  And I have selected the "3Y" return
  When I click each of "1Y", "5Y", "10Y" and "20Y" in turn
  Then the projected line's end point moves to 1, 5, 10 and 20 years from today respectively

Scenario: A return with insufficient history produces no projection, not an error
  Given I am on the Projection page for an account with under three years of recorded history
  When I select the "3Y" return and click any horizon button
  Then no projected line is drawn for the "3Y" return
  And the historical market-value line still renders normally with no error shown

Scenario: With no return selected, the historical line still renders on its own
  Given I am on the Projection page for an account with recorded history
  And no return is currently selected
  Then the chart shows only the historical market-value line
  And no error or empty-state message is shown
```

---

### User Story 2 - Project to an Exact Chosen Date (Priority: P2)

Someone with a specific goal in mind — a retirement date, a large purchase, a child's education —
wants to see their projected portfolio value on that exact date, not just at the nearest preset
horizon.

**Why this priority**: This is a refinement of User Story 1's core capability rather than a
separate one — the chart, the returns, and the historical line all already exist once US1 is
built. It is next because it is the most-requested kind of flexibility once the basic projection
works.

**Independent Test**: Open the Projection page, pick a date five and a half years from today using
the calendar control (a horizon no preset button reaches), and verify the projected line ends
exactly on that date rather than on the nearest preset horizon.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Picking an exact date projects to that date
  Given I am on the Projection page for an account with recorded history
  And I have selected the "1Y" return
  When I pick a date five and a half years from today using the calendar control
  Then the projected line ends exactly on that chosen date

Scenario: Clicking a preset horizon after picking an exact date replaces the chosen date
  Given I have picked an exact projection date using the calendar control
  When I click the "1Y" horizon button
  Then the projection now ends one year from today, not on my previously chosen date
  And the calendar control shows the date the "1Y" button resolved to

Scenario: A chosen date that is not in the future is rejected
  Given I am on the Projection page
  When I attempt to pick a projection date that is today or earlier
  Then that date is not accepted as the projection target
  And an inline message next to the calendar control explains why it was rejected
  And the chart continues showing the most recently valid projection
```

---

### User Story 3 - Compare Multiple Return Scenarios Side by Side (Priority: P3)

Someone unsure which historical return best represents what to expect going forward wants to see
more than one possibility at once — for example, both the 3-year and 5-year return — so they can
judge the range of plausible outcomes rather than commit to a single guess.

**Why this priority**: This multiplies the value of User Stories 1 and 2 but is not required for
either to be useful on its own — a single selected return already delivers a complete, useful
projection.

**Independent Test**: Select both the "3Y" and "5Y" returns, click "10Y", and verify two distinct
projected lines both start at today's value and diverge from each other as they run to ten years
from now.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Selecting two returns draws two projected lines from the same starting point
  Given I am on the Projection page for an account with over five years of recorded history
  When I select both the "3Y" and "5Y" returns and click "10Y"
  Then two projected lines are shown, one labelled "3Y" and one labelled "5Y"
  And both lines begin at the same point — today's market value
  And each line ends at the same date — ten years from today

Scenario: Selecting a third return adds a third distinct line without disturbing the other two
  Given two returns are already selected and their projected lines are shown
  When I additionally select the "Ann. ITD" return
  Then a third projected line labelled "Ann. ITD" appears
  And the two previously shown lines are unchanged
```

---

### Edge Cases

- **No account has any recorded history**: the page shows the same "no data" treatment already
  used elsewhere in the product rather than an error.
- **The chosen or resolved projection date falls before the start date**: rejected before any
  projection is attempted (User Story 2's rejection scenario) — a projection can only run forward
  in time.
- **The start date itself is moved earlier by the user** (see Assumptions — the start date is a
  visible, user-adjustable control defaulting to the account's most recent recorded date): the
  historical portion of the chart still runs from the account's true earliest date up to the new
  (earlier) start date, and every projection now begins from that earlier point's market value
  instead of today's.
- **A very long combined span** (e.g. twenty years of history plus a twenty-year projection):
  the chart remains readable — the same calendar-aligned, coarser-when-appropriate plotting
  already available elsewhere in the product applies across the whole combined span, historical
  and projected alike.
- **The data service is unavailable**: the same error treatment already used on every other page
  applies; the page does not silently show a stale or partial projection.
- **Switching accounts mid-session**: the start date, projection date/horizon, and selected
  returns all reset to that account's own defaults, consistent with how every other page resets
  its controls on an account switch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST remove the "Income" navigation entry and its page entirely.
- **FR-002**: The system MUST add a "Projection" navigation entry in the position the "Income"
  entry previously occupied, leading to a new page.
- **FR-003**: The Projection page MUST let the user choose an account, consistent with every other
  account-scoped page in the product.
- **FR-004**: The Projection page MUST offer four preset projection-horizon controls labelled
  "1Y", "5Y", "10Y" and "20Y", each resolving to the date that many years after the current start
  date.
- **FR-005**: The Projection page MUST offer a calendar control letting the user pick any future
  date directly as the projection target, as an alternative to the four preset horizons.
- **FR-006**: Exactly one projection target date MUST be in effect at any time — set by whichever
  of the preset horizons or the calendar control was used most recently — and the calendar control
  MUST always display the date currently in effect, however it was set.
- **FR-007**: The Projection page MUST offer a "start date" control, defaulting to the selected
  account's most recently recorded date, from which historical data ends and every projection
  begins.
- **FR-008**: The Projection page MUST offer the same set of selectable returns already used on
  the Performance page, **except** the plain "ITD" measure: "Ann. ITD", "1Y", "3Y" and "5Y". Zero,
  one, or many of these MAY be selected at once.
- **FR-009**: The main chart MUST show exactly one historical market-value line, covering the
  selected account's full recorded history through the current start date, regardless of which
  returns are selected.
- **FR-010**: The main chart MUST show one additional projected line per currently selected
  return, each running from the start date's market value to the current projection target date.
- **FR-011**: Every projected line MUST begin at the same point — the market value on the current
  start date — and MUST be visually distinguishable both from the historical line and from every
  other projected line shown at the same time.
- **FR-012**: A return that cannot be computed for the selected account (insufficient recorded
  history for that return) MUST be silently omitted from the projections shown, without an error,
  consistent with how the Performance page already treats a measure without enough history.
- **FR-013**: With no return currently selected, the chart MUST still show the historical
  market-value line on its own — this is not treated as an empty state.
- **FR-014**: An attempted projection target date that is not strictly later than the current
  start date MUST be rejected, the chart MUST continue showing the most recently valid projection
  rather than an invalid or blank one, and an inline validation message explaining the rejection
  MUST be shown alongside the calendar control (Clarifications session 2026-09-22).
- **FR-015**: Switching the selected account MUST reset the start date, the projection target, and
  the selected returns to that account's own defaults, consistent with every other page's
  account-switch behaviour.
- **FR-016**: The historical portion and every projected portion of the chart MUST be plotted at a
  consistent, calendar-aligned interval across the whole combined span, so a long combined span of
  history plus projection remains readable rather than overwhelming the chart with one point per
  business day.
- **FR-017**: The Projection page's error and "service unavailable" treatment MUST be consistent
  with every other page's existing treatment of the same conditions.
- **FR-018**: A capability MUST exist to produce, for a chosen account, start date and projection
  target date, the historical market-value series described in FR-009 together with one projected
  series per requested return as described in FR-010, each projected series computed by carrying
  the market value on the start date forward using that return's own historical rate, so that this
  page's chart can be rendered directly from the response.

### Key Entities *(include if feature involves data)*

- **Projection Request**: An account, a start date (defaulting to that account's most recently
  recorded date), a projection target date, an interval at which to bucket both the historical and
  projected data, and zero or more requested returns.
- **Historical Series**: The account's actual recorded market value from its earliest date through
  the request's start date, bucketed at the requested interval. Exactly one per request,
  independent of which returns were requested.
- **Projected Series**: One per requested return. A sequence of projected market-value points
  beginning at the start date's actual market value and running to the projection target date,
  bucketed at the requested interval, each point reflecting the compounding effect of that
  return's own historical rate applied since the start date.
- **Return**: One of "Ann. ITD", "1Y", "3Y", "5Y" — the same return measures already computed and
  named by the Performance capability, minus the plain, non-annualized "ITD" measure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see a ten-year portfolio projection in three interactions or fewer
  (select a return, click a horizon, done) from landing on the page.
- **SC-002**: A user can project to any specific future date, not just the four preset horizons,
  without leaving the page.
- **SC-003**: A user viewing two or more selected returns can visually tell each projected line
  apart, and can tell every projected line apart from the historical line, without hovering or
  clicking anything.
- **SC-004**: 100% of navigation to the position the "Income" entry previously occupied now leads
  to the Projection page; no page or link in the product still references "Income".
- **SC-005**: A twenty-year combined history-plus-projection view remains as readable as a
  one-year view — the number of plotted points does not grow unmanageably with the span chosen.
- **SC-006**: Choosing a return the account does not yet have enough history for produces a
  readable chart (the historical line, and any other valid returns' projections) rather than an
  error or a blank page.

## Assumptions

- The account's own most recently recorded date is used as the default start date; the UI does
  not require the user to specify one before a first projection can be shown.
- No separate "how far back to show history" control exists — the historical portion of the chart
  always spans the account's full recorded history through the start date. Limiting how much
  history is shown is out of scope for this feature.
- The label "Ann. ITD" refers to the same annualized inception-to-date return already computed and
  labelled "ITD (Ann.)" on the Performance page; the shorter label is used here purely for display
  concision, not a different calculation.
- Projected values are a straightforward, transparent forward compounding of the selected return's
  own historical rate — no additional adjustment (fees, inflation, volatility, tax) is applied, and
  the chart does not represent a guarantee or a range of confidence, only a single illustrative
  path per selected return.
- The four preset horizons (1Y, 5Y, 10Y and 20Y) are fixed, not user-configurable, and are counted
  from the current start date, not always from today — so moving the start date earlier also moves
  what "1Y" etc. resolve to.
- Requires a new capability in the portfolio analysis service able to produce, for a given account,
  start date and projection target date, the historical-plus-projected market-value data described
  in FR-018 — this capability does not exist yet and is a prerequisite dependency for this feature,
  to be specified and built as its own effort before this page can be connected to real data.
- This feature does not change or remove the Performance page or its own return calculations; it
  reuses the same return definitions for its own, separate projection purpose.
