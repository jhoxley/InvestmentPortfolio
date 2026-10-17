# Quickstart: Performance Page

No new dependency, config, or backing-service requirement beyond
`016-link-real-portfolio`'s own quickstart — this feature adds zero new
third-party packages (research.md #1, #2, #6 all reuse existing models,
the existing client pattern, and stdlib/Plotly's own percentage formatting).

## Setup

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps; safe to re-run
```

## Prerequisite

A running `portfolio-analysis-service` instance with the
`007-performance-endpoints` endpoints available (`GET
/v1/accounts/{account_name}/performance`, `GET /v1/performance/attributes`),
with at least one account that has an ingested position ladder — see
`portfolio-analysis-service/specs/007-performance-endpoints/quickstart.md`
for how to ingest one.

## Run

```bash
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050` and click "Performance" in the left-hand nav.

Manually verify each user story:

- **US1 (default view)**: On first navigating to Performance, the Account
  selector should show the first account selected, the date range should
  cover that account's full recorded history through the most recently
  completed business day, and a chart should render with one line (the
  first measure returned by `/v1/performance/attributes`, typically "ITD")
  with no further action.
- **US2 (explore)**: Switch accounts — the date range should reset to the
  new account's own full recorded history. Click each shortcut ("ITD"/
  "1Y"/"3Y"/"5Y"/"All") and confirm the date fields and chart update;
  clicking "ITD" and clicking "All" should produce the identical "From"
  date (both resolve to the account's earliest recorded date — this is
  expected, not a bug, per spec Clarifications).
- **US3 (measure selection)**: Toggle a second measure (e.g. "1Y") on and
  confirm a second line appears on the chart without affecting the first.
  Deselect every measure and confirm an empty-state prompt appears instead
  of a blank chart.
- **No stacked-area / no table**: Confirm there is no "Stacked area graph"
  toggle and no data table anywhere on this page — the chart and its
  controls are the entire page (spec Clarifications).
- **Formatting**: Confirm chart values are shown as percentages (e.g.
  "18.3%"), not currency, on both the y-axis and hover tooltips.
- **Missing history**: With "5Y" toggled on for an account with less than
  5 years of recorded history, confirm the "5Y" line simply starts partway
  through the chart (no error, no broken chart) once enough history exists.
