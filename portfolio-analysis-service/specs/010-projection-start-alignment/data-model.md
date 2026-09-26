# Data Model: Projection Start Alignment

No new or changed entities, fields, or response models. `PositionTimeSeriesResponse` and
`PositionTimeSeriesEntry` are reused unchanged.

## Behavioural rule on the existing projected series

| Concept | Rule |
|---|---|
| Projected series (per return) | Rows dated at window-start business days. First row is `resolved_start` only if `periodicity == day` or `resolved_start` is its own period's window-start business day; otherwise the first row is the next window start. |
| Window-start business day | First business day on or after the calendar period's start (`W` from Monday, `M`, `Q`, `Y`), as already defined by `aggregate_last_observation()`. |
| Last row | The last window start on or before `projection_date`; no extra row at `projection_date`. |
| Empty series | Allowed when the next window start is after `projection_date`; the return name is then absent from `positions`. |

## Worked examples (monthly, `projection_date=2026-12-31`)

| `resolved_start` | Projected series dates |
|---|---|
| 2026-09-22 (Tue) | 2026-10-01, 11-02, 12-01 |
| 2026-10-01 (Thu) | 2026-10-01, 11-02, 12-01 |
| 2026-11-02 (Mon, month starts Sun) | 2026-11-02, 12-01 |
| 2026-12-15 | *(empty)* |
