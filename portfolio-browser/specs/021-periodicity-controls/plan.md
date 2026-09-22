# Implementation Plan: Periodicity Control for Overview & Positions

**Branch**: `021-periodicity-controls` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/021-periodicity-controls/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a "Periodicity" control to the Overview and Positions parameters bars offering day / week /
month / quarter / year, forward the selection to the analysis service's new `periodicity` query
parameter (its feature 008), and derive a sensible interval from the date-range span whenever the
user has not picked one (≤1y → day, ≤3y → month, ≤5y → quarter, longer → year).

Three decisions shape the whole implementation:

1. **The control is a five-button `ButtonGroup`, not a dropdown.** FR-012's sticky-choice rule
   needs the code to distinguish "the user chose this" from "the system derived this". A
   `dbc.Select`'s only signal is `value`, and a callback writing `value` fires the callbacks
   listening on it exactly as a human change would — demonstrably so in this very codebase, where
   `_sync_date_range_to_selected_account` writes `app-parameters-from-date.date` and `_render_chart`
   fires off it. Telling the two apart through `value` alone therefore needs a
   last-written-value or pending-flag dance whose correctness depends on callback ordering.
   Buttons expose `n_clicks`, which only ever increments on a real click, so user intent is
   unambiguous by construction and needs no ordering assumptions. It also matches the date-range
   shortcuts sitting immediately beside it, which are already a `ButtonGroup` — so "in-line with
   current designs" is satisfied more literally than a dropdown would.

2. **Per-page component IDs, not shared ones.** The existing shared controls
   (`app-parameters-account`, `app-parameters-from-date`, …) use one id across three pages, which
   is precisely what caused feature 020's silent callback collision: Dash hashes an
   `allow_duplicate` Output's callback id from its Inputs alone, so three pages with identical
   Output+Input pairs collapse into one registration. This feature introduces
   `overview-parameters-periodicity-*` and `positions-parameters-periodicity-*` ids from a single
   shared *builder*, so the shared UI is shared code rather than shared DOM ids, and the collision
   class cannot recur. `tests/unit/test_callback_registration.py` (added while closing 020) is the
   backstop.

3. **The effective interval lives in a per-page `dcc.Store`, and that store is the single source
   of truth.** A derive callback writes it when the range changes and no explicit choice has been
   made; a click callback writes it (and latches "explicit") on a button press. Both the button
   styling and the chart read from it, so FR-011's "the control always shows the interval in
   effect" holds by construction rather than by keeping two things in sync.

