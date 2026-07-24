# Phase 0 Research: Overview Position Visualizations

## 1. Data source — reuse the existing position-timeseries endpoint verbatim

- **Decision**: Both new widgets are served by a single call to the
  already-implemented `PortfolioAnalysisClient.get_position_timeseries()`
  (added in `018-positions-page`), requesting
  `attributes=["market_value", "pnl", "book_cost"]`, `positions=[]` (every
  position), and `start=end=<selected "To" date>`. No new client method, no
  new Pydantic model, no new upstream endpoint.
- **Rationale**: The spec's own data source (`GET
  .../accounts/{account_name}/position`) is the exact endpoint `018`
  already integrated and documented in
  `specs/018-positions-page/contracts/portfolio-analysis-api.md`. Since a
  single-date snapshot (`start == end`) with all three needed attributes
  can be requested in one call, both the pie chart (needs `market_value`)
  and the winners/losers table (needs `pnl` + `book_cost`) are satisfied by
  one fetch — avoiding two round-trips for what is fundamentally one
  snapshot query, and reusing an already-tested, already-contracted client
  method rather than adding a parallel one.
- **Alternatives considered**: A new client method scoped to exactly this
  feature's three attributes — rejected: `get_position_timeseries` already
  accepts an arbitrary attribute list, so a narrower wrapper would add a
  second code path to the same endpoint for no behavioral difference,
  violating the constitution's SOLID/no-duplication guidance. Two separate
  calls (one per widget) — rejected: needlessly doubles network round-trips
  for data that differs only in which columns of the same single-date
  response each widget reads.

## 2. Extracting shared value formatting (second-caller justification)

- **Decision**: Move `_format_attribute_value()` and the
  `_PLAIN_NUMERIC_ATTRIBUTES` set out of `src/pages/_positions_chart.py`
  (018) into a new shared module, `src/components/value_formatting.py`.
  Both `_positions_chart.py` and the new
  `src/pages/_overview_position_widgets.py` import it.
- **Rationale**: `market_value`, `pnl`, and `book_cost` are all monetary
  attributes already covered by `018`'s existing currency-vs-plain-numeric
  formatting logic (FR-008a there) — this feature is a second, concrete
  caller of that exact function, the same condition that justified
  extracting `date_range_controls.py`/`attribute_toggles.py` out of
  Overview-only code in `018`'s own research.md #1/#2. Duplicating the
  monetary-attribute-name list a third time (Overview's pie chart, Overview's
  table, and Positions' comparison table) would let the two copies drift.
- **Alternatives considered**: Leaving it private to `_positions_chart.py`
  and importing it directly from there into the new Overview module —
  rejected: `_positions_chart.py`'s own module docstring explains it's kept
  side-effect-free specifically so it can be imported outside a running
  Dash app; reaching into another *page's* private module for a
  cross-cutting formatting concern is exactly the shape of coupling the
  `018` extractions were meant to avoid — a small, explicit shared module
  is one import away either way, with a clearer ownership story.

## 3. Pie chart: labeling threshold, hover, and slice coloring

- **Decision**: A single `plotly.graph_objects.Pie` trace. Per-slice `text`
  is set to the position name only for slices whose share is ≥5% of the
  account's total market value (empty string otherwise, so Plotly draws no
  on-slice label for small slices — `textinfo="text"`); `hovertemplate` is
  set on every slice regardless of size, showing exact position name,
  market value, and percentage. Slice colors use Plotly's own default
  qualitative color sequence — no custom palette.
- **Rationale**: `go.Pie`'s own `text`/`textinfo`/`hovertemplate` props are
  the built-in, first-class mechanism for exactly this per-slice
  label-vs-hover split (Principle V: use the library's own mechanism, same
  precedent `018` set for `stackgroup`). The 5% labeling threshold and
  always-on hover were fixed directly by `/speckit-clarify`'s Q1 answer.
  Slice coloring has no cross-refresh *stability* requirement in this
  spec (unlike `018`'s FR-015 for the line chart, which explicitly required
  a position to keep the same color across selections/date ranges) — this
  pie chart is a single, self-contained snapshot re-rendered wholesale on
  every account/date change, so there is no "does this color persist"
  question to answer, and Plotly's own default sequence is sufficient
  without reinventing `018`'s 50-color hash palette for a materially
  different requirement.
- **Alternatives considered**: Reusing `_positions_chart.py`'s
  `_color_for_position()` hash-based palette for pie slices too — rejected:
  that function exists specifically to guarantee color *stability* across
  a line chart's changing selection over time, a property this pie chart's
  spec never asks for; reusing it here would import a Positions-page
  concept into Overview for a requirement that doesn't exist, adding
  coupling without a corresponding need. Grouping small slices into an
  "Other" catch-all — rejected per spec Assumptions (every position is its
  own slice; the labeling threshold, not a grouping cutoff, is how small
  positions are handled per `/speckit-clarify` Q1).

## 4. Winners/losers gradient: interpolation and the single-row-group edge case

- **Decision**: A pure function,
  `_gradient_color(index: int, group_size: int, bright_hex: str, pale_hex: str) -> str`,
  linearly interpolating RGB channels between two hex endpoints. For the 5
  winner rows: `bright_hex` = a saturated green, `pale_hex` = a very pale
  green, with `index` counted from the *best* position (row 1) so index 0
  → brightest. For the (up to) 5 loser rows: the same function is called
  with the *loser* endpoints (`pale_hex` = pale blue for the mildest loser,
  `bright_hex` = saturated blue for the single worst position), with
  `index` counted from the *worst* position backward, so the single worst
  loser always resolves to the brightest blue regardless of how many
  losers are actually present (including the `group_size == 1` case) —
  matching the spec's own anchor ("row-10 for the lowest pnl position",
  i.e. brightness is anchored to *rank*, not to a fixed row slot.
- **Rationale**: The spec (FR-008, FR-013) describes a gradient anchored at
  named extremes — the single best winner is always the brightest green,
  the single worst loser is always the brightest blue — not a fixed
  5-slot gradient that only looks right at exactly 5 rows per side. Basic
  linear interpolation between two named colors is the simplest mechanism
  that satisfies this for any group size from 1 to 5 (FR-013's
  fewer-than-10 case), with no new dependency.
- **Alternatives considered**: A fixed 5-entry lookup table of pre-picked
  shades indexed positionally — rejected: breaks exactly at the
  fewer-than-10-positions edge case (FR-013), where a lone loser would
  incorrectly read the *first* (palest) table entry instead of the
  brightest, contradicting the spec's own "brightest = worst" anchor.

## 5. Responsive stacking breakpoint

- **Decision**: The new row's two halves use
  `dbc.Col(..., xs=12, lg=6)` (Bootstrap's `lg` breakpoint, 992px), not
  `md=6` (768px).
- **Rationale**: This project's own existing BDD suite already defines a
  concrete "tablet viewport width" for testing purposes —
  `tests/bdd/steps/test_shell_steps.py`'s `_TABLET_WIDTH = 800` (015's own
  precedent, reused as-is here rather than inventing a second definition).
  800px sits *above* Bootstrap's default `md` breakpoint (768px) but
  *below* its `lg` breakpoint (992px) — using `md=6` would therefore still
  render side-by-side at this project's own definition of "tablet width,"
  silently failing `/speckit-clarify` Q2's "stack at tablet width" answer.
  `lg=6` is the breakpoint that actually stacks at 800px while remaining
  side-by-side at the project's own `_DESKTOP_WIDTH = 1280`.
- **Alternatives considered**: `md=6` — rejected for the reason above,
  caught by cross-checking against the project's own existing viewport-width
  test constants rather than assuming Bootstrap's default breakpoint names
  map onto this project's specific "tablet" definition.

## 6. No `running=` clause on the new callback

- **Decision**: The new combined pie+table callback does not declare a
  `running=` clause disabling any controls. Each new container is wrapped
  in its own `dcc.Loading`, matching the existing chart container's own
  pattern, for the required ≤100ms loading feedback.
- **Rationale**: The existing `_render_chart` callback already declares
  `running=[...]` disabling the five shortcut buttons for its own
  duration. Two independent callbacks both targeting the same buttons'
  `disabled` prop via `running=` is untested territory in this codebase
  and an unnecessary risk to take on for a widget pair that has no
  controls of its own to disable in the first place (it only reads the
  already-selected account/"To" date, both controls already covered by
  `_render_chart`'s own `running=` for the shortcuts specifically).
  `dcc.Loading`'s spinner is Dash's own built-in mechanism for exactly this
  kind of "show feedback while a callback runs" requirement (Principle V),
  identical in spirit to how `018`/`017` already prefer built-in
  mechanisms over hand-rolled state.
- **Alternatives considered**: Adding the same five shortcut-button
  `Output`s to this callback's own `running=` list — rejected: would be the
  first place in this codebase two different callbacks' `running=` clauses
  target the same component prop, an untested and unnecessary combination
  for no user-facing benefit beyond what `dcc.Loading` already provides.
