# Quickstart: Account Performance Chart on Overview

## Setup

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # picks up new httpx/plotly/structlog deps
```

## Prerequisite: `portfolio-analysis-service` must be running with data

This feature has nothing to show without a live, populated
`portfolio-analysis-service`. From the repo root:

```bash
cd ../portfolio-analysis-service
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Ensure at least one account has an ingested capital ledger and/or position
ladder (see that service's own quickstart docs for ingestion steps) — an
empty `/v1/accounts` response means the Overview page has no account to
auto-select and should show its error/empty state, not a chart.

## Configure

`config/settings.py`'s `portfolio_analysis_service_url` already defaults to
`http://127.0.0.1:8000`, matching `run_end_to_end.ps1`'s port assignment.
Override via `.env` (`PORTFOLIO_ANALYSIS_SERVICE_URL=...`) if running the
backing service elsewhere. A new `request_timeout_seconds` setting (default
TBD in `tasks.md`) bounds how long the browser waits before showing the
error state (FR-014).

## Run

```bash
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050` and navigate to (or land on, since it's the
default section) **Overview**. You should see, with no clicks required:

- The Account selector already showing the alphabetically-first account
- "From"/"To" date pickers already populated (earliest available date for
  that account; last completed business day)
- A line chart already rendered, plotting `market_value` only
- A legend below the chart naming the plotted metric with a distinct color
- Hovering any point on the line shows its date/metric/value

Then manually verify each subsequent user story:

- **US2**: Switch the Account dropdown — chart, date defaults, and (if that
  account's own history differs) chart data all update.
- **US3**: Narrow the "from"/"to" range — chart re-renders to the narrower
  window; try setting "to" after today or "from" after "to" and confirm the
  picker itself prevents the invalid state.
- **US4**: Hover a metric toggle to see its tooltip description; turn on a
  second metric and confirm a second line + legend entry appears in a
  distinct color; turn all metrics off and confirm the empty-state message
  (not a blank chart) appears.

Navigate to Positions/Performance/Income and confirm the metric-toggle panel
is not present on any of them (FR-007), and that those pages' existing
placeholder parameters bar looks exactly as it did before this feature
(015 behavior unchanged).

## Test

```bash
.venv/Scripts/python -m pytest tests/unit           # HTTP client (httpx.MockTransport) + chart-shaping pure functions
.venv/Scripts/python -m pytest tests/bdd             # Gherkin/BDD Overview scenarios (dash_duo, real browser)
```

`tests/bdd` requires Chrome or Firefox (see 015's quickstart note on
`dash.testing` browser support — Edge is not supported). BDD scenarios for
this feature stub `portfolio-analysis-service` responses at the HTTP client
boundary (`httpx.MockTransport`) rather than requiring a real running
instance, so `pytest tests/bdd` does not need the service from the
"Prerequisite" section above — that section is for the *manual* walkthrough
only.

## Static analysis

```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy .
```

## Validating this feature against the spec

- User Story 1 (default chart on load) → `tests/bdd/features/overview_default_chart.feature`
- User Story 2 (switch account) → `tests/bdd/features/overview_switch_account.feature`
- User Story 3 (date range) → `tests/bdd/features/overview_date_range.feature`
- User Story 4 (metric toggles) → `tests/bdd/features/overview_metric_toggles.feature`

All four MUST pass, `ruff`/`mypy` MUST run clean, and both the automated and
manual walkthroughs above MUST match before this feature is considered
complete.
