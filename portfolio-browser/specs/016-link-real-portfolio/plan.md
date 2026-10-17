# Implementation Plan: Account Performance Chart on Overview

**Branch**: `016-link-real-portfolio` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/016-link-real-portfolio/spec.md`

## Summary

Replace the Overview page's placeholder content with a real, auto-populating
line chart of account performance, sourced entirely from
`portfolio-analysis-service`'s `/v1/accounts`, `/v1/timeseries/attributes`,
and `/v1/accounts/{account_name}/timeseries` endpoints. On first load, the
page auto-selects the alphabetically-first account and the `market_value`
metric, computes the "to" date as the last completed business day, and
fetches/renders the chart with no user action required. Account switching,
date-range edits, and metric toggles are Overview-page-scoped controls that
each trigger a re-fetch and re-render via Dash callbacks — no financial
calculation happens client-side; the browser only requests, shapes, and
plots exactly what the API returns.

Technical approach: a new thin `src/services/portfolio_analysis_client.py`
HTTP client (httpx, mirroring `portfolio-analysis-service`'s own
`app/clients/market_data_client.py` Protocol + concrete-class pattern) wraps
the three endpoints. Dash callbacks in `src/pages/overview.py` orchestrate
loading accounts → attributes → timeseries, using `dcc.Graph` +
`plotly.graph_objects` (already a transitive Dash dependency, now used
directly) for the chart, `dcc.DatePickerSingle` ×2 for the date range, and
`dbc.Checklist`/`dbc.Switch` + `dbc.Tooltip` for the metric toggles. The
existing shared shell parameters bar (`src/layout/shell.py`) is made
route-aware: on the Overview route it hosts the real Account/date controls;
on every other route it keeps today's static disabled placeholder unchanged.
The metric-toggle panel (Overview-only per FR-007) lives inside the Overview
page's own layout so it naturally disappears on navigation. `dcc.Loading`
wraps the chart output to satisfy the constitution's 100ms loading-feedback
requirement — the first requirement in this codebase to actually exercise it.

## Technical Context

**Language/Version**: Python 3.11 (unchanged from 015)
**Primary Dependencies**: Dash 2.17+, dash-bootstrap-components (existing);
adds `httpx>=0.27` (HTTP client — already the monorepo-standard choice, used
identically by `portfolio-analysis-service`'s own outbound client),
`plotly` (already installed transitively via `dash`; this feature is the
first to import `plotly.graph_objects` directly, so it becomes an explicit
dependency), and `structlog` (already the logging convention in both backing
services; adopted here for consistent structured request/duration/error logs
on the new outbound calls)
**Storage**: N/A — stateless proxy to `portfolio-analysis-service`; no
persistence in the browser beyond in-memory Dash callback state (`dcc.Store`
for the currently-selected account's accounts-payload, scoped to the
session)
**Testing**: pytest + pytest-bdd + `dash[testing]` (`dash_duo`, existing);
the new HTTP client is unit/BDD-tested against `httpx.MockTransport` (no new
mocking dependency — mirrors the pattern already proven in
`portfolio-analysis-service/app/clients/market_data_client.py` and its tests)
**Target Platform**: Web browser (desktop and tablet widths), Dash/Flask dev
server locally — unchanged from 015
**Project Type**: Single-project web UI (unchanged) — the Dash server itself
makes the outbound HTTP calls to `portfolio-analysis-service` (server-to-server),
so there is no browser-side CORS concern
**Performance Goals**: Loading feedback MUST appear within 100ms of any
triggering interaction (account switch, date change, metric toggle) per the
constitution's User Experience Standards — the first feature in this codebase
where that gate is actually exercised, since 015 had no API calls
**Constraints**: No client-side financial calculation (constitution
Principle I) — the chart plots `entries[].{attribute}` values verbatim; the
only client-side arithmetic is the non-financial "last completed business
day" date default (FR-004) and reading `min()` of the two nullable
`from_date`s already returned by `/v1/accounts` (FR-003) — neither derives a
new financial fact. Accounts with no ingested resource are already excluded
by the API's own contract (`/v1/accounts` only lists accounts with ≥1
resource), satisfying the edge case without extra client-side filtering logic.
**Scale/Scope**: 1 page (Overview) rebuilt from placeholder to real; 3 new
API integration points; 1 new HTTP client module; 4 user stories (P1–P4)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** All chart data (accounts, attribute metadata, timeseries entries) comes from `portfolio-analysis-service`. The browser performs zero financial calculations — no returns, PnL, or aggregation logic is reimplemented client-side. The two client-side derivations (last-business-day default, min-of-two-nullable-dates) are date/selection logic, not financial facts, consistent with the constitution's explicit carve-out for "purely presentational transforms." |
| II. Layered API Architecture | **Pass.** New `src/services/portfolio_analysis_client.py` is a pure data-access module (HTTP I/O only, no calculation, no caching) — mirrors the existing layering precedent in `portfolio-analysis-service/app/clients/`. Dash callbacks in `overview.py` are the "transport" layer for this UI (request orchestration + response→chart shaping), depending on the client abstraction (a `Protocol`), not a concrete transport, satisfying dependency inversion. |
| III. Test-First with BDD (NON-NEGOTIABLE) | **Pass (planned).** Each user story (P1–P4) becomes a `.feature` file exercised via `pytest-bdd` + `dash_duo`, written and confirmed failing before the corresponding callback/component code, following the same Red-Green-Refactor discipline as 015. The new HTTP client gets failing unit tests first (via `httpx.MockTransport`) before the concrete implementation. |
| IV. Configuration Over Hard-Coding | **Pass.** `portfolio_analysis_service_url` already exists in `config/settings.py` (added ahead of this feature). A request-timeout setting is added alongside it rather than inlined. No new hardcoded URLs, thresholds, or labels. |
| V. Standard Libraries and SOLID | **Pass.** Reuses `httpx` and `plotly` — both already proven/standard in this monorepo — instead of hand-rolling an HTTP client or charting. `ruff` + `mypy --strict` continue to run clean. The client module has one responsibility (HTTP I/O for one upstream service); chart-shaping logic is a separate, independently testable pure function from the callback that triggers it. |
| User Experience Standards | **Pass (planned).** `dcc.Loading` gives feedback within 100ms of any triggering interaction. Chart→legend is one view (no extra navigation hop). Empty-state and error-state messaging (FR-013/FR-014) satisfy "no blank or broken chart" requirement. Desktop/tablet usability inherited unchanged from 015's shell. |

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-link-real-portfolio/
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
├── config/
│   └── settings.py                    # + request_timeout_seconds for the new client (existing portfolio_analysis_service_url reused)
├── src/
│   ├── services/                      # NEW — data-access layer (constitution Principle II)
│   │   ├── __init__.py
│   │   └── portfolio_analysis_client.py   # Protocol + HttpPortfolioAnalysisClient: list_accounts(), list_attributes(), get_timeseries()
│   ├── models/                        # NEW — typed shapes for client responses (no calculation)
│   │   ├── __init__.py
│   │   └── portfolio_analysis.py      # AccountSummary, AttributeDefinition, TimeSeriesEntry/Response (mirrors service's Pydantic models)
│   ├── layout/
│   │   └── shell.py                   # MODIFIED — parameters bar becomes route-aware (real Account/date controls on Overview, unchanged static placeholder elsewhere)
│   ├── exceptions.py                   # NEW — PortfolioAnalysisServiceError
│   └── pages/
│       ├── _overview_chart.py         # NEW — side-effect-free pure helpers (business-day/date-derivation/figure-building); split from overview.py because importing overview.py triggers dash.register_page() at module load, which is unsafe for a plain unit-test import (implementation-time refinement, see tasks.md T005)
│       └── overview.py                # MODIFIED — real layout: chart, legend, metric-toggle panel, callbacks (FR-001–FR-015)
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   ├── overview_empty_and_error_states.feature   # Foundational — FR-013/FR-014 edge cases (analyze finding C1)
│   │   │   ├── shell_parameters_bar_unchanged.feature     # Foundational — non-Overview routes keep 015 placeholder (analyze finding C2)
│   │   │   ├── overview_default_chart.feature       # User Story 1 (P1)
│   │   │   ├── overview_switch_account.feature       # User Story 2 (P2) — also covers SC-006 no-full-reload (analyze finding G1)
│   │   │   ├── overview_date_range.feature            # User Story 3 (P3)
│   │   │   └── overview_metric_toggles.feature        # User Story 4 (P4)
│   │   └── steps/
│   │       └── test_overview_steps.py
│   └── unit/
│       ├── test_portfolio_analysis_client.py          # httpx.MockTransport-based; success + 404/422/timeout paths
│       └── test_overview_chart_shaping.py             # pure functions: entries→plotly traces, business-day default, min-of-dates
├── pyproject.toml                       # + httpx, plotly (explicit), structlog
└── CLAUDE.md
```

