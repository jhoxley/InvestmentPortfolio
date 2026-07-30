# Phase 1 Data Model: Overview Position Visualizations

This feature introduces no new API models — it reuses
`src/models/portfolio_analysis.py::PositionTimeSeriesEntry`/
`PositionTimeSeriesResponse` (`018-positions-page`) verbatim. Everything
below is a derived, presentation-only shape computed from that existing
response.

## Position Weight Slice (new, derived — not fetched, not stored)

One pie-chart slice, derived from a single `PositionTimeSeriesResponse`
whose `entries` all share the same (single) date.

| Field | Type | Derivation |
|---|---|---|
| `position` | `str` | From `entries[].position`. |
| `market_value` | `float` | From `entries[].market_value`; excluded entirely if absent or `<= 0` (FR-012, Edge Cases). |
| `share` | `float` | `market_value / sum(market_value across all included slices)`. Used only to compute the hover tooltip's percentage — no longer drives any on-slice labeling decision. |

*(Revised 2026-07-24, research.md #3: the original `label_visible`
5%-threshold field was removed — no slice ever carries on-slice text now.
Identification is via the below-chart legend's color mapping and via
hover only.)*

## Position Performance Rank Row (new, derived — not fetched, not stored)

One row of the "Biggest winners and losers" table, derived from the same
response's `pnl`/`book_cost` values.

| Field | Type | Derivation |
|---|---|---|
| `position` | `str` | From `entries[].position`. |
| `pnl` | `float` | From `entries[].pnl`; a position with no `pnl` value on the "To" date is excluded entirely (FR-012). |
| `book_cost` | `float \| None` | From `entries[].book_cost` (context only — never used for ranking or inclusion; spec Assumptions). |
| `group` | `"winner" \| "loser"` | Positions are sorted by `pnl` descending; the top up to 5 are `"winner"`, the bottom up to 5 (of the *remaining* positions, after winners are removed) are `"loser"` — see "Ranking algorithm" below for the exact split when fewer than 10 qualifying positions exist. |
| `rank_index` | `int` | 0-based position within its own group, counted from the group's "brightest" end (index 0 = best winner; index 0 = *worst* loser — see research.md #4). |
| `color` | `str` (hex) | `_gradient_color(rank_index, group_size, ...)` (research.md #4), green endpoints for `"winner"`, blue endpoints for `"loser"`. |

### Ranking algorithm

1. Collect every position with a recorded `pnl` value in the response
   (FR-012's exclusion).
2. Sort descending by `pnl`, tie-broken ascending by `position` name
   (spec Edge Cases — stable, reproducible ordering).
3. Let `n` = total qualifying positions.
   - If `n >= 10`: winners = first 5, losers = last 5 (of the same sorted
     list — i.e. positions 6..10 counting from the bottom, in
     mildest-to-worst order for display, per FR-006).
   - If `n < 10`: winners = the first `ceil(n / 2)` positions, losers =
     the remaining `floor(n / 2)` — every qualifying position appears
     exactly once, no padding, no duplicate (FR-013, Edge Cases). A
     single leftover "middle" position when `n` is odd is assigned to the
     winners group (the higher-`pnl` half), matching "highest pnl
     positions" taking priority in FR-006's own ordering.
4. Losers are displayed mildest-first (closest to the winners) through
   worst-last, i.e. reverse of the descending sort's natural tail order.

## State flow summary

```text
Overview's existing account-change / "To"-date-change (already-established
Inputs on `_render_chart`; this feature adds a second, independent
callback listening to the same two props, NOT to `from_date` or the
attribute toggles — research.md #6)
  → GET /v1/accounts/{account}/position?attribute=market_value&attribute=pnl
      &attribute=book_cost&start={to_date}&end={to_date}
      (positions omitted — every position included, per 018's existing
      "omitted = all positions" client behavior)
  → build Position Weight Slice list (exclude non-positive market_value)
      → build the pie chart (research.md #3)
  → build Position Performance Rank Row list (exclude missing pnl,
      rank + split into winner/loser groups, ranking algorithm above)
      → build the winners/losers table (research.md #4)
  → both render together from the same single response — never two
      separate fetches that could disagree (mirrors 018's own FR-013/
      SC-006 atomicity precedent, applied here to a single-date snapshot
      instead of a date-range series)
```
