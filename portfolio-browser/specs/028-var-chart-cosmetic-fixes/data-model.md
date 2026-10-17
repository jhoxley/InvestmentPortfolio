# Phase 1 Data Model: Value at Risk Chart Cosmetic Fixes

No new API entities and no change to any existing one. This feature changes only
presentation-layer layout, visibility, and labelling over data already modeled by
`portfolio-analysis-service` responses (see `specs/026-var-risk-view/data-model.md` for the
VaR series/backtest/methods entities, unchanged here).

## Combined Backtest Table (presentation change only)

Replaces the former "one `DataTable` per selected confidence level" layout
(`specs/027-risk-page-cleanup/data-model.md`'s note that the panel uses a `DataTable`
already stands; only its *count and shape* changes here).

| Column | Source | Notes |
|---|---|---|
| `statistic` | Fixed label (Exceptions, Kupiec p-value, Conditional coverage p-value, Zone, Mean VaR, VaR stability) | Row key; unchanged from the prior per-level table's row labels |
| one column per selected confidence level, e.g. `level_9500`, `level_9750`, `level_9900` | `level[statistic_field]` for the matching `confidence_bp`, from the already-fetched backtest result | Column header is the formatted confidence label (e.g. `"95%"`); column appears only while that confidence level is selected (spec FR-003/FR-004). Prefixed `level_`, not `pct_`, to avoid confusion with this feature area's unrelated `units == "pct"` chart-display concept (`/speckit-analyze` finding F3) |

**Derivation rule**: for each selected `confidence_bp` (already an input to `build_panel`),
look up its row in the single already-fetched backtest result
(`backtest_by_basis_quality[pnl_basis][min_quality]["levels"]`), exactly as the prior
per-level table did — no new lookup or calculation.

## Value at Risk Chart Trace Visibility (presentation change only)

| Trace | Shown when `units == "gbp"` | Shown when `units == "pct"` |
|---|---|---|
| Realised PnL (bar) | Yes (unchanged) | No — hidden; no percentage-equivalent field exists on `VarSeriesEntry` (confirmed: `hypothetical_pnl_gbp`/`ladder_pnl_gbp` have no `_pct` counterpart, unlike `var_gbp`/`var_pct` and `es_gbp`/`es_pct`) |
| VaR forecast (line) | Yes, `var_gbp` | Yes, `var_pct` (unchanged — already percentage-aware) |
| Expected Shortfall (line, optional) | Yes, `es_gbp` | Yes, `es_pct` (unchanged — already percentage-aware) |
| Total Market Value (linked chart) | Yes (unchanged, money) | Yes (unchanged, money — the linked chart's own units are independent of the main chart's units toggle) |
| Proxied/Rescaled Share (linked chart) | Yes (unchanged, %) | Yes (unchanged, %) |

## Chart Captions (new, static)

| Caption | Attached to | Text (fixed, not data-derived) |
|---|---|---|
| Main chart caption | First subplot row (`make_subplots`' `subplot_titles[0]`) | Describes realised profit/loss against the Value at Risk (and Expected Shortfall, when shown) forecast |
| Linked chart caption | Second subplot row (`subplot_titles[1]`) | Describes the account's total market value and its proxied/rescaled share over the same period |

Both captions are fixed strings rendered via Plotly's own `subplot_titles` mechanism — not
derived from fetched data, and not independently stored or configured.
