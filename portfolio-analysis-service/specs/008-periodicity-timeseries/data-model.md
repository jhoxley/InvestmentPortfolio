# Phase 1 Data Model: Periodicity Parameter for Account & Position Time Series

**Feature**: `008-periodicity-timeseries` | **Date**: 2026-09-22

This feature introduces **no persisted data** and **no new stored column**. Everything below is
either an in-request value object or an additive field on an existing response model.

---

## 1. `Periodicity` — value object (`app/models/periodicity.py`, NEW)

A closed vocabulary of calendar aggregation intervals.

| Member | Wire value | pandas period alias | Calendar alignment |
|--------|-----------|---------------------|--------------------|
| `DAY` | `day` | — (no aggregation) | one entry per business day |
| `WEEK` | `week` | `W` | Monday |
| `MONTH` | `month` | `M` | 1st of the calendar month |
| `QUARTER` | `quarter` | `Q` | 1 Jan, 1 Apr, 1 Jul, 1 Oct |
| `ANNUAL` | `annual` | `Y` | 1 Jan |

**Type**: `class Periodicity(str, Enum)` — string-based so `model_dump(mode="json")` emits the
bare wire value, and so it can be compared against a raw query string.

**Companion constants**:

- `SUPPORTED_PERIODICITY_VALUES: tuple[str, ...]` — request-order tuple
  `("day", "week", "month", "quarter", "annual")`, used in the OpenAPI `enum`, in the error
  message and in tests, so the allowed set is declared exactly once.
- `PERIOD_ALIAS: dict[Periodicity, str]` — maps every member **except** `DAY` to its pandas
  alias. `DAY`'s absence is deliberate: it makes "no aggregation" a lookup miss rather than a
  special-cased string.

**Validation rules** (FR-001, FR-002, FR-014):

| Input | Result |
|-------|--------|
| absent / `None` | `Periodicity.DAY` |
| `"day"`, `"week"`, `"month"`, `"quarter"`, `"annual"` | the matching member |
| `"Annual"`, `"yearly"`, `"daily"`, `"Q"`, `"fortnight"`, `""`, any other string | `UnsupportedPeriodicityError` |

**State transitions**: none — immutable value object resolved once per request.

---

## 2. `PeriodWindow` — derived, in-request concept (not a class)

One calendar-aligned span within the resolved date range. It exists only as two derived values
inside `aggregate_last_observation()` and is never serialised, so it is modelled as a labelled
column rather than a type:

| Concept | Derivation | Constraint |
|---------|-----------|------------|
| **Period key** | `pd.to_datetime(df["date"]).dt.to_period(PERIOD_ALIAS[periodicity])` | groups rows; groups with no rows never exist, satisfying FR-009 |
| **Reported date** | `bdate_range(start=max(period.start_time.date(), resolved_start), periods=1)[0].date()` | always a business day; always ≥ `resolved_start`, so never outside `[from_date, to_date]` (FR-006) |
| **Source row** | last row of the group after sorting by `date` | bounded above by `resolved_end` because the input frame is already clipped (FR-007); a whole row, so all attributes share one source date (FR-008) |

**Invariant worth testing directly**: the reported date is a function of `(period, resolved_start)`
alone — never of the frame's contents. Therefore two different positions in the same window carry
the **same** reported date, which is what allows per-position and account-level series to be
overlaid.

---

## 3. `TimeSeriesResponse` — MODIFIED (`app/models/timeseries.py`)

| Field | Type | Change |
|-------|------|--------|
| `account_name` | `str` | unchanged |
| `attributes` | `list[str]` | unchanged |
| `from_date` | `date` | unchanged — still the resolved **daily** range start (FR-013) |
| `to_date` | `date` | unchanged — still the resolved **daily** range end (FR-013) |
| `entries` | `list[TimeSeriesEntry]` | unchanged shape; row count and dates now reflect the applied periodicity |
| `links` (`_links`) | `dict[str, str]` | unchanged |
| **`periodicity`** | **`Periodicity`** | **NEW** — default `Periodicity.DAY`, always serialised, not in OpenAPI `required` (FR-011, FR-012) |

