# Research: Periodicity Control for the Projection Page

No `NEEDS CLARIFICATION` items remained after the spec; the decisions below fix the wiring.

## 1. Reuse the shared control with `page_prefix="projection"`

- **Decision**: Call `build_periodicity_control("projection", config)` from the Projection
  parameters bar; use the ids the helpers already generate.
- **Rationale**: The 021 builder is page-prefix generic and its docstring explains why ids must be
  page-scoped (Dash collapses `allow_duplicate` callbacks that share Inputs). Guarantees identical
  UI, options and order (FR-001, FR-002, SC-005) with zero component change.
- **Alternatives**: A dropdown (rejected — `n_clicks` is what distinguishes explicit from derived);
  a new Projection-specific control (rejected — duplicates code and config).

## 2. Store-driven interval; chart reads the store; target becomes a `State`

- **Decision**: Add `projection-periodicity-store` (`{value, explicit}`). A derive callback fires on
  target-store, account and accounts-store changes and always writes the store (derived when not
  explicit, unchanged when explicit). `_render_chart` takes the store as an Input and the target as
  a `State`.
- **Rationale**: Overview lets the chart fire both from the date change and from the store update,
  which can produce a fetch at a stale interval before the correct one. Projection fetches a
  potentially 20-year series, so the extra fetch matters and could also be overwritten out of
  order. Routing every target change through the store gives one fetch, at the final interval
  (FR-007, FR-008, SC-003).
- **Alternatives**: Mirror Overview exactly (rejected: stale intermediate fetch); compute the
  interval inside the chart callback from store + target (rejected: the control would not reflect a
  derived value, violating FR-008).

## 3. Derivation span stays earliest record → target

- **Decision**: Keep `_derive_projection_periodicity`'s span, returning the option key so the store
  can hold the service-side value via `value_for_key`.
- **Rationale**: That is the span the page already plots, so defaults stay identical to today
  (FR-010, SC-002) while using the same thresholds as Overview/Positions (FR-005).
- **Alternatives**: Span from the Start Date (rejected — would change today's default charts and
  understate what is plotted).

## 4. Explicit choice survives account switches

- **Decision**: The account-switch reset callback continues to clear only the target and return
  toggles; the store is untouched, so `explicit` persists. Derivation with no explicit choice
  re-runs when a new target is picked.
- **Rationale**: FR-009 / SC-004; identical to Overview.

## 5. Disabled while refreshing

- **Decision**: Add `running=[(Output(button_id, "disabled"), True, False) ...]` for the five
  buttons on `_render_chart`.
- **Rationale**: FR-011; same mechanism as Overview.

## 6. Backend

- **Decision**: No change. `PortfolioAnalysisClient.get_projection` already accepts `periodicity`,
  and the service's in-progress projection endpoint takes the same wire values as the other
  endpoints. This feature depends on that endpoint being available for live use; BDD tests use the
  existing fake client.
