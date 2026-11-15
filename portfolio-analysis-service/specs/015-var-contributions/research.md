# Research: VaR Contributions (Marginal Risk) Endpoint

## 1. Decision: Extract the scenario matrix out of `estimate()` into a reusable builder

**Decision**: Factor the matrix-building block currently inline in
`app/services/var/engine.py::estimate()` (lines building `values`, `returns`, `source_observed`,
`provenance`, the rescale pass, and `included`) into a new pure function, e.g.
`build_scenario_matrix(exposure, panel, as_of_row, lookback_days, settings, proxy_configs) ->
ScenarioMatrix`, where `ScenarioMatrix` holds the per-scenario-row, per-position effective returns
matrix, the position values vector, the included-row mask, the per-cell provenance codes
(`_ACTUAL`/`_PROXY`/`_RESCALED`), and the identifiers in column order (data-model.md). `estimate()`
calls this builder and then does exactly what it does today (aggregate via `scenario_pnl()`, call
`var_es()`). The new contributions math gets the same matrix and never re-derives it — including the
provenance codes contributions needs to compute each group's own `actual_mv_pct`/`proxied_mv_pct`/
`rescaled_mv_pct` (FR-002), which the existing per-run `instruments.csv` cannot supply on its own
(it stores one categorical "worst treatment" label per identifier per look-back, not a percentage).

**Rationale**: `estimate()` already computes everything the decomposition needs — it just throws the
per-position detail away after producing the aggregate `scenario_pnls` vector. Duplicating the
proxy/rescale/sparse logic in a second place would violate SOLID (two places that must agree on what
"effective return" means) and risks the two code paths silently diverging. Extracting a builder keeps
a single source of truth and is a pure refactor with no behavioural change to the existing `estimate()`
callers or its 012 test suite.

**Alternatives considered**:
- *Recompute independently in the new module*: rejected — duplicates proxy/rescale/sparse logic,
  the most intricate and already-tested part of the engine.
- *Have `estimate()` always return the full matrix*: rejected — every existing caller (feature 012's
  run loop, over thousands of dates x 3 lookbacks) would carry a matrix it never uses, needlessly
  increasing memory pressure for a pure refactor that doesn't need it.

## 2. Decision: Persist the scenario-returns snapshot as an accumulating per-account store

**Decision**: Add two new wide-format CSVs under the existing `data/{account}/var/` directory,
written by `VarRunService` as part of the same atomic commit it already does for
estimates/outcomes/instruments:

- `var/scenario_returns.csv` — one row per grid business date, one column per identifier, holding the
  *effective* simple return (post rescale is **not** baked in here — this stores the raw aligned
  return exactly as `ReturnPanel.returns` holds it, before proxy/rescale substitution, so it reflects
  observed market data only).
- `var/scenario_observed.csv` — same shape, boolean (0/1) `ReturnPanel.observed` mask.
- `var/scenario_returns_meta.json` — `{identifier: first_observed_date}` dict (mirrors
  `ReturnPanel.first_observed`), plus `updated_at`.

New columns and rows are **upserted**, not wholesale-replaced: `VarRepository` gains
`commit_scenario_returns(account_name, panel: ReturnPanel)` that outer-joins the incoming panel's
grid dates and identifiers onto whatever is already stored, with the incoming run's values winning on
overlap (same "latest run wins" semantics `_upsert_by_date` already uses for estimates/outcomes).

**Rationale**: A "missing" mode run (the common case after the first full run) only fetches a narrow
date window around its *new* dates — it does not refetch the multi-year lookback window behind
*already-computed* older dates. If the snapshot were replaced wholesale each run (as `instruments.csv`
is today), a series of small incremental runs would progressively shrink the persisted snapshot's
real coverage to just the latest run's narrow fetch window, breaking contributions for every older
date that still has a perfectly good stored VaR estimate. Upserting guarantees that once a (date,
identifier) cell has ever been fetched, it stays available, so a contributions request for any date
that already has an estimate also has the returns data that estimate was built from (or a superseding,
re-fetched value for the same cell — consistent with how a stale re-fetch already supersedes an old
estimate via `row_fingerprint`).

