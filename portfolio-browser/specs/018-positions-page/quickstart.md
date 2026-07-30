# Quickstart: Positions Page

No new dependency, config, or backing-service requirement beyond
`016-link-real-portfolio`'s own quickstart — this feature adds zero new
third-party packages (research.md #3, #4, #5, #6 all reuse stdlib or
already-installed `dash`/`plotly`/`dash-bootstrap-components`).

## Setup

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps vs. 017; safe to re-run
```

## Prerequisite

A running `portfolio-analysis-service` instance with the
`005-position-timeseries-api` endpoints available (`GET
/v1/accounts/{account_name}/position`, `GET
/v1/accounts/{account_name}/positions`, `GET /v1/positions/attributes`),
with at least one account that has an ingested position ladder — see
`portfolio-analysis-service/specs/005-position-timeseries-api/quickstart.md`
for how to ingest one.

## Run

```bash
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050` and click "Positions" in the left-hand nav.

Manually verify each user story:

- **US1 (default view)**: On first navigating to Positions, the Account
  selector should show the first account selected, the date range should
  show "YtD", the position filter should show every position for that
  account selected, and a chart should render with no further action.
- **US2 (explore)**: Switch accounts — the position filter should reset to
  every position for the new account and the date range should reset to
  "YtD" for that account (not its full history). Click each shortcut
  ("YtD"/"1Y"/"3Y"/"5Y"/"All") and confirm the date fields and chart update,
  matching the same behavior already verified for Overview in
  `specs/017-chart-date-range-shortcuts/quickstart.md`.
- **US3 (filter)**: Toggle a second attribute on, then narrow the position
  filter to 2-3 positions — the chart and table should update to reflect
  exactly that selection. Deselect every attribute, then every position,
  and confirm the empty-state prompts appear instead of a blank chart.
- **US4 (comparison table)**: With the chart showing data, confirm a table
  appears below it with one row per plotted position and, for each
  selected attribute, a value column and an adjacent "(prev)" column.
  Confirm the value column is shaded light green for positions that rose,
  light red for positions that fell, and unshaded for positions unchanged
  between "From" and "To".
- **US5 (stacked area)**: With exactly one attribute selected, turn
  "Stacked area graph" on and confirm the chart becomes a stacked area
  chart. Select a second attribute and confirm the toggle automatically
  turns off (not blocked) and the chart reverts to a line chart with both
  attributes. Confirm the toggle is disabled (not clickable) while more
  than one attribute remains selected.
- **FR-023 (control disabling)**: Click any control that triggers a
  refresh and, while the chart/table are loading, confirm the
  account/date/shortcut/attribute/position/stacked-area controls are all
  briefly disabled, then re-enabled once the refresh completes.
