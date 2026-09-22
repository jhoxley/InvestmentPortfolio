# Phase 0 Research: Periodicity Parameter for Account & Position Time Series

**Feature**: `008-periodicity-timeseries` | **Date**: 2026-09-22

No `NEEDS CLARIFICATION` markers were carried into the Technical Context — the spec's one
ambiguity (the first partial window's reported date) was resolved with the requester during
`/speckit-specify` and is recorded in spec.md's Clarifications section. The research below
resolves the *technical* unknowns instead: the exact pandas and FastAPI mechanics this feature
depends on, each verified by execution against the installed versions rather than assumed.

---

## 1. Calendar-aligned period bucketing in pandas 3.0.3

**Decision**: Label each row with `pd.to_datetime(df["date"]).dt.to_period(alias)`, using the
alias map `week → "W"`, `month → "M"`, `quarter → "Q"`, `annual → "Y"`. Derive each window's
calendar start from `period.start_time.date()`.

**Rationale**: Verified by execution under the installed pandas 3.0.3 — all four aliases are
accepted and align exactly as the spec requires:

| Alias | Sample input | Period | `start_time` |
|-------|--------------|--------|--------------|
| `W`   | 2016-03-15 (Tue) | `2016-03-14/2016-03-20` | 2016-03-14 (**Monday**) |
| `M`   | 2016-03-15 | `2016-03` | 2016-03-01 (**1st of month**) |
| `Q`   | 2016-12-30 | `2016Q4` | 2016-10-01 (**calendar quarter**) |
| `Y`   | 2025-12-31 | `2025` | 2025-01-01 (**01-Jan**) |

This satisfies FR-005 with no custom calendar arithmetic: `W` weeks already begin on Monday
(pandas' default `W` is `W-SUN`, i.e. the week *ending* Sunday, which starts Monday), `Q` is
already `Q-DEC` (Jan/Apr/Jul/Oct), and `Y` is already `Y-DEC` (01-Jan). The deprecated `A` alias
is not used.

**Alternatives considered**:

- **`pd.Grouper(freq=...)` / `.resample()`** — rejected. The resample frequency aliases changed in
  pandas 2.2+ (`M` → `ME`, `Q` → `QE`, `Y` → `YE`), so a resample-based implementation would carry
  a second, divergent alias map that emits `FutureWarning`s on some versions. `to_period` aliases
  are stable and were confirmed working as-is. `resample` would also silently **materialise empty
  windows**, which FR-009 explicitly forbids.
- **Manual date arithmetic** (`date.replace(day=1)`, ISO-week maths) — rejected. More code, more
  edge cases (year-straddling weeks such as `2016-12-26/2017-01-01`, leap years), and no benefit
  over a library primitive already proven in this environment.
- **`isocalendar()` week keys** — rejected. Produces `(year, week)` tuples needing separate
  conversion back to a start date, and handles the year boundary differently from `to_period`.

---

## 2. Selecting the last observation of each window

**Decision**: Sort by date, label with the period, then `groupby(period, sort=True).tail(1)` —
keeping the **entire last row** of each window, not a per-column aggregate.

**Rationale**: Taking a whole row satisfies FR-008 (every attribute on one entry comes from the
same source date) as a structural property rather than something tests must police. It also makes
FR-007's range-bounding automatic: the frame handed to the aggregator has already been clipped to
`[resolved_start, resolved_end]` by `expand_business_days`, so the final window's last row *is*
the resolved end date's observation, and a window with no in-range business day simply produces no
group — which is exactly FR-009's "omit, don't null".

**Alternatives considered**:

- **`.agg("last")` per column** — rejected. Column-wise `last` can draw different columns from
  different dates when any column has trailing NaNs, breaking FR-008.
- **`.last()` on a resampler** — rejected for the empty-window materialisation reason above.
- **`.max()` / `.mean()` / period-end selection** — out of scope. The spec is explicit that the
  value is the last observation, and the Assumptions section records that no averaging, summing or
  compounding is introduced.

---

## 3. Reported window-start date, and the first-window clamp

**Decision**: `window_date = bdate_range(start=max(period.start_time.date(), resolved_start), periods=1)[0].date()`
— i.e. clamp the calendar boundary up to the resolved start, then roll forward to the next
business day.

**Rationale**: The clamp implements the clarified decision (no entry date may precede the
response's `from_date`), and the forward roll preserves the endpoints' existing guarantee that
every reported date is a business day. `bdate_range(start=d, periods=1)` is the same idiom
`TimeseriesDateResolver._adjust_forward_capped_at_today` already uses, so business-day semantics
stay consistent across the codebase. Verified by execution:

- Range `2016-01-04 → 2025-12-31` at `annual`: first window dated **2016-01-04** (the calendar
  boundary 2016-01-01 clamped up to the resolved start), subsequent windows 2017-01-02,
  2018-01-01, … 2025-01-01.
- Range `2016-03-15 → 2017-12-29` at `annual`: first window dated **2016-03-15** (clamped),
  second 2017-01-02.

`bdate_range` applies a Mon–Fri calendar with **no public-holiday calendar**, so 2026-01-01 (a
Friday) counts as a business day. That is the existing, deliberate behaviour of
`TimeseriesDateResolver` and `expand_business_days`; reusing the same primitive keeps window
dates consistent with the dates these endpoints already return, and avoids introducing a
holiday calendar as a side effect of this feature.

Because the date depends only on the period and the resolved start — never on the frame's
contents — **window dates are identical across positions**. That is what lets a client overlay a
per-position series on the account-level series, and it is asserted directly by a unit test.

**Alternatives considered**:

- **Unclamped calendar boundary** — rejected by the requester during `/speckit-specify`; would
  emit entry dates outside the response's own stated range.
- **Dropping the partial first window** — rejected by the requester; silently loses data at the
  start of the range and would make a 10-year annual request return 9 entries.
- **Reporting the source (last-observation) date instead of the window start** — contradicts
  FR-006. Not exposed as an extra field either, since the spec's response contract is
  "existing fields + periodicity" and nothing more.

---

## 4. Window counts — verified against the spec's success criteria

**Decision**: No further work needed; the approach reproduces SC-002 and SC-006 exactly.

**Rationale**: A prototype over `bdate_range("2016-01-04", "2025-12-31")` (2,608 business days)
produced **10** annual, **40** quarterly, **120** monthly and **522** weekly windows — matching
SC-002's "exactly 10 / exactly 120" and SC-006's stated reduction figures. These numbers are
reused as unit-test fixtures so the success criteria are checked mechanically.

---

## 5. Validating the parameter while keeping RFC 7807 errors

**Decision**: Declare the query parameter as `str | None` with
`Query(default=None, json_schema_extra={"enum": ["day", "week", "month", "quarter", "annual"]})`,
and validate it in a new `resolve_periodicity()` that raises a new `UnsupportedPeriodicityError`,
handled by a new RFC 7807 handler in `app/main.py` (422, slug `unsupported-periodicity`).

**Rationale**: This is the only option found that satisfies FR-014, FR-017, Constitution V and
FR-016 simultaneously. Verified by generating the OpenAPI document: the `json_schema_extra` enum
**does** surface on the parameter schema (`"enum": ["day","week","month","quarter","annual"]`,
`"required": false`), so the allowed values remain machine-readable at `/openapi.json` (FR-017)
even though the parameter is a plain string. Raising a domain exception then routes the error
through the same `_problem()` helper as the other 14 handlers, so the body is
`application/problem+json` with the supported set named in `detail` (FR-014), and the message
wording mirrors `UnsupportedAttributeError`.

**Alternatives considered**:

- **`Periodicity | None` enum-typed parameter** — rejected. FastAPI would reject bad values itself
  with a `RequestValidationError`, whose default body is **not** RFC 7807 (violating
  Constitution V) and does not name the supported set in the project's error vocabulary.
- **Enum-typed parameter *plus* a global `RequestValidationError` handler** — rejected. It would
  change the error body of **every existing endpoint** in the service, which FR-016 forbids and
  which is far outside this feature's blast radius.
- **Silently falling back to `day` on an unknown value** — rejected explicitly by FR-014; it is
  the exact silent-misinterpretation failure User Story 3 exists to prevent.
- **Case-insensitive / synonym-tolerant matching** (`Annual`, `yearly`, `daily`) — rejected for
  consistency with the case-sensitive account names and attribute names these endpoints already
  use. Recorded in spec.md Assumptions and flagged in the requirements checklist as a
  low-cost, backward-compatible change if it is ever wanted.

---

## 6. Where aggregation hooks into each service

**Decision**: Apply the aggregator immediately **after** derived columns are computed and
immediately **before** entries are constructed. In `TimeSeriesService` that is a single call after
the `pnl` line; in `PositionTimeSeriesService` it is a call inside the existing per-position loop,
after that position's `pnl` line.

**Rationale**: At that point both services hold exactly what the aggregator needs — a
business-day-complete, forward-filled, range-clipped frame with every requested attribute's column
present. Placing it there means no change to validation, date resolution, source-coverage checks
or forward-fill, which is what makes FR-016 and FR-002/FR-003 provable by a straight
response-equality test. Computing `pnl` *before* aggregating is equivalent to computing it after
(it is a row-wise formula, and aggregation selects whole rows), so the cheaper and less invasive
ordering is kept.

For the position endpoint, aggregating inside the loop rather than over a concatenated frame keeps
the diff small and still yields uniform window dates across positions, because the date is
computed from the calendar period and the resolved start only (see §3). Each position also retains
its existing `expand_end` cap (`min(resolved_end, last_date)` when no longer held), so a closed
position's final window correctly reports its last real observation rather than a forward-filled
value beyond its life.

**Alternatives considered**:

- **Aggregating in the API layer after the response is built** — rejected. It would mean
  re-parsing response models, and the service's own structured log line could not report
  `window_count`.
- **Aggregating inside `expand_business_days`** — rejected. That helper is shared with the
  performance and capital paths; widening its contract would violate Single Responsibility and
  risk changing features 003/006/007 behaviour.
- **Concatenating all positions then one grouped aggregation** — viable and equivalent, but a
  larger diff to a working loop for no behavioural gain. Revisit only if the loop is refactored.

---

## 7. Response field shape and backward compatibility

**Decision**: Add `periodicity: Periodicity = Periodicity.DAY` to both response models — always
serialised, defaulted, and **not** in the OpenAPI `required` list.

**Rationale**: FR-011 wants the applied value on every response (including the defaulted `day`, so
a client never has to infer which rule ran); FR-012 wants strict additivity. A defaulted Pydantic
field gives both: existing fields keep their names, order and values, the new key is appended, and
because the field carries a default it is advertised as optional in the schema — the "optional
field, backward compatible" the spec asks for. Typing it as the `str`-based enum (rather than a
bare `str`) means `model_dump(mode="json")` still emits `"day"` / `"month"`, so the wire format is
a plain string, while `mypy --strict` prevents an invalid value being constructed internally.

**Alternatives considered**:

- **Omitting the field when periodicity is `day`** — rejected. A conditionally present field is
  harder for clients to consume than an always-present one, and no client can be broken by an
  added key that was absent before.
- **A nested object** (`{"periodicity": {"value": "month", "aligned_to": "calendar"}}`) — rejected
  as unnecessary structure for a single scalar.
- **A response header instead of a body field** — rejected; the spec calls for a payload field,
  and headers are lost when a body is cached or logged.