The service call itself is a one-line addition: an optional `periodicity` argument on the two
client methods, appended to the existing query-parameter list. No chart-shaping code changes —
`_build_figure` plots whatever entries come back, and 008 returns the same entry shape at every
interval.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`, `ruff target-version = py311`)
**Primary Dependencies**: Dash 4.4.0, dash-bootstrap-components, Plotly, Pydantic 2,
pydantic-settings, httpx, PyYAML, structlog — all already in use. **No new dependencies.**
**Storage**: None. This is a presentation layer; the only client-side state is Dash `dcc.Store`
components scoped to a page visit (no persistence, no cookies, no local storage)
**Testing**: `pytest` unit tests (`tests/unit/`), `pytest-bdd` Gherkin scenarios
(`tests/bdd/features/*.feature` + `tests/bdd/steps/*.py`) driven through `dash[testing]`
**Target Platform**: Dash web app served by Flask/uvicorn on localhost; desktop and tablet
viewport widths per the constitution's UX standards
**Project Type**: Single-project Dash UI (`config/`, `src/`, `tests/`, `app.py`), consuming
`portfolio-analysis-service` over HTTP
**Performance Goals**: Strictly better than today for long ranges — a coarser interval returns
far fewer entries (a verified 10-year range drops from 2,608 daily points to 10 annual / 40
quarterly / 120 monthly / 522 weekly), so both transfer and render cost fall. Interval changes
must show a loading state within 100ms per the constitution's UX standards, which the existing
`dcc.Loading` wrapper and `running=` disabled-controls pattern already provide
**Constraints**: MUST NOT re-derive or recompute any aggregation client-side (Principle I) — the
service decides period boundaries and representative values; MUST NOT hard-code the control
label, option labels or the year thresholds (Principle IV) — they belong in `config/content.yaml`;
MUST NOT alter existing account/date/metric/position/stacked controls beyond adding the new one;
MUST NOT add the control to Performance or Income, whose data sources take no interval
**Scale/Scope**: Two pages gain one control each; one new shared component, one new config
section, two client methods extended, two response models extended by one optional field. No new
page, no new endpoint, no new chart type

**Verification constraint (known, not a blocker)**: Chrome is not installed on the current
machine, so the `dash[testing]`/Selenium BDD suite cannot execute here (this is the same gap that
hid 020's collision). BDD scenarios will still be authored as the constitution requires, and the
plan deliberately pushes as much behaviour as possible into pure, browser-free unit-testable
functions — the interval-derivation rule, the config loader, the option mapping and the callback
registry guard are all fully covered without a browser. A human/CI pass with Chrome remains
required to sign the BDD scenarios off.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. API-Sourced Data, No Local Business Logic**: No financial fact is derived client-side.
  The pages pass an interval to the service and plot the entries it returns; period boundaries,
  the representative value for each period, and the omission of empty periods are all the
  service's decisions (its feature 008). The one piece of new client-side logic — mapping a
  date-range *span* to a plotting interval — is a **presentational** choice about chart density,
  not a financial derivation, and is explicitly permitted by this principle's "purely
  presentational transforms" carve-out. It is stated here so a reviewer does not have to guess.
- [x] **II. Layered API Architecture**: Layering is preserved and sharpened —
  `src/services/portfolio_analysis_client.py` (transport) gains one optional parameter and does no
  interval reasoning; `src/components/periodicity_controls.py` (presentation) owns the control and
  the pure derivation function and performs no I/O; `config/content.py` (configuration) owns the
  vocabulary and thresholds. No module gains a second responsibility, and the dependency direction
  (page → component/service → config/model) is unchanged.
- [x] **III. Test-First with BDD (NON-NEGOTIABLE)**: The spec already carries 14 Gherkin
  scenarios; they become `tests/bdd/features/periodicity_control.feature` plus step definitions,
  written before the page wiring. Unit tests for the derivation rule (every threshold and both
  sides of each boundary), the config loader, the option/value mapping, and the client parameter
  are written before their implementations. The Red-Green-Refactor order is explicit in the task
  breakdown, and the browser-free coverage noted above means most of it is actually executable
  here.
- [x] **IV. Configuration Over Hard-Coding**: The control label, the five option labels, their
  service-side values, and the 1/3/5-year thresholds all go into a new `periodicity:` section of
  `config/content.yaml`, loaded and validated fail-fast by the existing typed `ContentConfig`
  loader — following the `nav_sections` precedent. No literal `"Periodicity"`, `"annual"`, `1`,
  `3` or `5` appears in `src/`. (The internal option *keys* remain module constants, matching the
  precedent set by `date_range_controls.py`'s shortcut codes, which that module documents as a
  "fixed, spec-defined set — not user-configurable".)
- [x] **V. Standard Libraries and SOLID Design**: No bespoke machinery — `dbc.ButtonGroup` for the
  control, `dcc.Store` for state, Pydantic for config validation, and stdlib date arithmetic
  reusing `date_range_controls.py`'s existing `_years_before` helper rather than a new one. Single
  responsibility: one new component module for the control + derivation, one config section, one
  optional client parameter. Dependency inversion: pages depend on the shared builder's signature
  and the client Protocol, not on Dash internals or `httpx`. `ruff` and `mypy` must run clean, as
  they do today.
- [x] **UX Standards**: The control sits in the existing parameters bar row, which wraps rather
  than clips at narrower widths; a loading state is already provided by the pages' `dcc.Loading`
  wrapper and the `running=` disabled-controls pattern, satisfying the 100ms feedback rule;
  drill-down paths are untouched. The active interval is visible at a glance from the highlighted
  button, so no displayed figure becomes unexplainable.
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

**Post-Phase-1 re-check (2026-09-22)**: re-evaluated after `research.md`, `data-model.md`, both
contracts and `quickstart.md` were written. All seven gates still pass and the design did not
grow: still one new component module, one new config section, two client methods extended, two
models extended by one optional field, zero new dependencies. Two gates were *strengthened* during
Phase 0 rather than weakened — gate III (the ButtonGroup decision moved the sticky-choice logic
out of un-testable Dash value-write semantics into an `n_clicks` signal plus a pure function, both
coverable without a browser) and gate IV (Phase 0 settled that the thresholds belong in config
while the option keys stay as constants, with the existing `date_range_controls.py` precedent
cited for the split). No Complexity Tracking entries were required.

## Project Structure

### Documentation (this feature)

```text
specs/021-periodicity-controls/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── portfolio-analysis-api.md   # the periodicity parameter this UI consumes
│   └── ui-contract.md              # component ids, callback graph, config schema
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root of `portfolio-browser/`)

```text
config/
├── content.yaml                        # MODIFIED — NEW `periodicity:` section: control label,
│                                       #   five options (label + service value), and the
│                                       #   year thresholds
└── content.py                          # MODIFIED — NEW PeriodicityOption / PeriodicityConfig
                                        #   models + validation (exactly 5 options, unique
                                        #   labels/values, ascending thresholds), hung off
                                        #   ContentConfig

src/
├── components/
│   ├── periodicity_controls.py         # NEW — build_periodicity_control(page_prefix, config),
│   │                                   #   derive_periodicity(from, to, config) (pure),
│   │                                   #   and the id-naming helpers both pages share
│   └── date_range_controls.py          # unchanged — `_years_before` reused, not copied
├── layout/
│   └── shell.py                        # MODIFIED — splice the control into the Overview and
│                                       #   Positions parameters bars only (Performance and the
│                                       #   static placeholder bar untouched)
├── pages/
│   ├── overview.py                     # MODIFIED — periodicity store + click/derive callbacks
│   │                                   #   (page-scoped), and pass the interval when fetching
│   ├── positions.py                    # MODIFIED — the same three additions
│   ├── _overview_chart.py              # unchanged — plots whatever entries are returned
│   └── _positions_chart.py             # unchanged — ditto, incl. stacked mode
├── services/
│   └── portfolio_analysis_client.py    # MODIFIED — optional `periodicity` on get_timeseries()
│                                       #   and get_position_timeseries(), on both the Protocol
│                                       #   and the HTTP implementation
└── models/
    └── portfolio_analysis.py           # MODIFIED — optional `periodicity` field on
                                        #   TimeSeriesResponse and PositionTimeSeriesResponse
                                        #   (the service now echoes it; captured so it can be
                                        #   asserted rather than silently ignored)

tests/
├── bdd/
│   ├── features/
│   │   └── periodicity_control.feature # NEW — the spec's 14 scenarios (US1/US2/US3)
│   └── steps/
│       └── periodicity_control_steps.py# NEW — step definitions
└── unit/
    ├── test_periodicity_derivation.py  # NEW — every threshold, both sides of each boundary,
    │                                   #   "week is never derived", degenerate spans
    ├── test_periodicity_controls.py    # NEW — builder output: label, five options in order,
    │                                   #   per-page ids, active-state styling
    ├── test_content_config.py          # MODIFIED — the new config section's validation rules
    ├── test_portfolio_analysis_client.py # MODIFIED — periodicity reaches the query string;
    │                                   #   omitted when not supplied (backward compatibility)
    └── test_callback_registration.py   # unchanged — automatically covers the new callbacks
```

**Structure Decision**: The existing single-project Dash layout is kept
(`config/` → `src/models/` → `src/services/` → `src/components/` → `src/pages/` → `src/layout/`).
The new control follows the precedent set by `date_range_controls.py` in 018: a single shared
component module that both pages call, so the UI is identical without either page depending on
the other. It diverges from that precedent in exactly one respect — per-page component ids rather
than shared ones — for the callback-collision reason given in the Summary, and that divergence is
documented in `contracts/ui-contract.md` so the next page to reuse the control follows it.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty.
