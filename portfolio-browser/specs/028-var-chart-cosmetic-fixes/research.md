# Research: Value at Risk Chart Cosmetic Fixes

## 1. Moving the legend below the chart

**Decision**: Set the figure's `legend` to the exact same horizontal, centered position
already established by `_performance_chart.py`, `_projection_chart.py`, and
`_positions_chart.py` — `legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor":
"center"}` — with no different `y` value for this chart's two subplot rows (see
Implementation note below, corrected per `/speckit-analyze` finding F1).

**Rationale**: `build_figures()` currently sets no explicit `legend` position at all, so
Plotly's default (inside the plot area, upper right) is used — this is exactly what
crowds into the same horizontal space the backtest panel's column occupies (`risk.py`'s
`dbc.Col(..., width=9)` for the chart, `width=3` for the panel). Every other chart in this
codebase already solves the identical problem the same way; reusing that convention is
both the smallest diff and the one most consistent with the rest of the app.

**Alternatives considered**: Narrowing the chart's column width to make room for an
in-plot-area legend (rejected — doesn't fix the root cause and shrinks the chart itself)
and moving the legend to the chart's left side (rejected — no existing precedent in this
codebase, and would not obviously read better than below-chart).

**Implementation note** (corrected per `/speckit-analyze` finding F1): Plotly's legend
`y`, with the default `yref="paper"`, is relative to the *entire figure's* paper space —
not to any individual subplot row — so `y=-0.2` already positions the legend below both
of this figure's stacked rows (`row_heights=[0.7, 0.3]`) exactly as it positions it below
the single row in Performance/Projection/Positions' charts. No different `y` value is
needed for this chart specifically. If the legend still renders clipped or too close to
the bottom row once implemented, the correct fix is increasing `fig.update_layout`'s
existing `margin["b"]` (currently `30`) to reserve more pixel space below the whole
figure — not changing the legend's relative `y` offset. Confirm empirically against
`quickstart.md` step 1; this is a visual-polish detail, not a product decision either way.

## 2. Combining the up-to-three backtest tables into one

**Decision**: Replace `_level_block()`'s one-`DataTable`-per-confidence-level loop with a
single `dash_table.DataTable` whose first column is the statistic name and whose remaining
columns are one per currently selected confidence level (labelled e.g. `"95%"`, `"97.5%"`,
`"99%"`), built from the same six statistics (`Exceptions`, `Kupiec p-value`, `Conditional
coverage p-value`, `Zone`, `Mean VaR`, `VaR stability`) already rendered today.

**Rationale**: The underlying data (`backtest_by_basis_quality[pnl_basis][min_quality]`) is
unchanged — only the *shape* of the table changes, from "N small tables, each with a
statistic/value pair" to "one table, N value columns". This directly satisfies spec FR-003/
FR-004: columns appear/disappear immediately as confidence selection changes, because
`selected_confidence_bp` is already an `Input` to the callback that calls `build_panel()`
(`_render_var_view`), unchanged by this feature.

**Alternatives considered**: A table with confidence level as a *row* dimension instead of
a column (rejected — the user explicitly asked for "a single table with 1-3 value
columns", and rows-per-statistic/columns-per-level is also what makes comparing one
statistic *across* levels a single horizontal read, which was the stated motivation).

## 3. Hiding realised PnL when units are percentage

**Decision**: In `build_figures()`, when `units == "pct"`, skip adding the realised-PnL
`go.Bar` trace entirely (both its figure trace and its exception-coloring computation);
when `units == "gbp"`, behavior is unchanged. No new field or API call is introduced.

**Rationale**: Confirmed against `src/models/portfolio_analysis.py`'s `VarSeriesEntry` —
it defines `hypothetical_pnl_gbp`/`ladder_pnl_gbp` (money) but no corresponding `_pct`
equivalent (unlike `var_gbp`/`var_pct` and `es_gbp`/`es_pct`, which already have both
units). There is therefore no percentage-equivalent value available to plot, and the
spec's own Assumptions section already settles this: hide, don't invent a rescaled or
misleading value. Because `build_figures()` is already called fresh on every
confidence/units/pnl-basis/hide-degraded/show-ES change (FR-010/FR-012 from 026, still
true), switching units back to money automatically restores the bars with no extra state
to manage — the chart is rebuilt from scratch from `risk-var-store`'s unchanged data every
time any control changes (confirms spec FR-006 is satisfied "for free").

**Alternatives considered**: Computing an approximate percentage PnL as
`hypothetical_pnl_gbp / total_value_gbp * 100` client-side (rejected — this would be a new
derived financial fact computed in the UI, which Constitution Principle I prohibits; the
correct fix, if this figure is wanted later, is a new field on the
`portfolio-analysis-service` response, not a client-side approximation).

## 4. Chart captions without breaking the linked-chart's shared x-axis

**Decision**: Pass `subplot_titles=["Realised PnL vs. Value at Risk forecast", "Total
Market Value and Proxied/Rescaled Share"]` to the existing `make_subplots(rows=2, cols=1,
shared_xaxes=True, ...)` call, rather than splitting the single `go.Figure` into two
separate `dcc.Graph` components.

**Rationale**: `shared_xaxes=True` is what makes zooming/panning the main chart also
zoom/pan the linked market-value chart beneath it — the entire point of 026 User Story 1's
"linked chart... so changes in portfolio construction are visible" alongside the main one.
Splitting into two `dcc.Graph`s would lose that link unless a new relayout-sync callback
were added, which is both a functional regression risk and well beyond what a "cosmetic...
add captions" request calls for. Plotly's `subplot_titles` renders a text annotation
directly above each subplot row within the same figure — which is exactly "a caption
ahead of each graph" from the user's perspective (they already describe the two subplot
rows as "the two VaR charts"), achieved with a single, data-only parameter.

**Alternatives considered**: Splitting into two `dcc.Graph` components with Dash
`html.Div`/`html.P` captions above each, wired through a new x-axis-range-sync callback
(rejected — materially larger and riskier change than this feature's scope, for a result
`subplot_titles` already achieves natively) and adding the captions as `fig.add_annotation`
calls instead of `subplot_titles` (rejected — `subplot_titles` is the purpose-built,
no-manual-positioning-math option `make_subplots` already exposes for exactly this case).
