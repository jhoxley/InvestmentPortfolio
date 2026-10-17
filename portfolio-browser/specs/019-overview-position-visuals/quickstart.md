# Quickstart: Overview Position Visualizations

No new dependency, config, or backing-service requirement — this feature
reuses `018-positions-page`'s existing `get_position_timeseries` client
method and endpoint integration verbatim (research.md #1).

## Setup

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps vs. 018; safe to re-run
```

## Prerequisite

A running `portfolio-analysis-service` instance with the
`005-position-timeseries-api` endpoints available, and at least one
account with an ingested position ladder that has `market_value`, `pnl`,
and `book_cost` recorded for its most recent date.

## Run

```bash
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050` (Overview loads by default). Once the
existing performance chart has finished loading, a new row should appear
below it with a pie chart on the left and a "Biggest winners and losers"
table on the right.

Manually verify each user story:

- **US1 (pie chart)**: Confirm one slice per position, sized by market
  value share as of the "To" date shown above. Any slice ≥5% of the total
  should show its position name directly on the slice; hover any slice
  (including small ones) to confirm it shows the exact name, value, and
  percentage. Change the account, then change the "To" date, and confirm
  the pie chart refreshes both times. Select an account/date with no
  position data and confirm a "no data" message appears instead.
- **US2 (winners/losers table)**: Confirm up to 10 rows, captioned
  "Biggest winners and losers", each showing a position name, its
  profit/loss, and its book cost. Confirm row 1 is the brightest green,
  fading through row 5; row 6 is the palest blue, strengthening through
  row 10. Switch to an account with fewer than 10 positions and confirm
  every qualifying position appears exactly once with no blank/duplicate
  rows. Confirm the table refreshes on account/"To" date change.
- **FR-010 (independence)**: With the pie chart and table showing data,
  edit the "From" date, or toggle a performance-chart metric on/off (even
  down to zero toggled), and confirm neither new visualization changes or
  disappears.
- **FR-001a (responsive stacking)**: Resize the browser to a tablet width
  (~800px) and confirm the pie chart and table stack vertically (pie chart
  above the table) instead of squeezing side-by-side.