Storing the *raw* (pre-proxy/rescale) return, rather than each position's post-substitution effective
return, is deliberate: proxy configuration and the sparse/`always` decision are look-back-dependent
(the "sparse" check in `_position_returns_and_provenance` looks at density over the *specific* window),
so a single persisted number per (date, identifier) cannot represent every look-back's substitution
choice. Storing the raw panel and re-running the (cheap, pure, no-I/O) proxy/rescale logic at
contributions-request time for the requested look-back keeps one source of truth and avoids a
combinatorial (date x identifier x lookback) store.

**Alternatives considered**:
- *Replace wholesale each run* (matching `instruments.csv`): rejected for the coverage-shrinkage
  reason above.
- *Store per-(date, lookback) PnL matrices*: rejected — this is what proxy/rescale depends on the
  specific look-back for, but storing a full scenario x position matrix per as-of-date per look-back is
  a combinatorial blow-up (thousands of dates x 3 look-backs x up to ~1,300 scenario rows x ~60
  positions) for no benefit over storing the much smaller shared raw panel and recomputing the
  substitution on read, which is exactly what the run-time engine already does per request.
- *Parquet instead of CSV*: rejected, consistent with the existing store's own choice (`var_repository.py`
  docstring: "no new dependency, human-readable") and the original proposal's open-question answer.

## 3. Decision: Reuse `InvalidVarQueryError` / problem type `invalid-var-query` for `group_by`, not a new type

**Decision**: An invalid `group_by` value raises the existing `InvalidVarQueryError` (with
`fields=["group_by"]`), handled by the existing `invalid_var_query_handler` in `app/main.py`, which
already produces problem type `invalid-var-query` — the same type already used for invalid `lookback`,
`confidence`, `pnl_basis` and `min_quality` values on the series/backtest endpoints. No new exception
class or problem type is introduced.

**Rationale**: The feature description (and the original proposal, §7) suggested separate
`invalid-var-lookback` / `invalid-confidence-level` problem types, but feature 013's actual
implementation consolidated all of the read-side query-validation errors for this endpoint group into
one `InvalidVarQueryError` / `invalid-var-query` type, discriminated by the `fields` list in the
problem body — there is no `invalid-var-lookback` or `invalid-confidence-level` type anywhere in the
current codebase (confirmed in `app/exceptions.py` and `app/main.py`). Introducing a brand-new,
differently-named type for `group_by` alone, alongside a type that was never actually built for
`lookback`/`confidence`, would be inconsistent with the one precedent that does exist. This is a
correction of the spec's literal wording, not a behavioural change: spec FR-011–FR-013's
*observable* requirement — a structured, field-specific 422 for each bad parameter — is fully met;
only the internal type-name assumption is corrected.

**Alternatives considered**:
- *Introduce `invalid-group-by` as a new, distinct type*: rejected — would leave `group_by` validation
  inconsistent with how `lookback`/`confidence`/`pnl_basis`/`min_quality` are already validated on the
  neighbouring series/backtest endpoints in the same router file.

## 4. Decision: Add an optional `theme` field to `IdentifierMappingEntry`

**Decision**: Add `theme: str | None = Field(default=None, ...)` to
`app/models/market_data.py::IdentifierMappingEntry`, loaded the same way `var_proxy`/`var_proxy_mode`/
`var_proxy_scale` already are. A position whose entry has no `theme` (or whose sub-account has no
mapping entry at all) is grouped under a reserved `"Unclassified"` theme when `group_by=theme`.

