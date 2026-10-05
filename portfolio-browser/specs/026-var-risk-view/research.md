# Research: Value at Risk View (Risk Page)

## 1. Satisfying "instant, no new request" when `pnl_basis`/`min_quality` are server parameters

**Decision**: On every account/date/look-back refetch, call `GET .../risk/var/backtest` **four
times** — once for each combination of `pnl_basis` (`hypothetical`/`ladder`) × `min_quality`
(`ok`/`degraded`) — and store all four results. The "instant" PnL-basis and hide-degraded-dates
toggles then simply select which of the four already-fetched results to display; the render
callback performs no I/O. `confidence` is never passed to either the series or backtest call
(always omitted), since 013's own endpoints already default an omitted `confidence` to every
configured level in one response — so the confidence-level multi-select needs no analogous
multiplication, and `GET .../risk/var` (series) is called only once per refetch.

**Rationale**: `pnl_basis` and `min_quality` are not display formatting — they change which dates
count as exceedances and therefore the *computed* Kupiec, Christoffersen, conditional-coverage,
traffic-light-zone and stability figures (see
`portfolio-analysis-service/specs/013-var-series-backtest-api/research.md` §6, §8). Constitution
Principle I ("UI MUST NOT ... re-implement financial calculations client-side ... MUST NOT derive
new financial facts") forbids approximating a Kupiec likelihood ratio or a traffic-light zone in
the browser from the other three combinations' data. Pre-fetching the bounded 2×2 = 4 combinations
up front is the only way to satisfy both FR-010 (no new request on toggle) and FR-012 (the panel's
figures must reflect the hide-degraded state) without that approximation.

**Alternatives considered**:
- *Refetch backtest on every PnL-basis/min-quality toggle*: rejected — explicitly contradicts
  FR-010/FR-012's "without a new request."
- *Approximate the other combination client-side* (e.g. recompute Kupiec from the already-fetched
  exception flags): rejected — a real and easy-to-get-subtly-wrong reimplementation of a
  financial calculation (Principle I), and 013's own statistics (Christoffersen's chain-break
  rule, the stability measure's holdings-change exclusion) are not simple functions of the data
  this view already has in a form the browser could safely recompute from.
- *Only pre-fetch the 2 PnL-basis states, and refetch on the hide-degraded toggle*: rejected as an
  unjustified exception — FR-012 is as "instant" a requirement as FR-010, and the extra 2 calls
  are a bounded, known cost handled by the same concurrency approach as the other two.

## 2. When to fetch `GET /v1/risk/var/methods`

**Decision**: Once per page mount, via the existing `risk-mount-trigger` `dcc.Interval` pattern
(the same one `_fetch_accounts` already uses), independent of the selected account. Its result
(available look-backs and confidence levels) populates the VaR tab's controls and is stored in a
new `risk-var-methods-store`.

**Rationale**: The methods endpoint "requires no account and always succeeds" (013's own FR-022);
its answer is deployment configuration, not account data, so re-fetching it per account/date
change would be both wasteful and semantically wrong (it never varies by account). This mirrors
how `risk-accounts-store` is populated once per mount rather than once per render.

## 3. Linking the main chart and the market-value chart

**Decision**: One Plotly figure built via `plotly.subplots.make_subplots(rows=2, cols=1,
shared_xaxes=True, row_heights=[0.7, 0.3])`, with the PnL/VaR traces on row 1 and the market-value/
proxied-share traces on row 2, returned as a single `dcc.Graph`.

**Rationale**: `shared_xaxes=True` gives synchronized zoom/pan between the two panels for free,
with no custom callback wiring to keep two separate `dcc.Graph`s' x-ranges in sync — satisfying
FR-008's "visually linked ... so changes in portfolio construction can be related to changes in
the risk picture above it" using Plotly's own built-in mechanism (Constitution Principle V:
prefer the standard library's own solution over a bespoke one).

**Alternatives considered**: Two separate `dcc.Graph`s with a `relayoutData` callback to copy one's
x-range onto the other — rejected as unnecessary custom synchronization code for something
Plotly's subplot support already does natively.

## 4. "Hide degraded-quality dates" and the backtest panel

**Decision**: The toggle has two effects, both presentational selections over already-fetched
data: (a) the chart's render function filters the already-fetched series list to drop entries
with `quality == "degraded"` before plotting; (b) the backtest panel switches which of the four
pre-fetched backtest results (research.md #1) it displays — the one whose `min_quality` matches
the toggle's state (`ok` when on, `degraded` when off, matching 013's own default).

**Rationale**: Filtering a list of already-fetched dicts by a field already present in each entry
is a presentational operation, not a calculation (Principle I); the panel's actual statistics
still come untouched from the server response computed with that exact `min_quality`.

## 5. Formatting confidence levels: basis points in, percentages in the UI

**Decision**: `VarMethodsResponse.confidence_levels_bp` (e.g. `[9500, 9750, 9900]`) is converted to
display labels once, in `_var_controls.py`, via `f"{bp / 100:g}%"` (giving `"95%"`, `"97.5%"`,
`"99%"`) — the same `:g` formatting 013's own router uses server-side for its error messages. The
multi-select's option *values* stay as the integer basis points (so round-tripping through the
confidence query parameter, when needed for the series/backtest calls that do pass it — see
research.md #1's note that confidence is *never* passed — remains exact); only the *labels* are
percentage strings.

**Rationale**: Basis-point integers avoid float-equality bugs when matching a selected level
against a `ConfidenceLevelEstimate.confidence_bp` from the fetched series/backtest payloads;
percentages are what the spec's own language and every other part of this UI's vocabulary uses.

## 6. Concurrency for the 6-call refetch

**Decision**: Issue the 1 series + 4 backtest + 1 status calls concurrently from the fetch
callback using a bounded thread pool (`concurrent.futures.ThreadPoolExecutor`, stdlib — no new
dependency), not sequentially.

**Rationale**: `httpx.Client`'s synchronous calls block; running six of them sequentially could
approach 12s in the worst case (013's own 2s-per-call SC-004 budget), which would make the
refetch's loading state feel broken even though it technically still "appears within 100ms" per
the UX standard (that standard is about *feedback*, not total completion time, but a multi-second
wait undermines the view's usability). A stdlib thread pool is the simplest fix with no new
dependency (Principle V).
