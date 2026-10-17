# Quickstart: Value at Risk View (Risk Page)

## Prerequisites

- `portfolio-analysis-service` running, with at least one account that has a completed VaR
  calculation run (feature 012: `POST /v1/accounts/{account}/risk/var/runs`) — see that service's
  own quickstart for how to trigger one.
- `portfolio-browser`'s `.env`/`config/settings.py` pointing at that running service.
- This app's dev server running: `python app.py` (or the project's usual dev entrypoint).

## 1. Open the Risk page and find the new tab

Navigate to `/risk`. Confirm two tabs: "Return Histogram" (unchanged) and "Value at Risk" (new).
Confirm the account selector, date range and shortcut buttons above the tabs are identical
whichever tab is active — switching tabs must not reset or duplicate them (FR-001).

## 2. See the chart and backtest panel for an account with completed VaR

Select the Value at Risk tab for the account with a completed run. Expect, within the account's
2-year default look-back:

- A chart with one bar per business day (realised PnL) and an overlaid line for each selected
  confidence level's negative VaR.
- Any day whose realised loss exceeded its VaR visually distinguished (red, per plan.md).
- Beneath it, a smaller linked chart of total market value and proxied/rescaled share.
- A side panel reporting exceedances vs. expected, two p-values, a traffic-light zone, mean VaR
  and VaR stability for every selected confidence level.

## 3. Confirm instant controls make no network call

With browser dev tools' Network tab open, toggle a confidence level off, then switch units from
money to percentage, then switch PnL basis from hypothetical to ladder. Expect the chart and
panel to update after each toggle, and expect **no** new `GET` request to
`portfolio-analysis-service` for any of the three toggles (FR-010).

## 4. Confirm account/date/look-back changes do refetch

Change the look-back from "2Y" to "1Y". Expect new `GET .../risk/var` and `GET .../risk/var/backtest`
requests (4 of them) in the Network tab, and the chart/panel to refresh (FR-011).

## 5. Confirm the empty state for an account with no calculation

Open the tab for an account that has never had a VaR run. Expect no chart, no panel — just an
explanatory message describing why and how a calculation is triggered (FR-013), not a blank or
broken chart.

## 6. Confirm the stale-data banner

Open the tab for an account whose VaR store is behind its ladder (e.g. right after a trade was
ingested but before the next VaR run). Expect a banner stating the number of missing dates
(FR-014), with the chart/panel still rendering whatever has been calculated.

## 7. Confirm the degraded-quality toggle

For an account/range with at least one `degraded`-quality date, turn on "hide degraded-quality
dates." Expect that date's bar/overlay point to disappear and the backtest panel's figures to
change to the `min_quality=ok` result (no new network call — it was already fetched, research.md
#1). Turn it off; expect both to revert.

## 8. Confirm periodicity has no presence on this tab

Confirm no day/week/month/quarter/annual control is visible while the Value at Risk tab is active
(FR-015).
