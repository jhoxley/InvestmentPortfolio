# Phase 1 Data Model: Periodicity Control for Overview & Positions

**Feature**: `021-periodicity-controls` | **Date**: 2026-09-22

This is a presentation-layer feature. It introduces **no persisted data** and **no new financial
entity** — only a configuration section, one piece of per-page view state, and one optional field
on two existing response models.

---

## 1. `PeriodicityOption` — configuration entity (`config/content.py`, NEW)

One selectable interval, as offered to the user.

| Field | Type | Purpose | Validation |
|---|---|---|---|
| `key` | `str` | Stable identifier used in component ids and callback branching | Required, non-empty, unique across options; drawn from the fixed set `day`/`week`/`month`/`quarter`/`year` |
| `label` | `str` | Visible button text | Required, non-empty, unique across options |
| `value` | `str` | The interval name sent to the analysis service | Required, non-empty, unique across options |

The `key` and `value` differ for exactly one option — `key: year` carries `value: annual`, the
analysis service's own name for that interval. Every other option's `key`, `label` and `value`
coincide. That divergence living in data rather than code is deliberate: it is the only place the
UI's vocabulary and the service's differ, and it is visible at a glance in `content.yaml`.

---

## 2. `PeriodicityConfig` — configuration entity (`config/content.py`, NEW)

The whole control's configuration, hung off `ContentConfig` as `periodicity`.

| Field | Type | Purpose |
|---|---|---|
| `label` | `str` | The control's own label ("Periodicity") |
| `options` | `list[PeriodicityOption]` | The five intervals, in display order |
| `thresholds` | `PeriodicityThresholds` | Year bounds driving automatic derivation |

**`PeriodicityThresholds`**:

| Field | Type | Meaning |
|---|---|---|
| `day_max_years` | `int` | Spans up to and including this many years derive `day` (1) |
| `month_max_years` | `int` | …then `month` (3) |
| `quarter_max_years` | `int` | …then `quarter` (5); anything longer derives `year` |

**Validation rules (fail-fast at startup, per Principle IV)**:

- `options` MUST contain exactly five entries.
- `key`, `label` and `value` MUST each be unique across options.
- Thresholds MUST be strictly ascending (`day < month < quarter`) and all positive.
- Every interval a threshold can resolve to — `day`, `month`, `quarter`, and the `year` fallback —
  MUST be present among `options`' keys. A config that could derive an interval the control cannot
  display is rejected rather than allowed to produce an unreachable state.

**Note on what is *not* configurable**: the option `key` strings are also declared as module
constants in `src/components/periodicity_controls.py` and are branched on in code. This mirrors
`date_range_controls.py`'s shortcut codes ("fixed, spec-defined set — not user-configurable"):
labels and thresholds are content, identifiers are contract.

---

## 3. `PeriodicitySelection` — per-page view state (a `dcc.Store` payload, not a class)

The single source of truth for what interval a page is currently plotting at. Held in
`{page}-periodicity-store`, one per page, scoped to the page visit (no persistence).

| Field | Type | Meaning |
|---|---|---|
| `value` | `str` | The **service-side** interval value currently in effect (e.g. `annual`) |
| `explicit` | `bool` | `true` once the user has clicked a button; `false` while derived |

**State transitions**:

| From | Event | To |
|---|---|---|
| (absent) | page mounts, dates resolve | `{value: derive(span), explicit: false}` |
| `explicit: false` | date range changes | `{value: derive(new span), explicit: false}` |
| `explicit: false` | user clicks an interval | `{value: clicked, explicit: true}` |
| `explicit: true` | date range changes | **unchanged** (FR-012) |
| `explicit: true` | user clicks an interval | `{value: clicked, explicit: true}` |
| any | page unmounts (navigation away) | discarded |

**Invariants**:

- `explicit` can only ever be set by a button click, never by the derivation path — which is what
  makes FR-012 hold regardless of callback ordering.
- `value` is always one of the five configured `value`s; nothing else can be written.
- The rendered chart and the button styling both read `value`, so FR-011 ("the control always
  shows the interval in effect") is structural rather than something to keep in sync.

---

## 4. Derivation — pure function contract

```python
def derive_periodicity(
    from_date: date, to_date: date, thresholds: PeriodicityThresholds
) -> str: ...
```

| Aspect | Contract |
|---|---|
| **Input** | The effective range shown in the existing date pickers |
| **Output** | One option `key` — never `week` |
| **Rule** | `from_date >= to_date - day_max_years` → `day`; else `>= to_date - month_max_years` → `month`; else `>= to_date - quarter_max_years` → `quarter`; else `year` |
| **Boundaries** | Inclusive comparisons, so exactly 1/3/5 years resolve to the *finer* interval (`day`/`month`/`quarter`) |
| **Year arithmetic** | Delegated to `date_range_controls.py::_years_before`, so "N years ago" matches the 1Y/3Y/5Y shortcut buttons exactly, leap-day fallback included |
| **Degenerate input** | `from_date == to_date` → `day`; `from_date > to_date` (transient during editing) → `day`, never an exception |
| **Purity** | No I/O, no clock read (`to_date` is supplied), no Dash imports |

---

## 5. `TimeSeriesResponse` / `PositionTimeSeriesResponse` — MODIFIED (`src/models/portfolio_analysis.py`)

| Field | Change |
|---|---|
| existing fields | unchanged |
| **`periodicity`** | **NEW**, `str \| None = None` — the interval the service reports having applied |

Optional with a `None` default so responses from a pre-008 service (which omit it entirely) still
validate. Captured rather than ignored so the client can log a warning when the echoed value is
absent or differs from what was requested — the silent-mismatch guard from research.md §6.

`TimeSeriesEntry` and `PositionTimeSeriesEntry` are **unchanged**: 008 returns aggregated entries
in exactly the same shape as daily ones.

---

## 6. Summary of the change surface

| Kind | Count | Items |
|---|---|---|
| New config entities | 3 | `PeriodicityOption`, `PeriodicityThresholds`, `PeriodicityConfig` |
| New config data | 1 section | `periodicity:` in `content.yaml` |
| New view state | 1 per page | `{page}-periodicity-store` |
| New pure functions | 1 | `derive_periodicity()` |
| New components | 1 | `build_periodicity_control()` |
| Modified models | 2 | one optional field each |
| Modified client methods | 2 | one optional parameter each |
| Modified pages | 2 | store + 2 callbacks + fetch argument each |
| Persisted schema changes | **0** | — |
| New financial derivations | **0** | Principle I — the service owns all aggregation |