**Rationale**: The spec's Assumptions section guessed that theme grouping would reuse "the existing
`theme` field already present in the identifier/static mapping file (as used elsewhere in the
system)" — but inspection of `IdentifierMappingRepository` / `IdentifierMappingEntry` shows this
service's own mapping file has no such field at all. `theme` only exists in the **separate**, legacy
root-level `InvestmentDataStatic.json` consumed by the standalone `PortfolioAnalysis.py` script
(outside this service, per the top-level `CLAUDE.md`) — a different file, a different model, not read
by this service. Rather than reopen scope with the user over a field name, the proven, minimal-risk
path already used twice for this exact mapping file (`var_proxy*` in feature 012) is to add one more
optional, additive field. This keeps the feature's user-visible behaviour exactly as specified
(`group_by=theme` groups positions by theme) while being honest that the data has to be entered once
into this service's own mapping file (manually, via the existing JSON) before any theme group other
than `"Unclassified"` appears — which is no different from how `var_proxy` entries were populated.

**Alternatives considered**:
- *Read the legacy root `InvestmentDataStatic.json` directly*: rejected — that file is keyed by
  `Position Name` string matching against the legacy script's own Excel reading (per the root
  `CLAUDE.md`), a different identity scheme than this service's sub-account-name-keyed mapping file;
  cross-referencing two independently-maintained static files is more fragile than maintaining one
  additive field in the file this service already owns and already extended once before.
- *Defer `group_by=theme` entirely to a later feature*: rejected — the user's confirmed scope
  explicitly includes `group_by=position|theme` as core to this feature; dropping it would be a scope
  cut the planning phase should not make unilaterally.

## 5. Decision: `group_by=position` keys by ladder sub-account, not by identifier

**Decision**: A "position" group is one `PositionExposure` (keyed by `sub_account`), the same
granularity `build_exposures()` already produces — not collapsed by `identifier` even when two
sub-accounts share one identifier (e.g. two Aegon Ethical Equity holdings in the evidence table,
proposal Appendix A).

**Rationale**: This matches an explicit, already-made product decision recorded in the proposal
(§3.3): "Two sub-accounts that map to the same identifier... share one return series but stay
separate positions (needed later for decomposition)." This feature *is* that later decomposition, so
honouring that decision is not a new choice — it is executing on one already on record.

## 6. Decision: Component ES is computed from the full portfolio's tail-scenario set, applied per group

**Decision**: `contributions.py` exposes a function that, given the full-portfolio loss vector and a
confidence level, determines the (possibly fractional, Acerbi-Tasche) tail weighting already computed
by `var_es()` for the aggregate ES, and a second function that applies that *same* per-scenario-row
weighting to any single group's PnL column to get that group's Component ES. Because the weighting is
shared and the groups partition the full position set exactly, the Component ES values sum exactly to
the portfolio's total ES (mathematical identity, not an approximation) — SC-001's 0.5% tolerance
exists only to absorb floating-point summation order, not any approximation in the method itself.

**Rationale**: This is exactly the method the proposal recommends (§8, "Component ES_i... Sums
**exactly** to ES and is far more stable" — chosen over Component VaR, which is "noisy with a single
scenario"). Reusing `var_es()`'s existing `Fraction`-based exact tail-weight computation (rather than
re-deriving it) keeps one source of truth for the Acerbi-Tasche split between the aggregate and the
per-group calculation.

## 7. Decision: Standalone and Incremental VaR recompute `var_es()` on reduced loss vectors

**Decision**: Standalone VaR for a group calls the existing `var_es()` on `-group_pnl_column` alone
(same confidence level, same included-scenario rows as the portfolio). Incremental VaR calls
`var_es()` twice: once on the full portfolio's losses (reusing the vector already computed), once on
the portfolio's losses with that group's column subtracted out, and reports the difference.

**Rationale**: Both are exact "with vs without" comparisons per the proposal's §8 table, and both are
single extra calls to the one already-tested quantile/ES function — no new statistical method is
introduced, keeping the Constitution's Type Safety/Quality bar (one well-tested numeric core) intact.

## 8. Resolved: no new third-party dependency

numpy, pandas and the existing `fractions.Fraction`-based exact arithmetic in `engine.py` cover every
new computation (matrix column sums/subtraction, quantile selection, tail averaging). No clarification
markers remain from Phase 0; proceeding to Phase 1 design.
