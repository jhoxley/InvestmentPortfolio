# Implementation Plan: Periodicity Control for the Projection Page

**Branch**: `023-projection-periodicity-controls` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/023-projection-periodicity-controls/spec.md`

## Summary

Add the shared Periodicity button group (built by feature 021's `build_periodicity_control`) to the
Projection page's parameters bar, and wire it exactly as Overview/Positions are wired: a
page-scoped `dcc.Store` holding `{value, explicit}`, one callback that latches an explicit click,
one that derives an interval when nothing has been chosen, one that styles the buttons from the
store, and a chart callback that reads the store. Today `_render_chart` derives an interval inline
and discards it; this feature replaces that inline call with the store so the interval is visible,
overridable and sticky. The derivation *span* is unchanged (account's earliest record → projection
target), so default charts are identical to today. No backend change: `get_projection` already
accepts `periodicity`.

## Technical Context

**Language/Version**: Python 3.11+ (existing project)
**Primary Dependencies**: Dash, dash-bootstrap-components, pydantic, structlog (all existing; no new dependencies)
**Storage**: N/A (per-page in-browser `dcc.Store`; nothing persisted)
**Testing**: pytest; pytest-bdd + Selenium/Chrome for BDD (existing `tests/bdd`), plain pytest for `tests/unit`
**Target Platform**: Desktop/tablet browsers via the existing Dash app
**Project Type**: Web application (Dash UI over `portfolio-analysis-service`)
**Performance Goals**: One chart fetch per user action (no stale intermediate fetch after a horizon click); loading feedback unchanged
**Constraints**: Must pass `ruff` and `mypy`; no Projection-specific periodicity config; no callback id collisions (`tests/unit/test_callback_registration.py`)
**Scale/Scope**: 1 page, 1 layout bar, ~4 callbacks, 2 BDD feature files

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 — still passing.*

| Principle | Assessment |
|-----------|------------|
| I. API-sourced data, no local business logic | PASS. The UI only chooses an interval string and passes it to the service; aggregation stays server-side. `derive_periodicity` is presentational parameter selection already accepted in 021 and already used by this page. |
| II. Layered API architecture | PASS / N/A. UI-only change; no service layers touched. |
| III. Test-first BDD | PASS. Gherkin from the spec becomes two executable feature files written and seen failing before implementation (see tasks). |
| IV. Configuration over hard-coding | PASS. Labels, order and thresholds come from the existing `periodicity` config block; no new literals. |
| V. Standard libraries / SOLID / static analysis | PASS. Reuses the shared component and helpers; no bespoke replacement. `ruff` + `mypy` must stay clean. |
| UX standards | PASS. Buttons disable while the chart refreshes; loading feedback unchanged. |

No violations, so the Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/023-projection-periodicity-controls/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-contract.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root: `portfolio-browser/`)

```text
src/
├── layout/shell.py                  # add Periodicity control to _build_projection_parameters_bar
└── pages/projection.py              # store + 3 new callbacks; _render_chart reads the store;
                                     # module docstring updated (no longer "no visible control")
config/                              # unchanged (existing periodicity block reused)
src/components/periodicity_controls.py   # unchanged (already page-prefix generic)

tests/
├── bdd/features/projection_periodicity.feature            # new — User Story 1
├── bdd/features/projection_periodicity_defaults.feature   # new — User Story 2
├── bdd/steps/test_projection_steps.py                     # extended with new steps
└── unit/test_projection_page.py                           # derivation/latch/style callback unit tests
```

**Structure Decision**: Existing single Dash project. All production changes are confined to
`shell.py` and `projection.py`; the shared component already takes a `page_prefix`, so
`"projection"` yields ids `projection-parameters-periodicity-<key>` and
`projection-periodicity-store` with no component change.

## Design Notes

- **Callbacks (mirror `overview.py`)**: `_apply_periodicity_click` (button `n_clicks` + page-scope
  input → `{value, explicit: True}`), `_derive_periodicity` (see below), `_style_periodicity_buttons`
  (store → each button's `active`/`outline`), and the existing `_render_chart` reading the store.
- **Single fetch per action**: unlike Overview, Projection's chart takes the projection target as a
  `State`, not an `Input`, and the derive callback is what fires on a target change. The derive
  callback listens to the target store, account and accounts store, and *always writes* the store —
  with the derived value when nothing is explicit, or the unchanged store contents (explicit stays
  `True`) when it is. The chart callback, downstream of the store, therefore runs exactly once per
  target change and always sees the final interval (research.md #2).
- **Span unchanged**: derivation still uses the account's earliest recorded date through the
  target date, via the existing `_derive_projection_periodicity` (refactored to return a key or
  `None`), so FR-010 holds.
- **Explicit-ness**: only the click callback sets `explicit: True`; the derive callback never does.
  The store is created in the page layout, so it resets on revisit, matching the other pages.
- **Disabled during refresh**: `running=[...]` on `_render_chart` for the five buttons, as on Overview.

## Risks

- BDD steps for projection currently assume the chart re-renders on target-store change; moving the
  target to `State` changes that trigger path. Existing scenarios must stay green (tasks include a
  full projection-suite run).
- Callback id collisions: all new callbacks have projection-only Inputs, and the store Output uses
  `allow_duplicate=True`; `test_callback_registration.py` is the backstop.
- Spec 022's docstring/FR-016 wording says the interval is "not user-selectable"; this feature
  supersedes that and the docstring is updated with the change.
