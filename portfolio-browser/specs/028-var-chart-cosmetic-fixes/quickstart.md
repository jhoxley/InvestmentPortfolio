# Quickstart: Value at Risk Chart Cosmetic Fixes

Manual verification steps once implementation lands. Assumes a running
`portfolio-analysis-service` (with an account that has a completed VaR calculation and at
least two confidence levels available) and this app pointed at it, per feature 024's own
quickstart.

1. Open the Risk page for such an account and scroll to the Value at Risk section. Confirm
   the chart's legend appears below the entire chart (both the main and linked subplot
   rows), not beside or inside the plot area.

2. Confirm the backtest summary panel is fully visible within the page's normal width —
   no part of it cut off or requiring horizontal scrolling.

3. With two or three confidence levels selected, confirm the backtest summary is a single
   table with one column per selected level (e.g. "95%", "97.5%", "99%") and one row per
   statistic (Exceptions, Kupiec p-value, Conditional coverage p-value, Zone, Mean VaR,
   VaR stability) — not a separate table per level.

4. Deselect one confidence level. Confirm its column disappears from the table immediately
   and the remaining columns' values are unchanged. Reselect it and confirm the column
   reappears with the same values as before.

5. With the chart's units set to money (£), confirm the realised profit/loss bars render
   as before. Switch units to percentage. Confirm the realised profit/loss bars disappear
   from the chart, and the VaR (and, if enabled, Expected Shortfall) forecast line is
   clearly readable at a sensible percentage scale — not compressed near zero.

6. Switch units back to money. Confirm the realised profit/loss bars reappear exactly as
   they did in step 5, with no stale or mismatched data.

7. Confirm a short caption appears directly above the main chart (profit/loss vs. Value at
   Risk forecast) and a second short caption appears directly above the linked chart
   (total market value / proxied-rescaled share).

8. Zoom or pan the main chart (e.g. via a click-drag selection). Confirm the linked chart
   beneath it zooms/pans to the same date range — the two subplot rows must remain linked,
   not become two independent charts.

9. Resize the browser window (or use its device toolbar) to a common tablet width (e.g.
   ~768-1024px). Confirm the repositioned legend and the combined backtest table (steps 1
   and 3) both remain fully readable — no overlapping text, no column cut off, no
   horizontal scroll required — consistent with this project's existing tablet-width
   usability standard (`/speckit-analyze` finding F2).
