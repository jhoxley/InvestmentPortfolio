# Implementation Plan: Dash Application Shell

**Branch**: `015-create-template-python` | **Date**: 2026-07-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/015-create-template-python/spec.md`

## Summary

Build the Investment Portfolio Browser's persistent Dash application shell:
a header naming the app, a footer showing version/publish date, a
left-hand navigation menu (≤20% width) offering a handful of placeholder
sections (defaulting to "Overview"), and a main content area whose top
always shows a parameters/controls placeholder above the section's
placeholder body. Navigation between sections must not reload the page.
No real data or API calls are wired up in this feature — that is explicitly
deferred to a subsequent feature per the spec's Assumptions.

Technical approach: a single-project Python/Dash app using Dash's built-in
multi-page routing (`use_pages=True`) so each nav section is a registered
page — this gives no-reload navigation, a default/index page, and a clean
seam for later features to drop in real page content without restructuring
routing. Layout is composed from small, single-responsibility presentational
components (header, footer, sidebar, content-frame) built with
`dash-bootstrap-components` for an accessible, responsive grid (handles the
≤20% sidebar / ≥80% content split and the "shrink, don't collapse" tablet
behavior via Bootstrap's column system). All version/publish-date/nav-label
values are read from a validated YAML config file at startup, never
hardcoded, per the constitution's configuration principle. Behaviour is
specified first as Gherkin scenarios (`pytest-bdd`) exercised against a real
rendered page via Dash's official browser-testing fixtures.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Dash 2.17+ (with built-in Pages routing),
dash-bootstrap-components, Pydantic v2 + PyYAML (typed, validated config)
**Storage**: N/A (no persistence in this feature; config is a static YAML
file, not a data store)
**Testing**: pytest + pytest-bdd (Gherkin scenarios) driving Dash's official
`dash[testing]` browser fixtures (`dash_duo`, Selenium-based) for end-to-end
shell behaviour; plain pytest for config-loading unit tests
**Target Platform**: Web browser (desktop and tablet widths), served by the
Dash/Flask development server locally (no deployment target defined yet)
**Project Type**: Single-project web UI (Dash is both the app server and
the rendering layer; no separate frontend/backend split applies)
**Performance Goals**: Not applicable to this feature — no API calls occur
that would trigger the constitution's 100ms loading-state requirement; that
requirement will be re-verified when a future feature adds real data calls
**Constraints**: No client-side calculation of financial data (constitution
Principle I) — trivially satisfied since this feature has no financial data
at all; sidebar must never exceed 20% width; sidebar must shrink rather than
collapse at tablet widths (per Clarifications)
**Scale/Scope**: 4 placeholder navigation sections (Overview, Positions,
Performance, Income), 1 shared shell layout, no data volume considerations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** This feature displays no financial data and performs no calculations; every value in the content area is a static placeholder. Nothing to source from an API yet — deferred to the next feature by spec design. |
| II. Layered API Architecture | **N/A / compliant-by-design.** No API/data-access/calculation layer exists in this feature. The module split (`components/` presentational, `pages/` routing+content, `config/` settings) keeps a clean seam so a future data-access layer can be added without restructuring the presentation code. |
| III. Test-First with BDD | **Pass (planned), one documented exception.** Each user story becomes a `.feature` file (Gherkin) exercised via `pytest-bdd` + Dash's `dash_duo` browser fixture, written and confirmed failing before the corresponding component/page code exists (see `tasks.md`'s explicit Red checkpoints). Config-loading logic (`config/content.py`, `config/settings.py`) likewise gets failing unit tests first. One exception is recorded in Complexity Tracking below: User Story 3's footer-content scenario cannot start Red because the footer is necessarily built once, in User Story 1, as shared persistent-shell infrastructure. |
| IV. Configuration Over Hard-Coding | **Pass (planned).** App name, version, publish date, and nav section labels live in a validated YAML config file loaded at startup (fail-fast on malformed values), not inlined as string literals. |
| V. Standard Libraries and SOLID | **Pass.** Uses Dash's built-in Pages routing instead of a hand-rolled router, `dash-bootstrap-components` instead of hand-rolled CSS grid, Pydantic for config validation instead of ad-hoc parsing. Each component module has one rendering responsibility. `ruff` + `mypy` run in CI. |
| User Experience Standards | **Pass.** Sidebar capped at 20% width (dbc grid columns); nav switches require exactly one click (well under the 2-interaction budget); layout remains usable at desktop/tablet widths per Clarifications. Loading-state requirement not yet applicable (no API calls in this feature). |

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-create-template-python/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
portfolio-browser/
├── app.py                        # Entrypoint: builds Dash app (use_pages=True), assembles shell layout, runs server
├── config/
│   ├── settings.py               # Pydantic-settings: runtime settings (HOST, PORT, DEBUG) from env/.env
│   ├── content.py                # Pydantic model + loader/validator for content.yaml (fail-fast at startup)
│   └── content.yaml               # Non-secret static config: app_name, version, published_date, nav_sections
├── src/
│   ├── components/
│   │   ├── header.py              # Persistent header (FR-001)
│   │   ├── footer.py              # Persistent footer showing Build Info (FR-002)
│   │   └── sidebar.py             # Left-hand nav menu, ≤20% width, active-link state, scrollable overflow (FR-003, FR-007, FR-009)
│   ├── layout/
│   │   └── shell.py               # Composes header + sidebar + page content frame + parameters bar with concrete placeholder controls (FR-004, FR-005, FR-008)
│   └── pages/                     # Dash Pages — one placeholder module per nav section
│       ├── overview.py            # Default page ("/", FR-007 default section)
│       ├── positions.py
│       ├── performance.py
│       └── income.py
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   ├── application_shell.feature       # User Story 1
│   │   │   ├── section_navigation.feature       # User Story 2
│   │   │   └── build_info_footer.feature        # User Story 3
│   │   └── steps/
│   │       └── test_shell_steps.py
│   └── unit/
│       └── test_content_config.py               # Validates fail-fast config loading
├── pyproject.toml                  # Dependencies, ruff + mypy configuration
├── .env.example
└── CLAUDE.md
```

**Structure Decision**: Single Python project rooted at `portfolio-browser/`
(this repository). Dash's Pages feature (`pages_folder="src/pages"`) is used
instead of a hand-rolled router or a separate frontend project, since Dash
itself renders the UI — there is no separate "frontend" to split out (Option
2/3 from the template are not applicable). `config/` is kept as a top-level
package, distinct from `src/`, so it's obvious at a glance that it holds
externally-tunable values rather than application logic, per the
constitution's configuration principle.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| User Story 3's `build_info_footer.feature` step definitions pass immediately (no Red state) rather than following strict Red-Green-Refactor | The footer (`src/components/footer.py`) is unavoidably shared, persistent-shell infrastructure (FR-008) built once in User Story 1 alongside the header and sidebar, since all three render as one atomic shell | Deferring footer construction to User Story 3 was rejected: User Story 1's and User Story 2's own acceptance scenarios explicitly assert the footer persists unchanged across navigation, so the footer must already exist by User Story 1 — deferring it would make earlier, higher-priority stories' own tests unsatisfiable until a lower-priority story lands, inverting the stories' priority order in practice |

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (data-model.md, contracts/ui-contract.md,
quickstart.md): the design introduces no data access, no calculations, and
no new dependencies beyond those already assessed above. All rows in the
Constitution Check table above still hold. **Gate: Pass.**
