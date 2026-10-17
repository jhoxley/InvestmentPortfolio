# Quickstart: Risk Page Cosmetic Cleanup

Manual verification steps once implementation lands. Assumes a running
`portfolio-analysis-service` (with at least one ingested account that has a completed VaR
calculation) and this app pointed at it, per feature 024's own quickstart.

1. Start the analysis service and the Dash app; open the Risk page for an account with several
   years of return history and a completed VaR calculation.

2. Confirm there is no tab control. The return histogram chart and statistics table appear first;
   scrolling down reveals the Value at Risk controls, chart, and backtest summary below it, all on
   the same page.

3. Note the histogram chart's x-axis position of the mean reference line (e.g. "8.08%"). Confirm
   the statistics table's "mean" row shows the same value with the same "%" unit (e.g. "8.08%"),
   not a bare number like "808". Confirm median/minimum/maximum/std_dev rows are likewise shown
   in percent; confirm count/skewness/kurtosis rows are shown without a "%" suffix.

4. Confirm the chart shows exactly one vertical reference line (the mean), with no separate median
   line or label.

5. Pick any clearly-populated bar away from the mean (e.g. the bar nearest "-1%"). Confirm its
   position matches that same absolute return value — not a position offset from the mean (e.g. if
   the mean is 0.08% and that bar is nominally "-1%", it must sit at x = -1%, not at x = -1.08%
   relative to the mean).

6. Confirm the page shows exactly one set of range controls: the shared shortcut buttons
   (1Y/2Y/3Y/5Y/10Y/All) above both sections, with no separate "Look-back" dropdown inside the
   Value at Risk area.

7. Click "1Y". Confirm both the histogram section and the Value at Risk section refresh for a
   1-year window. Click "2Y". Confirm the Value at Risk section refreshes using the server's 2-year
   look-back. Click "3Y" (or "10Y"/"All"). Confirm the histogram section still renders normally,
   while the Value at Risk section shows its "No Value at Risk data is available for the selected
   range" message instead of stale or mismatched figures.

8. Compare the histogram's statistics table with the Value at Risk backtest summary below it.
   Confirm both present their labelled figures using the same visual style (matching typography,
   borders/spacing, and header styling) rather than looking like two unrelated components.

9. Confirm the account selector and manually-edited date range still work as before, and that
   editing a date picker by hand (rather than clicking a shortcut) clears the active shortcut
   highlighting without breaking either section.
