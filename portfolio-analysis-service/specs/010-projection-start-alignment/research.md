# Research: Projection Start Alignment

## 1. Where the extra row comes from

**Decision**: The leading off-boundary row is the *clamped first window* from
`aggregate_last_observation()`; trim it in `ProjectionService`.

**Rationale**: `_build_projected_series` builds a business-day frame starting at `resolved_start`
and passes `resolved_start` as the clamp. `_window_start_date` returns
`bdate_on_or_after(max(period_start, resolved_start))`, so the first (partial) window is dated
`resolved_start` (2026-09-22) and carries the last observation of that window (end of September).
The next window is dated at its real start (2026-10-01). Hence both rows in the reported bug. The
clamp exists for the time series endpoints, where the first row must not precede the requested
`start`; for a projection that clamp is exactly the artefact to remove.

**Alternatives considered**:
- *Change `aggregate_last_observation()`*: rejected — shared by the time series, position time
  series and performance endpoints, whose clamp behaviour is specified and tested; `009`'s plan
  forbids modifying it.
- *Start the business-day frame at the next boundary*: rejected — the compounding exponent `t` is
  business days since `resolved_start` (009 research #5); moving the frame start would shift values
  and violate FR-007.

## 2. Detecting "start is a boundary"

**Decision**: Skip the trim when `periodicity is DAY`; otherwise compute
`natural = bdate_on_or_after(Period(resolved_start, alias).start_time)` and trim only when
`natural != resolved_start`. Trimming is `rows with date > resolved_start` (the clamped row is the
only one dated `resolved_start`; every other window date is strictly later).

**Rationale**: Handles boundaries on weekends (start Mon 2026-11-02, month start Sun 11-01 →
natural 11-02 == start, row retained) and weeks (start Tuesday → trimmed; start Monday → kept),
using the same `PERIOD_ALIAS` and the same business-day adjustment the aggregator uses, so the
two can never disagree.

**Alternatives considered**: `resolved_start.day == 1` style checks — rejected, wrong for
week/quarter/annual and weekends.

## 3. End of series (FR-009)

**Decision**: No code change; add a regression test.

**Rationale**: Windows are dated at their start business day, so with `projection_date=2026-12-31`
monthly the last window is dated 2026-12-01 (valued at the last observation ≤ 2026-12-31). No
row is dated at `projection_date` unless it is a window start. This already matches the
clarified behaviour.

## 4. Empty result

**Decision**: If trimming leaves no rows (next boundary is after `projection_date`), the return
contributes no entries, exactly as the existing "insufficient history" omission does.

**Rationale**: Matches the spec edge case; the existing `entries.extend(...)` over an empty frame
is already safe. Consequence: that return name is absent from `positions`.

## 5. Historical series

**Decision**: Untouched (FR-006). The historical Sept window stays dated 2026-09-01 carrying the
2026-09-22 value.
