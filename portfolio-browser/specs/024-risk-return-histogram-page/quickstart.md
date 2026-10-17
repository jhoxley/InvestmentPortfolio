# Quickstart: Risk Page (Return Histogram)

Manual verification steps once implementation lands. Assumes a running
`portfolio-analysis-service` (with at least one ingested account) and this app pointed at it via
`Settings().portfolio_analysis_service_url`.

1. Start the analysis service and confirm the endpoint responds directly:
   ```
   curl "http://127.0.0.1:8000/v1/accounts/HL-ISA/risk/return-histogram?start=2020-01-01&end=2026-09-01"
   ```
   Confirm the response has `histogram` (array of `[bp, count]` pairs) and `statistics`
   (`count`, `mean`, `median`, `mode`, `minimum`, `maximum`, `std_dev`, `std_dev_bands`,
   `skewness`, `kurtosis`).

2. Start the Dash app (`.venv/Scripts/python app.py` or the project's usual entrypoint) and open
   it in a browser.

3. Click the "Risk" entry in the sidebar. Confirm:
   - An account is pre-selected (alphabetically first).
   - The date range defaults to that account's full recorded history.
   - A bar chart renders with basis-point buckets on the X-axis and day-counts as bar heights.
   - A table headed "statistic"/"value" renders to the right of the chart, with rows count, mean,
     median, mode, minimum, maximum, std_dev, skewness, kurtosis (in that order) — no
     `std_dev_bands` row anywhere.
   - The chart and table sit in one row, chart wider than the table (~60/40).

4. Click each of "10Y", "1Y", "3Y", "5Y", "All" in turn. Confirm the from-date updates each time
   and the chart/table refresh to match.

5. Manually edit the From/To date pickers to a narrow custom range. Confirm the chart/table
   refresh to exactly that range and no shortcut button appears active afterward.

6. Switch to a different account. Confirm the date range resets to the new account's own default
   and the chart/table refresh for it.

7. Pick a To date on/before the From date. Confirm an inline validation message appears and the
   previously valid chart/table remain shown.

8. Stop the analysis service and refresh/interact with the page. Confirm the shared error-state
   message appears in place of both the chart and the table, not a crash or blank page.