**Structure Decision**: Extends the existing single Python/Dash project
(no new project/service boundary). Two new top-level packages under `src/`
follow the constitution's layering (Principle II): `src/services/` is the
data-access layer (HTTP only, no domain logic — same shape as
`portfolio-analysis-service/app/clients/`), and `src/models/` holds typed,
calculation-free response shapes shared between the client and the page
callbacks. `src/pages/overview.py` and `src/layout/shell.py` are modified in
place rather than restructured, keeping this feature's footprint additive and
consistent with 015's established module boundaries.

## Complexity Tracking

No violations — table intentionally empty.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (`data-model.md`, `contracts/ui-contract.md`,
`contracts/portfolio-analysis-api.md`, `quickstart.md`):

- **Principle I**: Confirmed by design — `data-model.md`'s "Chart Series"
  and "State flow summary" sections show every plotted value traced back to
  an `entries[].{attribute}` field with no arithmetic on it. The two
  client-side date computations remain selection logic, not financial
  facts.
- **Principle II**: Confirmed — `src/services/portfolio_analysis_client.py`
  (data access) and the Overview callbacks (transport/orchestration) stay
  separate; chart-shaping (`entries` → Plotly traces) is planned as its own
  pure, independently unit-testable function (`tests/unit/test_overview_chart_shaping.py`),
  not inlined in a callback.
- **Principle III**: Four `.feature` files map 1:1 to the four user stories,
  matching the BDD-first structure already proven in 015.
- **Principle IV**: No new hardcoded config surfaced during design beyond
  the already-planned `request_timeout_seconds` setting.
- **Principle V**: No new dependency introduced beyond `httpx`, `plotly`
  (now direct), and `structlog` — all three already justified in
  `research.md` as monorepo-standard, not novel choices.
- **User Experience Standards**: `overview-chart-loading` (`dcc.Loading`)
  satisfies the 100ms feedback requirement; `overview-empty-state` /
  `overview-error-state` satisfy "no blank/broken chart" for every edge case
  the spec identifies.

All rows still hold. **Gate: Pass.** No Complexity Tracking entries needed.
