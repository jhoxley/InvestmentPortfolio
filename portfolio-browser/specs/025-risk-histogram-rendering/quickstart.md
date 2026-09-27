# Quickstart: Readable Return Histogram Rendering

Manual verification steps once implementation lands. Assumes a running
`portfolio-analysis-service` (with at least one ingested account) and this app pointed at it, per
feature 024's own quickstart.

1. Start the analysis service and the Dash app; open the Risk page for an account with several
   years of return history.

2. Confirm the bar chart shows noticeably fewer, wider bars than before — grouped in 0.1%-wide
   ranges rather than one bar per basis point.

3. Confirm the X-axis is labeled/scaled in percent (e.g. "0.3%"), not "Return (bps)".

4. Confirm two vertical reference lines are drawn on the chart — one at the mean return, one at
   the median — and that they are visually distinguishable (different dash style/color, each with
   its own label).

5. Confirm bars near the center of the distribution are shaded mid-green, bars further out are
   mid-yellow, further still mid-orange, and the most extreme bars (if any, at the tails) are red
   — consistent with the 1/2/3-sigma bands shown in the statistics table.

6. Select an account/date-range combination with only 1 observation (std dev undefined). Confirm
   the chart still renders, with every bar shown in a single neutral gray rather than erroring or
   partially coloring.

7. Confirm the statistics table, account/date controls, and shortcut buttons are all unaffected —
   only the chart's own rendering changed.