`TimeSeriesEntry` itself is **unchanged** (`extra="allow"`, dynamic attribute keys). An aggregated
entry is structurally identical to a daily one — same `date` key, same attribute keys — so no
client-side type change is needed.

---

## 4. `PositionTimeSeriesResponse` — MODIFIED (`app/models/position_timeseries.py`)

| Field | Type | Change |
|-------|------|--------|
| `account_name` | `str` | unchanged |
| `attributes` | `list[str]` | unchanged |
| `positions` | `list[str]` | unchanged — still the positions actually represented in `entries`, sorted |
| `from_date` / `to_date` | `date` | unchanged (FR-013) |
| `entries` | `list[PositionTimeSeriesEntry]` | unchanged shape; now one entry per (window, position) that has data |
| `links` (`_links`) | `dict[str, str]` | unchanged |
| **`periodicity`** | **`Periodicity`** | **NEW** — default `Periodicity.DAY`, as above |

`PositionTimeSeriesEntry` is **unchanged** (`date`, `position`, plus dynamic attribute keys).

Ordering is unchanged: entries remain sorted by `(date, position)` (FR-010).

---

## 5. `UnsupportedPeriodicityError` — NEW (`app/exceptions.py`)

Mirrors the existing `UnsupportedAttributeError` in shape and message style.

| Attribute | Type | Purpose |
|-----------|------|---------|
| `requested` | `str` | the rejected raw value, echoed for diagnosis |
| `supported` | `tuple[str, ...]` | `SUPPORTED_PERIODICITY_VALUES` |
| `message` | `str` | e.g. `Periodicity 'fortnight' is not supported. Supported values: day, week, month, quarter, annual.` — names the full set so FR-014 / SC-007 hold from the error body alone |

**HTTP mapping**: 422 Unprocessable Entity, RFC 7807 `application/problem+json`,
`type = https://portfolio-analysis/errors/unsupported-periodicity`,
`title = "Unsupported Periodicity"`, via a new handler in `app/main.py` using the existing
`_problem()` helper.

---

## 6. Aggregation contract (`app/services/periodicity_aggregation.py`, NEW)

```python
def aggregate_last_observation(
    df: pd.DataFrame,
    periodicity: Periodicity,
    resolved_start: date,
) -> pd.DataFrame: ...
```

| Aspect | Contract |
|--------|----------|
| **Input** | A frame with a `date` column of `datetime.date`, one row per business day, already forward-filled and clipped to `[resolved_start, resolved_end]` — i.e. exactly what `expand_business_days` returns, with any derived columns (e.g. `pnl`) already added |
| **Output** | Same columns in the same order; one row per non-empty calendar window; `date` replaced by the window's reported date; sorted ascending by `date`; index reset |
| **`Periodicity.DAY`** | Returns the input unchanged (identity), so callers need no branch and FR-003 is structural |
| **Empty input** | Returns the empty frame unchanged |
| **Purity** | No I/O, no repository, no account context, no mutation of the caller's frame |
| **Position handling** | Called once per position by `PositionTimeSeriesService`; the function itself is position-agnostic, which is why window dates stay uniform across positions |

---

## 7. Summary of the change surface

| Kind | Count | Items |
|------|-------|-------|
| New models | 1 | `Periodicity` (+ 2 companion constants) |
| Modified models | 2 | `TimeSeriesResponse`, `PositionTimeSeriesResponse` — one additive field each |
| New services | 1 | `periodicity_aggregation.aggregate_last_observation()` |
| Modified services | 2 | `TimeSeriesService.get_series()`, `PositionTimeSeriesService.get_series()` — one defaulted parameter + one delegating call each |
| New validators | 1 | `resolve_periodicity()` |
| New exceptions | 1 | `UnsupportedPeriodicityError` (+ 1 handler) |
| Modified routes | 2 | `/accounts/{account_name}/timeseries`, `/accounts/{account_name}/position` |
| Persisted schema changes | **0** | — |
