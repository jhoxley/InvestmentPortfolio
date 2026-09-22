# Implementation Plan: Projection Page (replaces Income)

**Branch**: `022-projection-page` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/022-projection-page/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Remove the "Income" page/nav-entry and replace it with "Projection": an account-scoped page,
built on the same Performance-page patterns (account selector, date controls, a
toggle-selected set of return measures, a single `dcc.Graph`), that renders an account's
historical market-value line followed by one projected line per selected return, running from
a user-adjustable start date (defaulting to the account's most recent record) out to a
projection target date set either by a preset horizon button (1Y/5Y/10Y/20Y) or a calendar
picker. All projection math happens server-side in a **new** `portfolio-analysis-service`
capability (`GET /v1/accounts/{account_name}/projection`) whose contract this plan pins but
whose implementation is explicitly deferred as its own effort (spec Assumptions) — this
feature's browser-side work proceeds against that pinned contract via a fake test client,
exactly as `research.md` describes.

Three decisions shape the whole implementation:

1. **The new endpoint reuses `PositionTimeSeriesResponse`'s exact shape**, repurposing its
   `position` discriminator field as a series label (`"Historical"`, `"1Y"`, `"3Y"`, `"5Y"`,
   `"Ann. ITD"`) rather than a position name. The spec says so explicitly ("same structure as
   the 'positions' and 'overview' page"), and it means zero new response-parsing or
   chart-grouping code is needed on the browser — the existing "one trace per distinct
   `position` value" plotting pattern already proven on the Positions page renders this
   directly.

2. **The projection math is the literal formula given in the original request**:
   `daily_rate = annualized_return * sqrt(260)`, compounded daily from the start date's actual
   market value, with periodicity bucketing applied as an overlay afterward by reusing feature
   008's `aggregate_last_observation()` unmodified, once per series. This is recorded verbatim
   in `research.md` rather than "corrected" to a conventional de-annualization, because the
   spec's own Assumptions describe this as "a straightforward, transparent forward compounding"
   with no claim to statistical rigor, and the exact formula was explicitly specified.

3. **"Projection date in effect" (FR-006) is a single-writer `dcc.Store`**, written by either
   the horizon buttons or the calendar picker, with the calendar control unconditionally synced
   from the store — the same pattern 021 used for its periodicity store, extended here to a
   genuine two-writer case (button vs. calendar), which is why an explicit store indirection is
   used instead of two callbacks writing the calendar's `date` prop directly (see
   `contracts/ui-contract.md`'s callback-graph note on avoiding the 020 collision shape).

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`, `ruff target-version = py311`)
**Primary Dependencies**: Dash 4.4.0, dash-bootstrap-components, Plotly, Pydantic 2,
pydantic-settings, httpx, PyYAML, structlog — all already in use. **No new dependencies.**
**Storage**: None — presentation layer only; page state lives in page-scoped `dcc.Store`
components (no persistence, no cookies, no local storage)
**Testing**: `pytest` unit tests (`tests/unit/`), `pytest-bdd` Gherkin scenarios
(`tests/bdd/features/*.feature` + `tests/bdd/steps/*.py`) driven through `dash[testing]`;
browser-side work against the new endpoint is tested via a fake client implementing
`PortfolioAnalysisClient`, since the real endpoint is not yet implemented (see Summary)
**Target Platform**: Dash web app served by Flask/uvicorn on localhost; desktop and tablet
viewport widths per the constitution's UX standards
**Project Type**: Single-project Dash UI (`config/`, `src/`, `tests/`, `app.py`), consuming
`portfolio-analysis-service` over HTTP — this plan covers `portfolio-browser` only; the
service-side endpoint is a pinned-but-deferred contract (`contracts/portfolio-analysis-api.md`)
**Performance Goals**: A twenty-year combined history-plus-projection span MUST remain as
readable as a one-year view (SC-005) — achieved for free by reusing feature 008's periodicity
bucketing on both the historical and projected legs, the same mechanism 021 already verified
collapses a decade of daily data to ~10-120 points depending on interval
**Constraints**: MUST NOT compute any return, growth rate, or projected value client-side
(Principle I) — every `market_value` point rendered, historical or projected, comes from the
service response; the only client-side date arithmetic permitted is the purely presentational
resolution of a horizon *button* to a calendar date (start + N years), the same category of
carve-out 021 already relied on for its interval-derivation rule; MUST NOT alter or remove the
Performance page's own return calculations (spec Assumptions); MUST NOT hard-code the nav
label, horizon labels/offsets, or return labels (Principle IV) — belong in `content.yaml`
**Scale/Scope**: One page removed (Income), one page added (Projection); one new client method
and zero new response models (full reuse of `PositionTimeSeriesResponse`); one new config
section plus one nav-entry edit; no change to Overview, Positions, or Performance

**Known scope boundary (not a blocker, explicitly deferred)**: The actual
`GET /v1/accounts/{account_name}/projection` implementation in `portfolio-analysis-service` is
**out of scope for this plan's tasks**. Per the spec's own Assumptions, it is "a prerequisite
dependency... to be specified and built as its own effort," most naturally via its own
`/speckit-specify` cycle in that repo. This plan's Phase 0/1 artifacts pin its contract so that
future effort and this feature's browser-side tasks can each proceed against a stable interface
without drifting apart — mirroring exactly how 021 depended on 008 (021's plan.md Assumption,
confirmed correct in practice).

**Verification constraint (known, carried over from 021)**: Chrome is not installed on the
current machine, so `dash[testing]`/Selenium BDD scenarios cannot execute here — the same gap
021 worked around via `tests/bdd/conftest.py`'s environment-conditional auto-skip, which this
feature's BDD scenarios inherit automatically (new scenarios collected from `tests/bdd/` get
the same skip-if-no-browser treatment with no per-feature configuration needed). The unit suite
covers the horizon-date arithmetic, the config schema, the callback registry, and (via the fake
client) the full request/response wiring without a browser.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. API-Sourced Data, No Local Business Logic**: No return, growth rate, or projected
  `market_value` is computed in `portfolio-browser`. The service (once built) owns the
  historical series, the compounding math, and the periodicity bucketing entirely; the browser
  only requests, parses, and plots. The one piece of client-side date logic — resolving a
  horizon button's label to a concrete calendar date — is a purely presentational transform
  (which date to *ask for*, not what value results), the identical category of exception 021's
  Constitution Check already relied on and is called out explicitly here for the same reason:
  so a reviewer doesn't have to infer it.
- [x] **II. Layered API Architecture**: `src/services/portfolio_analysis_client.py` (transport)
  gains one method that does no projection reasoning of its own; `src/pages/projection.py`
  (presentation) owns the horizon-to-date resolution and callback wiring and performs no
  server-side-equivalent calculation; `config/content.py`/`content.yaml` (configuration) own
  the horizon and return vocabularies. Layering direction (page → component/service → config)
  is unchanged from every prior feature.
- [x] **III. Test-First with BDD (NON-NEGOTIABLE)**: The spec's 12 Gherkin scenarios (across
  US1/US2/US3) become `tests/bdd/features/projection_page.feature` plus step definitions using
  a fake `PortfolioAnalysisClient` implementing `contracts/portfolio-analysis-api.md`'s
  response shape (since no live service exists yet — this is a deliberate, documented deviation
  from 021's "verify against a real running service" approach, forced by the endpoint not
  existing, not a relaxation of the principle itself: the scenarios are still real, executable
  Gherkin against real page/callback code, only the HTTP boundary is faked). Unit tests for the
  horizon date-arithmetic, the config loader, and the client's query-parameter construction are
  written before their implementations, per the Red-Green-Refactor task ordering.
- [x] **IV. Configuration Over Hard-Coding**: The nav label, the four horizon labels/year
  offsets, and the four return labels/wire-values all live in a new `projection:` section of
  `config/content.yaml`, validated fail-fast by a new `ProjectionConfig` Pydantic model
  following the `PeriodicityConfig` precedent from 021. No literal `"1Y"`, `10`, `"Ann. ITD"`,
  or `"Projection"` label appears in `src/`.
- [x] **V. Standard Libraries and SOLID Design**: No bespoke machinery — `dbc.ButtonGroup` for
  horizons (matching the Reporting Period Shortcut precedent), `dcc.DatePickerSingle` for both
  date controls (matching the existing From/To pattern), `dcc.Store` for the single-writer
  projection-target state, `build_attribute_toggles()` reused unmodified for the return
  selection. Single responsibility: one new page module, one new chart module
  (`_projection_chart.py`), one new client method, one new config section. Dependency
  inversion unchanged: the page depends on the `PortfolioAnalysisClient` Protocol, not on
  `httpx` directly. `ruff`/`mypy --strict` must run clean, as required of every prior feature.
- [x] **UX Standards**: The page sits in the existing parameters-bar layout pattern (account +
  date controls + shortcut-style buttons), which already wraps rather than clips at narrower
  widths; loading feedback reuses the existing `dcc.Loading`/`running=` pattern (100ms rule);
  the projection date always visible on the calendar control satisfies "no displayed figure
  becomes unexplainable" for FR-006. Drill-down: consistent with Performance (a chart-only
  page, no further drill-down level below it, matching that page's own precedent).
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

**Post-Phase-1 re-check (2026-09-22)**: re-evaluated after `research.md`, `data-model.md`, both
contracts, and `quickstart.md` were written. All seven gates still pass. Phase 0/1 did not
expand scope — still one new page, one new chart module, one new client method, zero new
response models, one new config section. One gate was *clarified* rather than weakened during
design: gate III's live-service-verification approach (021's own quickstart pattern) had to be
explicitly adapted to a fake-client approach here, recorded as a deliberate, documented
deviation forced by the deferred backend rather than a principle relaxation — the BDD scenarios
themselves remain real and executable. No Complexity Tracking entries were required.

## Project Structure

### Documentation (this feature)

```text
specs/022-projection-page/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── portfolio-analysis-api.md   # the deferred projection endpoint's pinned contract
│   └── ui-contract.md              # component ids, callback graph, config schema
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root of `portfolio-browser/`)

```text
config/
├── content.yaml                        # MODIFIED — `nav_sections`' `income` entry replaced
│                                       #   by `projection` (same order:4); NEW `projection:`
│                                       #   section (4 horizons, 4 returns)
└── content.py                          # MODIFIED — NEW ProjectionHorizon / ProjectionReturn /
                                        #   ProjectionConfig Pydantic models + validation
                                        #   (exactly 4 horizons, exactly 4 returns, unique
                                        #   keys/labels, positive ascending `years`), hung off
                                        #   ContentConfig

src/
├── components/
│   ├── attribute_toggles.py            # unchanged — build_attribute_toggles() reused as-is
│   └── date_range_controls.py          # unchanged — date-arithmetic helpers reused
├── layout/
│   └── shell.py                        # MODIFIED — projection route's parameters bar
│                                       #   (start date + horizons + calendar + return toggles)
│                                       #   replaces income's placeholder bar
├── pages/
│   ├── income.py                       # DELETED
│   ├── projection.py                   # NEW — page layout + all callbacks (see
│   │                                   #   contracts/ui-contract.md's callback graph)
│   ├── _projection_chart.py            # NEW — _build_figure(), a new color mapping keyed by
│   │                                   #   series label ("Historical" + the 4 return labels)
│   └── performance.py                  # unchanged — read as this feature's structural model,
│                                       #   not modified
├── services/
│   └── portfolio_analysis_client.py    # MODIFIED — NEW get_projection() on both the Protocol
│                                       #   and the HTTP implementation, mirroring
│                                       #   get_position_timeseries() closely
└── models/
    └── portfolio_analysis.py           # unchanged — PositionTimeSeriesResponse reused as-is

tests/
├── bdd/
│   ├── features/
│   │   └── projection_page.feature     # NEW — the spec's 12 scenarios (US1/US2/US3)
│   └── steps/
│       └── projection_page_steps.py    # NEW — step definitions + fake client implementing
│                                       #   contracts/portfolio-analysis-api.md's response shape
└── unit/
    ├── test_projection_horizons.py     # NEW — start+N-years date arithmetic, leap-day edge
    │                                   #   case (reusing 021's `_years_before` leap-day test
    │                                   #   as the template for its forward equivalent)
    ├── test_projection_page.py         # NEW — layout construction, callback wiring, fake-
    │                                   #   client-backed render/validation behavior
    ├── test_content_config.py          # MODIFIED — new ProjectionConfig validation rules
    ├── test_portfolio_analysis_client.py # MODIFIED — get_projection()'s query-parameter
    │                                   #   construction (start omitted when None,
    │                                   #   projection_date always present, repeated `return`)
    └── test_callback_registration.py   # unchanged — automatically covers the new callbacks
```

**Structure Decision**: Single-project Dash layout unchanged. `projection.py` follows
`performance.py`'s structure directly (single page module owning layout + all callbacks, one
sibling `_*_chart.py` module for the pure figure-building function) rather than 021's
shared-component-across-pages precedent, because — unlike periodicity — nothing here is shared
with Overview/Positions/Performance; Projection is a standalone page the way Performance itself
is. The one genuine addition to precedent is the `projection-target-store` two-writer
indirection (button vs. calendar), documented in `contracts/ui-contract.md` so a future page
needing "two controls, one effective value" copies that shape rather than re-deriving it.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty.
