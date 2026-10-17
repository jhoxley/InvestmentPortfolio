# Feature Specification: Readable Return Histogram Rendering

**Feature Branch**: `025-risk-histogram-rendering`
**Created**: 2026-09-27
**Status**: Draft
**Input**: User description: "make some changes to the last features histogram rendering to make it easier to read and render better. Firstly, an X-axis of basis-point granularity is to fine grained. Add a pass to convert the data from the API into 0.1% (10bp) buckets, summing the count of observations per bucket. Change the x-axis title to be % return, instead of basis points. Next, annotate two vertical lines on the graph matching the mean and median daily return. Finally, use the std_dev_bands from the API response to colour bars in the chart. Where the bar is in the sigma=1 lower/upper band shade the bar a mid-green. For bars not in the sigma=1 range but in the sigma=2 lower/upper range shade them a mid-yellow colour, for sigma=3 shade a mid-orange and anything outside of the sigma=3 lower/upper should be a red."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the Distribution Shape at a Glance (Priority: P1)

Someone looking at the Risk page's histogram today sees a bar for nearly every individual
basis-point value, making the chart look noisy and spread thin rather than showing a clear
distribution shape. They want the same underlying data grouped into coarser, easier-to-scan
ranges, labeled in the units they think in (percent, not basis points).

**Why this priority**: This is the core readability complaint driving the whole feature — every
other change (reference lines, color-coding) builds on top of a chart that is first legible on
its own.

**Independent Test**: Open the Risk page for an account with return history; verify the histogram
shows noticeably fewer, wider bars than before (grouped in 0.1 percentage-point ranges) and the
X-axis is labeled in percent rather than basis points.

**Acceptance Scenarios**:

1. **Given** a return histogram response with counts spread across many individual basis-point
   values, **When** the chart renders, **Then** observations are grouped into 0.1%-wide ranges,
   with each bar's height equal to the sum of observation counts falling in that range.
2. **Given** the chart has rendered, **When** looking at the X-axis, **Then** its title reads as a
   percent-based return label (not basis points) and its tick values are expressed in percent.
3. **Given** two adjacent raw basis-point buckets that fall within the same 0.1% range, **When**
   the chart renders, **Then** their counts appear combined in a single bar, not as two separate
   bars.

---

### User Story 2 - See Mean and Median at a Glance (Priority: P2)

Someone studying the distribution wants to immediately see where the average and the midpoint of
daily returns sit relative to the overall spread, without cross-referencing the statistics table.

**Why this priority**: This turns the chart from a shape-only view into one that answers "is this
account's typical/average return positive, negative, and how do they compare" without extra
lookups — valuable on its own, independent of the color-coding in User Story 3.

**Independent Test**: Open the Risk page for an account with a mean return distinct from its
median; verify two vertical lines are drawn on the chart, one at the mean return value and one at
the median return value, and they are distinguishable from each other.

**Acceptance Scenarios**:

1. **Given** a return histogram response with defined mean and median statistics, **When** the
   chart renders, **Then** a vertical line is drawn at the mean return's position on the X-axis and
   a separate vertical line is drawn at the median return's position.
2. **Given** the mean and median happen to be equal, **When** the chart renders, **Then** both
   reference lines are still shown (even if visually overlapping) rather than one being silently
   dropped.
3. **Given** the two lines are shown, **When** looking at the chart, **Then** it is clear which
   line represents the mean and which represents the median (e.g. via labels, a legend, or
   distinct styling).

---

### User Story 3 - Assess How Typical or Extreme Returns Are (Priority: P3)

Someone wants to see, at a glance, which parts of the distribution are "normal" day-to-day
variation versus unusually large moves, without manually comparing each bar to the statistics
table's standard-deviation figures.

**Why this priority**: This is the most advanced refinement — it adds a visual risk cue on top of
a chart that is already readable (User Story 1) and already shows central-tendency lines (User
Story 2), and is the least essential to basic comprehension of the three.

**Independent Test**: Open the Risk page for an account with a computed standard deviation;
verify bars within one standard deviation of the mean are shaded a distinct "typical" color, bars
progressively further out are shaded increasingly attention-grabbing colors, and the color
boundaries line up with the standard-deviation bands shown in the statistics data.

**Acceptance Scenarios**:

1. **Given** a return histogram response with standard-deviation bands, **When** the chart
   renders, **Then** every bar whose range falls within the 1-standard-deviation band is shaded a
   mid-green.
2. **Given** the same response, **When** the chart renders, **Then** bars outside the
   1-standard-deviation band but within the 2-standard-deviation band are shaded a mid-yellow.
3. **Given** the same response, **When** the chart renders, **Then** bars outside the
   2-standard-deviation band but within the 3-standard-deviation band are shaded a mid-orange.
4. **Given** the same response, **When** the chart renders, **Then** any bar entirely outside the
   3-standard-deviation band is shaded red.
5. **Given** a response where standard deviation cannot be computed (too few observations),
   **When** the chart renders, **Then** bars are shown in a single neutral color rather than
   erroring or showing partially-colored bars.

