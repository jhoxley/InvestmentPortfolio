# Feature Specification: Date Range Shortcut Buttons on Overview

**Feature Branch**: `017-chart-date-range-shortcuts`
**Created**: 2026-07-16
**Status**: Draft
**Input**: User description: "for the 'Overview' line chart implemented in the previous feature, add some short-cuts to the navigation parameters section - buttons for "YtD", "1Y", "3Y", "5Y" and "All". These set the from date to 1st Jan current year ("YtD"), one year earlier than today ("1Y"), three years earlier ("3Y") and five years earlier ("5Y") and earliest from date for "All" button. In each case the 'to' field stays as today. On clicking the button the from/to dates are updated and a suitable query+refresh via the web service is initiated to reflect the updated date range."

## Clarifications

### Session 2026-07-16

- Q: What should happen if the user clicks a shortcut button while the chart is still loading/refreshing from a previous action (another shortcut click, a manual date edit, an account switch, or the initial page load)? → A: Ignore new clicks until the current refresh finishes (buttons disabled while loading).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Jump to a common reporting period in one click (Priority: P1)

A user viewing the Overview performance chart wants to quickly focus on a
standard reporting period — year-to-date, the last 1, 3, or 5 years —
without manually operating the "from"/"to" date pickers.

**Why this priority**: This is the core value of the feature — replacing a
multi-step manual date-picker interaction with a single click for the
reporting periods people actually ask for most often.

**Independent Test**: With the Overview chart displayed, click each of the
"YtD", "1Y", "3Y", and "5Y" buttons in turn and verify the "from"/"to" date
fields and the chart itself update to the correct range each time.

**Acceptance Scenarios**:

1. **Given** the Overview chart is displayed, **When** the user clicks
   "YtD", **Then** the "from" date updates to 1st January of the current
   year, the "to" date updates to the most recently completed business day,
   and the chart refreshes to show only data within that range.
2. **Given** the Overview chart is displayed, **When** the user clicks
   "1Y", **Then** the "from" date updates to exactly one year before today,
   the "to" date updates to the most recently completed business day, and
   the chart refreshes accordingly.
3. **Given** the Overview chart is displayed, **When** the user clicks
   "3Y", **Then** the "from" date updates to exactly three years before
   today and the chart refreshes accordingly.
4. **Given** the Overview chart is displayed, **When** the user clicks
   "5Y", **Then** the "from" date updates to exactly five years before
   today and the chart refreshes accordingly.
5. **Given** the user has just clicked a shortcut button, **When** they look
   at the "from"/"to" date fields, **Then** the fields show the exact dates
   now being charted, not the button's label.

---

### User Story 2 - See an account's full history in one click (Priority: P2)

A user wants to see the complete recorded history for the currently
selected account without knowing or looking up its earliest available date.

**Why this priority**: Valuable and asked for directly, but a distinct,
secondary capability from the fixed-period shortcuts in User Story 1 (it
looks up a per-account date rather than computing a fixed calendar offset),
and the feature already delivers most of its value without it.

**Independent Test**: With the Overview chart displayed, click "All" and
verify the "from" date updates to the selected account's earliest recorded
date, the "to" date updates to the most recently completed business day,
and the chart refreshes to show the account's complete history.

**Acceptance Scenarios**:

1. **Given** the Overview chart is displayed for an account, **When** the
   user clicks "All", **Then** the "from" date updates to that account's
   earliest recorded date and the chart refreshes to show its complete
   history.
2. **Given** the user has switched to a different account, **When** they
   click "All", **Then** the "from" date reflects the newly-selected
   account's own earliest recorded date, not the previous account's.

---

### Edge Cases

- What happens when a clicked shortcut's computed "from" date is earlier
  than the selected account's earliest recorded date (e.g., "5Y" clicked on
  an account with only 2 years of history)? The "from" date MUST be clamped
  to the account's earliest recorded date, so the chart shows that
  account's complete available history rather than requesting an
  out-of-range date.
- What happens when a shortcut is clicked while zero metrics are toggled
  on? The existing empty-state prompt (from the previous feature) MUST
  still be shown — a shortcut click updates the date range but does not by
  itself satisfy the "at least one metric selected" precondition for
  fetching data.
- What happens when the backing data service is unavailable or errors when
  a shortcut is clicked? The existing error-state message (from the
  previous feature) MUST be shown, consistent with any other date-range
  change.
- What happens to a shortcut-derived date range when the user switches to a
  different account? The date range resets to the newly-selected account's
  own default range (existing behavior), not the previous account's
  shortcut-derived range.
