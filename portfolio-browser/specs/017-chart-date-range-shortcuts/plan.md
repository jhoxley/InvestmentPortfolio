# Implementation Plan: Date Range Shortcut Buttons on Overview

**Branch**: `017-chart-date-range-shortcuts` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/017-chart-date-range-shortcuts/spec.md`

## Summary

Add five one-click date-range shortcut buttons ("YtD", "1Y", "3Y", "5Y",
"All") to the Overview page's parameters bar, alongside the existing
Account/From/To controls from `016-link-real-portfolio`. Clicking one
computes a "from" date (a fixed calendar offset for the first four, the
selected account's own earliest recorded date for "All"), clamps it to the
account's earliest recorded date if it would otherwise be out of range, sets
"to" to the chart's existing "most recently completed business day" default,
and triggers the same chart refresh the existing From/To pickers already
trigger. The five buttons are disabled for the duration of any chart
refresh (shortcut click, manual date edit, account switch, or initial load)
per the `/speckit-clarify` decision, using Dash's native `running=` callback
parameter rather than a hand-rolled loading-state store.

Technical approach: this is a pure extension of `016-link-real-portfolio`'s
existing architecture — no new dependency, no new module, no new API
integration. `src/layout/shell.py`'s `_build_overview_parameters_bar()`
gains five `dbc.Button`s. `src/pages/_overview_chart.py` gains one new pure
function (`_shortcut_from_date`) computing/clamping each shortcut's "from"
date, reusing the existing `_earliest_from_date`/`_last_business_day`
helpers. `src/pages/overview.py` gains one new callback
(`_apply_date_range_shortcut`, five `n_clicks` Inputs, `ctx.triggered_id` to
determine which button fired) that sets the very same
`app-parameters-from-date`/`app-parameters-to-date` `date` props the manual
pickers already set — meaning the existing `_render_chart` callback (already
listening to those two props as Inputs) picks up the change and re-fetches
automatically, with zero new fetch/render logic. `_render_chart` gains a
`running=[...]` clause disabling the five new buttons for its duration.

## Technical Context

**Language/Version**: Python 3.11 (unchanged from 015/016)
**Primary Dependencies**: None added. Reuses Dash 2.17+/`dash-bootstrap-components`
(for the new `dbc.Button`s), and `016-link-real-portfolio`'s own
`httpx`/`plotly`/`structlog` stack unchanged — this feature adds zero new
third-party dependencies.
**Storage**: N/A — unchanged from 016 (stateless proxy; `dcc.Store` for
in-session account/attribute caching already exists and is reused, not
extended)
**Testing**: pytest + pytest-bdd + `dash[testing]` (unchanged). The new pure
date-shortcut-computation function gets failing unit tests first
(`tests/unit/test_overview_chart_shaping.py`, extended); the click-through
behavior and button-disabled-during-refresh behavior get failing BDD
scenarios first (`tests/bdd/features/overview_date_range_shortcuts.feature`,
new)
**Target Platform**: Web browser (desktop and tablet widths), Dash/Flask dev
server locally — unchanged
**Project Type**: Single-project web UI (unchanged)
**Performance Goals**: No new performance goal beyond 016's existing 100ms
loading-feedback requirement — the "buttons disabled while loading"
behavior (FR-013) *is* that feedback for this feature, made visible via
`running=` rather than a separate spinner
**Constraints**: No client-side financial calculation (constitution
Principle I, unchanged posture from 016) — `_shortcut_from_date` computes
calendar dates only (offsets and a min/clamp against an already-fetched
account date), never a financial value; the chart continues to plot only
`entries[].{attribute}` values verbatim, unchanged from 016
**Scale/Scope**: 1 page modified further (Overview, already real from 016);
0 new API integration points (reuses 016's three endpoints as-is); 1 new
pure function; 1 new callback; 5 new buttons; 2 user stories (P1: YtD/1Y/3Y/5Y,
P2: All)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** `_shortcut_from_date` computes calendar dates (offsets from today, a min/clamp against a date already returned by `/v1/accounts`) — selection logic, not a financial calculation, matching the same carve-out 016 relied on for its own date-default logic. No new financial fact is derived; the chart still plots only verbatim API values. |
| II. Layered API Architecture | **Pass / N/A change.** No data-access or calculation layer changes — this feature adds zero new API calls, reusing 016's existing client and callback chain unchanged. The one new pure function lives alongside 016's existing pure helpers in `_overview_chart.py`, keeping the same separation. |
| III. Test-First with BDD (NON-NEGOTIABLE) | **Pass (planned).** Both user stories get `.feature` files exercised via `pytest-bdd` + `dash_duo`, written and confirmed failing before the corresponding callback/component code — same discipline as 015/016. `_shortcut_from_date` gets failing unit tests first, including the Feb-29 leap-year edge case. |
| IV. Configuration Over Hard-Coding | **Pass.** Button labels ("YtD", "1Y", "3Y", "5Y", "All") are short, fixed, domain-standard reporting-period abbreviations — not environment-specific config, consistent with how 016 treated fixed UI copy (e.g., empty/error-state text) as source, not config. No new URLs, thresholds, or environment-dependent values are introduced. |
| V. Standard Libraries and SOLID | **Pass.** Uses Dash's own native `running=` callback parameter (verified working on a synchronous callback via a spike test during planning) instead of a hand-rolled `dcc.Store`-based loading flag — the exact kind of "prefer the library's built-in solution" the principle calls for. The year-offset/leap-day edge case is handled with three lines of stdlib `datetime` rather than adding `python-dateutil` for one narrow case, consistent with 016's own precedent of avoiding a dependency for a similarly narrow date-math need. |
| User Experience Standards | **Pass (planned).** Disabling the five buttons during any refresh (FR-013) *is* the loading-state feedback for this control, appearing immediately (Dash sets `running=` state synchronously with the server round-trip starting) — satisfies the 100ms feedback requirement by construction, not by a race-prone timer. |

No violations requiring justification — Complexity Tracking table is empty.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (`data-model.md`, `contracts/ui-contract.md`,
`quickstart.md`):

- **Principle I**: Confirmed — `data-model.md`'s "Reporting Period
  Shortcut" and extended "Date Range" sections show `from_date` is always
  either a fixed calendar offset from today or an already-fetched
  account's own earliest date; no new financial value is derived anywhere
  in this feature.
- **Principle II**: Confirmed — no data-access or calculation layer touched;
  the one new pure function sits alongside 016's existing pure helpers.
- **Principle III**: Confirmed — `overview_date_range_shortcuts.feature`
  covers both user stories plus the FR-013 disabled-during-refresh
  behavior, planned to be written and failing before implementation.
- **Principle IV**: Confirmed — no new config surfaced; button labels are
  fixed UI copy, consistent with existing empty/error-state text treatment.
- **Principle V**: Confirmed by the Phase 0 spike — `running=` verified
  working on a synchronous callback before committing to it as the design,
  avoiding a wrong architectural bet on an unverified assumption.
- **User Experience Standards**: Confirmed — `running=`'s disabled-state
  change is synchronous with the callback starting, satisfying the 100ms
  feedback requirement without a separate timer/spinner mechanism.

All rows still hold. **Gate: Pass.** No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/017-chart-date-range-shortcuts/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
portfolio-browser/
├── src/
│   ├── layout/
│   │   └── shell.py                   # MODIFIED — _build_overview_parameters_bar() gains 5 dbc.Button shortcuts
│   └── pages/
│       ├── _overview_chart.py         # MODIFIED — + _shortcut_from_date(), + _SHORTCUT_* constants
│       └── overview.py                # MODIFIED — + _apply_date_range_shortcut() callback; _render_chart gains running=[...]
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   └── overview_date_range_shortcuts.feature   # NEW — both user stories (P1: YtD/1Y/3Y/5Y, P2: All) + the in-flight-disable edge case
│   │   └── steps/
│   │       └── test_overview_steps.py                   # MODIFIED — new step definitions for shortcut buttons
│   └── unit/
│       └── test_overview_chart_shaping.py                # MODIFIED — + tests for _shortcut_from_date (incl. Feb-29 leap-year offset, clamping)
└── CLAUDE.md
```

**Structure Decision**: No new modules, packages, or dependencies — this
feature is implemented entirely as additive changes to the three files
`016-link-real-portfolio` already created/established
(`src/layout/shell.py`, `src/pages/_overview_chart.py`,
`src/pages/overview.py`), plus their corresponding test files. This is a
deliberate minimal footprint: the feature is a thin, self-contained
extension of an existing, already-layered architecture, and introducing new
structure for it would violate the constitution's SOLID/simplicity guidance
without adding any real separation-of-concerns benefit.

## Complexity Tracking

No violations — table intentionally empty.