---

### Edge Cases

- **Very few observations (standard deviation undefined)**: bars render in a single neutral
  color; the chart does not error or fall back to a broken/partial coloring scheme (User Story 3,
  Scenario 5).
- **A single 0.1% bucket spans a standard-deviation band boundary**: the bucket is colored by
  whichever band contains its central return value, so every bar has exactly one color (no
  split-colored bars).
- **Mean or median falls outside the range of any rendered bar** (e.g. a single extreme
  observation skews the mean far from the bulk of the data): the reference line is still drawn at
  its true position, even if that means it appears at the very edge of the chart or requires the
  chart's range to extend to accommodate it.
- **All observations fall into a single 0.1% bucket**: a single bar is shown; mean/median lines
  and any applicable band coloring still apply normally.
- **This feature changes only how the histogram chart renders** — the statistics table
  introduced by the prior Risk-page feature, the account/date controls, and the
  `std_dev_bands` data's own values are unaffected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The histogram chart MUST group the API's raw per-basis-point observation counts
  into 0.1 percentage-point (10 basis point) wide ranges before rendering, summing the observation
  counts of every raw value that falls within each range into that range's single bar.
- **FR-002**: The histogram chart's X-axis MUST be labeled and scaled in percent (e.g. "0.3%"),
  not basis points, reflecting the same underlying return values at the coarser grouping from
  FR-001.
- **FR-003**: The histogram chart MUST draw two vertical reference lines: one at the response's
  mean daily return and one at its median daily return, each visually distinguishable from the
  other (e.g. by label, color, or line style).
- **FR-004**: When the mean and median values are equal, both reference lines MUST still be drawn
  rather than one being omitted.
- **FR-005**: Each bar's color MUST reflect which standard-deviation band (from the response's
  `std_dev_bands`) contains that bar's return range: mid-green for the 1-sigma band, mid-yellow
  for the 2-sigma band (excluding the 1-sigma band), mid-orange for the 3-sigma band (excluding
  the 1- and 2-sigma bands), and red for anything outside the 3-sigma band.
- **FR-006**: When standard deviation cannot be computed for the current account/range (too few
  observations), every bar MUST render in a single neutral color instead of applying FR-005's
  band-based coloring.
- **FR-007**: A bar that spans a standard-deviation band boundary MUST still be assigned exactly
  one color (no bar is split or rendered with a blended/ambiguous color).
- **FR-008**: The grouping, labeling, reference lines, and coloring introduced by this feature
  MUST NOT alter the statistics table, the account/date controls, or any other part of the Risk
  page introduced previously.

### Key Entities *(include if feature involves data)*

- **Histogram Bucket (grouped)**: A 0.1%-wide return range and the total observation count of
  every raw basis-point value from the API response that falls within it. Replaces the
  previous one-bar-per-raw-value rendering.
- **Reference Line**: A labeled marker at a specific return value (the response's mean, or its
  median) drawn across the chart's vertical extent.
- **Standard-Deviation Band Color**: A mapping from a `std_dev_bands` entry (sigma = 1, 2, or 3,
  each with a lower/upper bound) to a bar color, plus a default "outside every band" color and a
  neutral fallback color used when no bands are available.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any account's history, the number of distinct bars shown is at most the number
  of distinct 0.1%-wide ranges spanned by the data — never one bar per individual basis-point
  value as before, and typically at least 5x fewer bars for a spread-out distribution.
- **SC-002**: A user can identify the mean and median return values from the chart alone, without
  consulting the statistics table, in under 5 seconds.
- **SC-003**: A user can visually distinguish "typical" (mid-green) daily returns from
  increasingly unusual ones (yellow, orange, red) without needing to read the underlying
  standard-deviation numbers.
- **SC-004**: An account with too little history to compute a standard deviation still produces a
  fully readable, non-erroring chart.

## Assumptions

- "0.1% (10bp) buckets" means grouping the API's integer-basis-point observations into
  contiguous, equal-width ranges 10 basis points wide (e.g. 0–9bp, 10–19bp, etc., or an
  equivalent symmetric convention around zero); the exact boundary alignment is an implementation
  detail left to the planning phase, since the feature request specifies the width but not the
  exact starting offset.
- A bucket that straddles a standard-deviation band boundary is colored using its central return
  value's band membership (Edge Cases), since the request colors "the bar" as a single unit, not
  a partial/split bar.
- The reference-line and bar-coloring changes apply to the histogram chart only; the "statistic /
  value" table introduced by the prior Risk-page feature is unaffected, since the request is
  scoped explicitly to "the last feature's histogram rendering."
- Specific color values ("mid-green", "mid-yellow", "mid-orange", red, and the neutral fallback
  for when standard deviation is undefined) are a qualitative palette intent from the request;
  exact color codes are an implementation detail for the planning phase.
- This feature depends only on data already present in the existing `/risk/return-histogram`
  response (`histogram`, `statistics.mean`, `statistics.median`, `statistics.std_dev_bands`) — no
  new or changed API endpoint is required.