- What happens if the user manually edits the "from" or "to" date after
  clicking a shortcut? The fields behave exactly as any other manual edit —
  there is no "locked in" shortcut state to undo.
- What happens if the user clicks a shortcut button while a chart refresh
  triggered by a previous action (another shortcut click, a manual date
  edit, an account switch, or the initial page load) is still in flight?
  The shortcut buttons MUST be disabled for the duration of any in-flight
  refresh, so the new click has no effect until the current refresh
  completes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Overview page MUST display five date-range shortcut
  buttons — labeled "YtD", "1Y", "3Y", "5Y", and "All" — in the parameters
  section, positioned alongside the existing "from"/"to" date controls.
- **FR-002**: Clicking "YtD" MUST set the "from" date to 1st January of the
  current year.
- **FR-003**: Clicking "1Y" MUST set the "from" date to exactly one year
  before today's date.
- **FR-004**: Clicking "3Y" MUST set the "from" date to exactly three years
  before today's date.
- **FR-005**: Clicking "5Y" MUST set the "from" date to exactly five years
  before today's date.
- **FR-006**: Clicking "All" MUST set the "from" date to the earliest date
  for which the currently selected account has any recorded history.
- **FR-007**: Clicking any of the five shortcut buttons MUST set the "to"
  date to the most recently completed business day (the same value the
  chart already defaults "to" to).
- **FR-008**: If a shortcut's computed "from" date is earlier than the
  selected account's earliest recorded date, the "from" date MUST be
  clamped to the account's earliest recorded date instead.
- **FR-009**: Clicking a shortcut button MUST update the visible "from" and
  "to" date controls to show the newly computed dates.
- **FR-010**: Clicking a shortcut button MUST trigger a fresh chart
  request reflecting the updated date range and the currently-toggled
  metrics, with no further action required from the user.
- **FR-011**: The shortcut buttons MUST remain usable after a manual date
  edit, a metric toggle change, or an account switch — they are not
  one-time or single-use controls.
- **FR-012**: Selecting a different account MUST NOT retain a
  previously-clicked shortcut's date range from the prior account; the date
  range reverts to the newly-selected account's own default range until a
  shortcut is clicked again.
- **FR-013**: The shortcut buttons MUST be disabled while any chart refresh
  is in flight (triggered by a shortcut click, a manual date edit, an
  account switch, or the initial page load), so a click during that time
  has no effect; they MUST become clickable again once the refresh
  completes.

### Key Entities

- **Reporting Period Shortcut**: A named, fixed date-range calculation
  ("YtD", "1Y", "3Y", "5Y", "All") that, when selected, computes a concrete
  "from" date (and reuses the existing "to" date default) for the currently
  selected account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can switch the chart to any of the five common
  reporting periods in a single click, with no manual date-picker
  interaction required.
- **SC-002**: After any shortcut click, the "from"/"to" fields and the
  chart always agree on exactly the same date range.
- **SC-003**: 100% of shortcut clicks result in the chart updating to show
  only data within the newly selected range, without a full page reload.
- **SC-004**: A user viewing an account with less history than a clicked
  shortcut's span still sees a correctly-bounded chart showing that
  account's full available history, with no error.

## Assumptions

- The "to" date set by every shortcut is the same "most recently completed
  business day" value the chart already uses as its own default (from the
  previous feature), not literally today's calendar date — this keeps
  shortcut-selected ranges consistent with the rest of the chart's existing
  behavior and avoids showing a partial, not-yet-closed trading day. The
  user's phrasing ("the 'to' field stays as today") is read as "stays at
  its already-established default," which is this value.
- "1Y"/"3Y"/"5Y" use exact calendar-date offsets from today (e.g., "1Y"
  clicked on 15 March 2026 sets "from" to 15 March 2025), not rounded to
  year boundaries.
- Shortcut buttons are simple one-shot triggers: clicking one immediately
  computes and applies its date range. No persistent "currently active
  shortcut" highlighting is required, since the "from"/"to" fields
  themselves already show the exact range in effect (FR-009, SC-002).
- Clicking a shortcut button only changes the date range; any
  currently-toggled metrics are left exactly as they were.
- This feature only adds shortcut buttons to the existing Overview chart's
  date controls — no new chart, page, or navigation section is introduced,
  and no change to the previous feature's account-switching or
  metric-toggle behavior is intended beyond what FR-012 and the Edge Cases
  above describe.
