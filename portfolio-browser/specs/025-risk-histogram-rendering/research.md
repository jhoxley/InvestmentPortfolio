# Phase 0 Research: Readable Return Histogram Rendering

No `NEEDS CLARIFICATION` markers remained in the Technical Context, so this phase documents the
concrete decisions made while resolving open design questions.

## #1 — Percent-axis scale: numeric-with-suffix vs. Plotly `tickformat`

**Decision**: Convert bucket centers to percent numerically (`bp / 100`) and render the axis with
`ticksuffix="%"` and a plain numeric title, rather than passing raw bp/10000 fractions through
Plotly's `tickformat=".1%"` (the convention `_performance_chart.py` already uses for return-rate
lines).

**Rationale**: `_performance_chart.py`'s measures are natively stored as decimal fractions (e.g.
`0.071` for "7.1%"), so `tickformat=".1%"` multiplying by 100 for display is correct there. This
feature's data starts in basis points (1bp = 0.01%), so the "natural" fraction for Plotly's
percent format would be `bp / 10000`, not `bp / 100` — an easy transcription error if the two
conventions are mixed in the same codebase without a clear boundary. Converting to a plain percent
number once (`bp / 100`) and suffixing "%" in the axis avoids a second implicit ×100 and keeps the
value shown in hover text and the value used for bucket math identical.

**Alternatives considered**:
- *Use `tickformat=".2%"` with `x = bp / 10000`*: rejected — technically equivalent, but
  introduces a second, different bp→display-unit divisor (10000) alongside this feature's own
  bucketing math (which naturally works in bp), increasing the chance of a units bug.
- *Keep raw bp on the axis, just relabel the title "bps as %"*: rejected — doesn't satisfy FR-002,
  which requires the axis to actually be scaled in percent, not merely relabeled.

## #2 — Bucket boundary alignment

**Decision**: `bucket_key(bp) = (bp // 10) * 10`, using Python's floor-toward-negative-infinity
integer division, giving contiguous 10-wide buckets aligned to multiples of 10 (…, -20..-11,
-10..-1, 0..9, 10..19, …).

**Rationale**: This is the simplest, most standard binning convention (fixed-width bins aligned to
the bin width itself), requires no special-casing for negative values, and every raw bp value maps
to exactly one bucket with no gaps or overlaps — satisfying FR-001's "sum counts of every raw
value into that range" without ambiguity.

**Alternatives considered**:
- *Center bins on zero (e.g. -5..4, 5..14, …)*: rejected — adds no readability benefit over
  standard aligned bins and complicates the negative-value case for no stated requirement.
- *Round to nearest 10 instead of flooring*: rejected — rounding can push a value into a
  neighboring bucket asymmetrically at the boundary (e.g. 5 rounds up, -5 rounds... which way?),
  whereas flooring is unambiguous and matches how the API's own rounding-to-nearest-integer-bp
  step (portfolio-analysis-service spec 011) is already described.

## #3 — Band-membership test at the bucket level

**Decision**: A bucket's color is decided by testing its **center** value against each
`StdDevBand`'s `lower`/`upper` (smallest sigma match wins), not by testing every raw observation
within the bucket individually.

**Rationale**: The response's `histogram` field is already the API's own final granularity (one
count per rounded integer bp); this feature only re-groups those already-rounded values for
display. Directly matches spec Edge Cases' "a bucket is colored by whichever band contains its
central return value" and FR-007's "exactly one color per bar."

**Alternatives considered**:
- *Split a bucket into two colors if raw observations within it fall in different bands*:
  rejected — spec Edge Cases explicitly rules this out ("no bar is split or rendered with a
  blended/ambiguous color").

## #4 — Reference lines: `add_vline` vs. a second trace

**Decision**: Use `go.Figure.add_vline(x=..., line_dash=..., annotation_text=...)` twice (mean,
median), each with distinct `line_dash`/color and its own annotation label.

**Rationale**: `add_vline` is Plotly's purpose-built primitive for exactly this (a full-height
reference line with an optional label), avoids constructing a second `go.Scatter` trace with
manually-computed y-range endpoints, and keeps both lines visually correct regardless of the bar
chart's y-axis autoscaling.

**Alternatives considered**:
- *A second `go.Scatter` trace per line*: rejected — requires manually tracking the current
  y-axis max to draw a "full height" line and re-deriving it whenever the data changes; `add_vline`
  handles this natively.

## #5 — Fallback color when standard deviation is undefined

**Decision**: A single named neutral gray constant, used for every bar whenever
`statistics.std_dev_bands` is empty (the API's own signal for "count < 2").

**Rationale**: Matches FR-006 directly; reusing the existing `DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR`
constant's role/precedent from `_performance_chart.py` (a single documented fallback color, not a
per-call default parameter) keeps the convention consistent across the two chart modules.

**Alternatives considered**:
- *Reuse the original solid-blue bar color from feature 024's first version*: rejected — reads as
  "normal"/"typical" (the same visual role mid-green now has), which would be misleading precisely
  in the case where "typical" cannot even be computed.
