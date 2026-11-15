# Data Model: VaR Contributions (Marginal Risk) Endpoint

## New/changed persisted entities

### ScenarioReturnsSnapshot (new, per account)

Extends `data/{account}/var/` (feature 012's `VarRepository` layout) with:

| File | Shape | Content |
|---|---|---|
| `scenario_returns.csv` | rows = grid business dates (ascending), columns = `date` + one per known identifier | Raw aligned simple return for that identifier on that date (`ReturnPanel.returns`); blank/NaN where unknown. |
| `scenario_observed.csv` | same shape as above | `1`/`0`/blank mirroring `ReturnPanel.observed` — whether the cell is a genuine market observation vs. a zero-filled in-history gap day or unknown cell. |
| `scenario_returns_meta.json` | `{"identifiers": {<identifier>: {"first_observed_date": "YYYY-MM-DD" \| null}}, "updated_at": "..."}` | Mirrors `ReturnPanel.first_observed`; `updated_at` is the last commit's timestamp. |

**Identity**: one snapshot per account (not per look-back — see research.md §2).

**Lifecycle**: Created on an account's first successful VaR run. Every subsequent successful run
upserts (outer-joins) its own run's `ReturnPanel` into the stored snapshot: new dates/identifiers are
added, and any (date, identifier) cell already covered by this run's fetch window is overwritten with
the freshly fetched value (latest fetch wins, consistent with how a stale re-fetch already supersedes
an old estimate via `row_fingerprint`). Never wholesale-replaced. Never deleted independently of the
account's whole `data/{account}/` directory being wiped (same lifecycle as the rest of the VaR store).

**Validation rules**: Column identifiers are the same identifier strings already used elsewhere in
the VaR store (`estimates.csv`'s position identifiers and proxy identifiers); no new identifier
namespace. A row/column with no data anywhere is simply absent, not a stored null row — same
sparsity-by-omission convention `instruments.csv` already uses for optional columns.

### IdentifierMappingEntry.theme (new field, additive)

`app/models/market_data.py::IdentifierMappingEntry` gains:

```python
theme: str | None = Field(
    default=None,
    description="Free-text grouping label for risk/contribution reporting (e.g. 'Global Equity')",
)
```

No migration needed — existing mapping files without this key continue to validate (Pydantic default
`None`), and every existing entry in production mapping files is unaffected. A position with no theme
(because its sub-account is unmapped, or its entry has no `theme`) is grouped under the reserved
`"Unclassified"` theme at request time — this label is never stored, it is applied in the
`VarContributionsService`/`contributions.py` grouping step.

## In-memory / computation-only entities (no persistence)

### ScenarioMatrix (new, in `app/services/var/engine.py`)

```python
@dataclass(frozen=True)
class ScenarioMatrix:
    identifiers: tuple[str, ...]     # column order, matches `values`
    values: np.ndarray               # length-m GBP market values
    effective_returns: np.ndarray    # window_len x m, after proxy/rescale substitution
    included: np.ndarray             # length-window_len bool, the holiday-scenario mask
    provenance: np.ndarray           # window_len x m int, the _ACTUAL/_PROXY/_RESCALED codes
                                      #   `estimate()` already computes internally
```

Produced by the new `build_scenario_matrix(...)` builder extracted from `estimate()` (research.md
§1). `estimate()` now calls this builder, then does exactly what it already does
(`scenario_pnl(effective_returns[included], values)`, then `var_es()` per confidence level).
`provenance` is carried through specifically so a contributions request can derive each **group's**
`actual_mv_pct`/`proxied_mv_pct`/`rescaled_mv_pct` (FR-002) the same way the engine already derives
the account-wide figures: for `group_by=position`, from that one column's own per-scenario-day codes
(market-value-weighted across the group's constituent columns for `group_by=theme`) restricted to
`included` rows — not from `instruments.csv`'s single stored "worst treatment" label, which is too
coarse (one categorical value per identifier per look-back, not a percentage). Note this mirrors
the existing account-wide convention exactly: a *single* position's own worst-treatment is itself
binary (0% or 100%, the same as `EstimateResult.position_treatments`), so a genuinely mixed
percentage only appears for a group spanning several positions with different treatments — in
practice, this means `group_by=position` percentages are always 0/100, and only `group_by=theme`
groups (or Cash, always 100/0/0) can show a blended percentage.

### ContributionGroupEntry (new, in `app/services/var/contributions.py` and the API response model)

One row of the contributions response — a position (ladder sub-account) or a theme, for one
account/date/lookback/confidence request.

| Field | Type | Meaning |
|---|---|---|
| `key` | `str` | Sub-account name (`group_by=position`) or theme label, `"Cash"` for the synthetic cash group (FR-018), or `"Unclassified"` (theme grouping only). |
| `identifier` | `str \| None` | The market-data identifier, when `group_by=position` and the group is a single priced position; `None` for `group_by=theme` (a theme can span multiple identifiers) and for the Cash group. |
| `market_value_gbp` | `float` | GBP market value of the group on the requested date. |
| `weight_pct` | `float` | `market_value_gbp / total_value_gbp * 100`, where `total_value_gbp` includes Cash. |
| `standalone_var_gbp` | `float` | Quantile of the group's own PnL column alone (FR-004). |
| `incremental_var_gbp` | `float` | Portfolio VaR minus portfolio-VaR-without-this-group (FR-005). |
| `component_es_gbp` | `float` | Group's share of the full-portfolio tail-weighted ES (FR-002, research.md §6); sums exactly to total ES across all groups. |
| `marginal_var_gbp_per_gbp` | `float` | `component_es_gbp / market_value_gbp` — risk per £ of exposure (FR-006); `0.0` when `market_value_gbp` is `0` (should not occur post FR-014/FR-018, but guarded). |
| `actual_mv_pct`, `proxied_mv_pct`, `rescaled_mv_pct` | `float` | Coverage/quality shares, reusing the same per-position provenance the underlying VaR run already computed (FR-002); for Cash these are always `100.0`/`0.0`/`0.0`. |

All four risk measures are `0.0` (not `None`) for the Cash group (FR-018) — Cash is never a
`NEEDS CLARIFICATION`-style "unknown", it is a defined zero by construction.

## API response model (Pydantic, `app/models/var_series.py`)

```python
class ContributionGroupEntry(BaseModel):
    key: str
    identifier: str | None
    market_value_gbp: float
    weight_pct: float
    standalone_var_gbp: float
    incremental_var_gbp: float
    component_es_gbp: float
    marginal_var_gbp_per_gbp: float
    actual_mv_pct: float
    proxied_mv_pct: float
    rescaled_mv_pct: float


class VarContributionsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    date: dt.date | None                 # None when nothing is computed for this request (FR-009)
    outcome_date: dt.date | None
    lookback_code: str
    lookback_days: int
    confidence_bp: int
    group_by: Literal["position", "theme"]
    total_value_gbp: float | None
    quality: Quality | None              # "ok" / "degraded" / "insufficient" / None (not computed)
    quality_reason: str | None
    groups: list[ContributionGroupEntry] = Field(default_factory=list)
    links: dict[str, str] = Field(alias="_links")
```

- **Not computed** (FR-009): `date`/`quality`/`total_value_gbp` are `None`, `groups` is `[]`, and
  `_links` includes `status` and `runs` alongside `self` — exactly mirroring `VarSeriesResponse`'s
  empty-series shape.
- **Insufficient quality** (FR-010): `quality` is `"insufficient"`, `groups` is `[]`, `total_value_gbp`
  is still populated (it is known even when the estimate itself is insufficient), `quality_reason`
  carries the stored reason.
- **Computed, sufficient or degraded quality**: `groups` has one entry per position or theme
  (including Cash), per FR-002/FR-015/FR-018.

## Relationships

```text
VarRun (012)  --writes-->  estimates.csv, outcomes.csv, instruments.csv (existing)
              --writes-->  scenario_returns.csv, scenario_observed.csv, scenario_returns_meta.json (NEW)

VarContributionsService (NEW)
  reads  estimates.csv          -- quality/date lookup (FR-009/FR-010 gating)
  reads  scenario_returns*.csv  -- rebuild ReturnPanel for the requested lookback window
  reads  LadderRepository       -- rebuild Exposure for the requested date (local, no market-data call)
  reads  IdentifierMappingRepository -- theme lookup for group_by=theme
  calls  build_scenario_matrix() + contributions.py functions (pure, in-process)
```
