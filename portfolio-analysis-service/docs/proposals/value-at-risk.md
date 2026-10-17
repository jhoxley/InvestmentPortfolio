# Proposal: Historical-Simulation Value at Risk (VaR) Suite

| | |
|---|---|
| **Status** | Draft for review |
| **Date** | 2026-10-03 |
| **Projects affected** | `market-data-web-service` (prerequisite), `portfolio-analysis-service` (calculation, store, API), `portfolio-browser` (UI), `run_end_to_end.ps1` |
| **How to use this document** | Review §3–§5 (methodology, backtesting, execution). Once agreed, each feature in §11 is one `/speckit-specify` run (paste-ready inputs are provided). §3–§8 then become source material for `research.md` / `data-model.md` during `/speckit-plan`. |

---

## 0. Summary of recommendations

| Question | Recommendation |
|---|---|
| **Method** | 1-day **historical simulation**: apply each historical day's instrument returns to *today's* GBP holdings to build a hypothetical PnL vector, then read VaR (and Expected Shortfall) off the loss tail at 95%, 97.5% and 99%. |
| **Returns, moving averages or monetary PnL?** | **Simple 1-day returns per instrument as the scenario input, monetary GBP PnL as the output** (returns × today's market value). Never moving-average returns: they shrink 1-day VaR by roughly √k (§3.6). The portfolio's *actual* historical PnL is the right series for **backtesting**, not for building scenarios. |
| **Look-back** | Compute **1Y (260), 2Y (520) and 5Y (1,300) business days** for every date. All three come from the same scenario vector, so this costs almost nothing extra. Make **2Y the headline**: it gives at least 5 tail scenarios at 99%; real price history covers every current holding except Lindsell Train D Acc and the two sparse local-file instruments (about 5% of market value in each account); and it can be backtested over the ladder's full history from 2016. Let the backtest confirm or overturn that choice (§3.7, §4.7). |
| **Short histories** | Use real price history where it exists, then a **configured proxy** (per instrument, in `InvestmentDataStatic.json`), then a rescale fallback. Every VaR row records the share of market value that is actual / proxied / rescaled, plus a quality flag. *(Decided.)* |
| **Market-data prerequisite** | Add an **observed-only price history option** to market-data-web-service, and have it remember each instrument's first available date. Without this, back-filled flat prices quietly understate VaR. *(Decided.)* |
| **Backtesting** | Compare VaR(t) with the **hypothetical PnL** of the holdings frozen at the close of day t and revalued at t+1. This isolates the model from trading and cash flows, which deals with changing portfolio construction. Run Kupiec POF, Christoffersen independence / conditional coverage and Basel traffic-light tests over the full history and over rolling 250-day windows. |
| **Execution** | The maths is cheap: **0.58 s for about 10 years of dates × 50 instruments × 3 look-backs × 3 confidence levels**. The cost is in data: reading the SIPP ladder `.xlsx` takes about 7 s, and the first yfinance fetch of extended history is slow. So: **precompute into a per-account store, one row per business date** (upserted, with fingerprints). Trigger it through an **asynchronous run resource** (`POST …/risk/var/runs`); the service, not a script, works out which dates are missing or stale. Scripts are thin triggers: a new `run_end_to_end.ps1` phase plus a small `refresh-var.ps1`. |
| **API** | Fast `GET` endpoints read the store: the VaR time series, the backtest, status/coverage metadata, and method metadata. Run endpoints sit alongside them. |
| **UI** | A "Value at Risk" view on the Risk page. Daily PnL bars with −VaR lines (lagged one day, so each forecast lines up with its outcome), exceptions highlighted, a coverage/market-value strip underneath, and a backtest summary panel. |
| **Incremental VaR later** | The engine is built around a scenario × position PnL matrix for any set of holdings. Subset, incremental, component (Euler/ES) and combined-account VaR are then just different holdings vectors fed through the same functions. *(Per-account now, combined later — decided.)* |

---

## 1. Decisions taken

| # | Decision | Implication |
|---|---|---|
| D1 | Short-history instruments use a **configured proxy** as the primary treatment | `InvestmentDataStatic.json` entries gain optional `var_proxy` / `var_proxy_mode`. Rescale is the documented fallback when no proxy is set. |
| D2 | **Extend market-data-web-service** with observed-only history | Prerequisite feature `009-observed-price-history` (§11-A) must ship first. |
| D3 | **Per-account VaR now; combined/subset later** | The store is keyed by account. The engine takes arbitrary holdings, so combined and Incremental VaR need no redesign. |
| D4 | **Scottish Widows Pension** (a balanced mixed-asset pension fund, priced about monthly) is proxied by **BlackRock Consensus 85** (`GB00B08HD927`), mode `always`, scale 1.0 | Evidence in Appendix B. Adds an optional static `var_proxy_scale` field so the 1:1 assumption can be changed without a code change. |

---

## 2. Evidence gathered

### 2.1 Current data available to the service

* Each account's position ladder (`data/{account}/ladder.xlsx`) holds, per business day and sub-account: `quantity`, `price` (GBP, from market-data), `market_value`, `portfolio_weight` (total includes Cash), `position_return` and `weighted_position_return` (computed on the start-of-day weight).
* HL-SIPP: 47 sub-accounts, 2016-04-20 → 2026-09-23, currently 42 held (median 20 over history). HL-ISA: 15 sub-accounts, 2018-07-12 → 2026-09-23, currently 10 held.
* Re-ingesting the same ledger (checksum match) **re-prices** the existing dates but does **not** extend the date range. New dates only arrive with a fresh ledger ingest.

### 2.2 Price history really available (not just what is cached)

The market-data cache only holds prices for the periods each fund was **actually held**, so it under-represents what exists. A direct read-only yfinance probe of the 47 currently held instruments (full table in Appendix A) shows:

| Look-back | Instruments **without** enough real history today | Share of account market value |
|---|---|---|
| 1Y (260 bd) | Scottish Widows Pension, WisdomTree Battery Metals (both sparse local files) | SIPP 4.5%, ISA 0% |
| 2Y (520 bd) | The two above + Lindsell Train Global Equity D **Acc** (1.2y) | SIPP 4.5%, ISA 5.4% |
| 5Y (1,300 bd) | The above + Ark Genomic, Pictet Clean Energy I Acc EUR, Schroder ISF Global Climate Change, Vanguard ActiveLife, iShares Lithium, iShares Pacific ex Japan S | SIPP ≈16.6%, ISA 5.4% |

Most Morningstar-ID funds report history from exactly **2014-01-02** on yfinance. That looks like a data-floor date rather than the funds' inception, but in practice it means a 2Y window is available from about 2016, the start of the SIPP ladder.

### 2.3 Compute cost benchmark

Synthetic, fat-tailed data shaped like the real problem: 4,000 business days, 50 instruments, holdings changing daily. A numpy loop computing 3 look-backs × 3 confidence levels for **2,700 as-of dates took 0.58 s**. By comparison, reading the HL-SIPP `ladder.xlsx` takes **about 7 s**, and the first-time fetch of pre-holding history from yfinance is network-bound (minutes, first run only).

**Conclusion:** the VaR maths is not the bottleneck. Data acquisition is, and so is the latency of recomputing on every request. That drives the execution model in §5.

### 2.4 Data hazards found (these shape the methodology)

| Hazard | Where | Effect on VaR |
|---|---|---|
| **Silent back-fill / forward-fill** (spec `006-price-series-fill`, with no fill indicator by design) | market-data history endpoint | Asking 5Y of history for a fund with 1Y of real data returns 4Y of flat prices, i.e. zero returns, i.e. **VaR understated**. → D2. |
| **Re-fetch of non-existent history** | `CachedPricingProvider`: if the prepend segment returns no data, `cached_min` never moves, so the same yfinance call is attempted on *every* request | Slow runs, and load on yfinance. → Part of D2 (remember the inception date). |
| **Sparse local price files** | Scottish Widows Pension (8 prices), WisdomTree Battery Metals (37) | Daily returns are mostly 0 with occasional jumps, so the risk is understated. → proxy mode `always`. |
| **Adjusted-close restatement** | yfinance `Ticker.history()` defaults to `auto_adjust=True`. Cached rows are not re-adjusted when a later dividend restates history. | A spurious "return" can appear at the seam between old and new cache rows and land in the tail. → Outlier guard (§3.9) and a risk entry (§10). |

---

## 3. Methodology

### 3.1 Notation

| Symbol | Meaning |
|---|---|
| $t$ | As-of date (a ladder business day). VaR(t) forecasts the loss from close $t$ to close $t+1$. |
| $H_t$ | Positions held at the close of $t$ (quantity > 0, ladder closure rule applies), mapped to identifiers. |
| $V_{i,t}$ | GBP market value of position $i$ at $t$ (ladder `market_value`). $V_t = \sum_i V_{i,t}$ **including Cash**. |
| $P_i(s)$ | GBP price of instrument $i$ on day $s$, **observed points only** (market-data `fill=none`). |
| $r_i(s)$ | Simple 1-day return of $i$ on scenario day $s$. |
| $W_L(t)$ | Scenario window: the $L$ Mon–Fri business days ending at $t$ inclusive, $L \in \{260, 520, 1300\}$ (the same 260-days-per-year convention as the performance endpoints). |
| $p$ | Confidence level $\in \{0.95, 0.975, 0.99\}$. |

### 3.2 Scenario returns

For each instrument, using only observed prices:

$$r_i(s) = \frac{P_i(s)}{P_i(s^-)} - 1$$

where $s^-$ is the instrument's previous observed day. Aligned onto the Mon–Fri grid:

* **Observed on $s$**: $r_i(s)$ as above. If a holiday intervened, the return spans more than one grid day.
* **Not observed on $s$, but within the instrument's observed history**: $r_i(s) = 0$ (no information, equivalent to a flat price).
* **Before the first observed price** (or in a sparse window, §3.8): *missing*, handled by proxy, then rescale.
* The first return in an instrument's history (its inception date versus a back-filled price) is **never** used.

Prices are GBP-translated by market-data, so returns include FX moves. That's correct for a GBP investor.

### 3.3 Exposures

$V_{i,t}$ comes straight from the ladder. Two sub-accounts that map to the same identifier (e.g. the two Aegon Ethical Equity names) share one return series but stay separate positions (needed later for decomposition). Cash has $r = 0$: it adds to $V_t$ but never to risk. Positions with zero market value (e.g. LF Equity Income, priced at zero) are excluded.

### 3.4 Scenario PnL vector

$$\Pi_t(s) = \sum_{i \in H_t} V_{i,t}\, r_i(s), \qquad s \in W_L(t), \qquad \ell_t(s) = -\Pi_t(s)$$

**Mini example.** Holdings at $t$: A £60,000, B £30,000, Cash £10,000 ($V_t$ = £100,000).

| Scenario day | $r_A$ | $r_B$ | $\Pi_t(s)$ |
|---|---|---|---|
| s1 | −1.2% | +0.4% | −720 + 120 = **−600** |
| s2 | +0.5% | −2.0% | 300 − 600 = **−300** |
| s3 | −3.1% | −2.5% | −1,860 − 750 = **−2,610** |
| s4 | +0.8% | +1.1% | 480 + 330 = **+810** |
| s5 | −0.2% | +0.3% | −120 + 90 = **−30** |

With 520 such scenarios, the 99% VaR is the 6th-largest loss (§3.5).

**Holiday scenario days.** Scenario days where less than 50% (configurable) of today's risky market value was observed (UK bank holidays, Christmas) carry almost no information and are excluded, so $n \le L$. The scenario count $n$ is stored with every estimate.

### 3.5 VaR and ES estimators

VaR is reported as a **positive loss** in GBP and as a percentage of $V_t$.

Sort the losses in descending order, $\ell_{(1)} \ge \ell_{(2)} \ge \dots \ge \ell_{(n)}$:

$$k = n - \lceil n\,p \rceil + 1, \qquad \mathrm{VaR}_p(t) = \ell_{(k)}$$

This is the standard lower-quantile definition $\inf\{\ell : \hat F(\ell) \ge p\}$. It equals `numpy.quantile(losses, p, method="inverted_cdf")` (checked: 0 mismatches for $n$ = 50…2,000 at all three levels). Implement $\lceil n p \rceil$ in **integer arithmetic** ($p$ held in basis points: 9500, 9750, 9900) so floating-point error can't shift the rank.

| $n$ | k @ 95% | k @ 97.5% | k @ 99% |
|---|---|---|---|
| 260 | 14 | 7 | 3 |
| 520 | 27 | 14 | 6 |
| 1,300 | 66 | 33 | 14 |

**Expected Shortfall** (recommended at all three levels; it costs one extra line). This is the empirical Acerbi–Tasche estimator, with $m = n(1-p)$:

$$\mathrm{ES}_p(t) = \frac{1}{m}\left(\sum_{j=1}^{\lfloor m\rfloor}\ell_{(j)} + \left(m-\lfloor m\rfloor\right)\ell_{(\lfloor m\rfloor+1)}\right)$$

The 1-day mean is not subtracted. At a 1-day horizon it is negligible, and leaving it in keeps VaR directly comparable with realised PnL.

### 3.6 Why returns × today's exposure (and not the alternatives)

| Candidate scenario input | Verdict | Reason |
|---|---|---|
| **1-day simple returns × today's GBP exposure** | ✅ Use | It revalues the *current* portfolio under each historical day's market moves. It is scale-free across years (a £10k portfolio in 2016 and £400k today are treated consistently), and portfolio PnL is exactly linear in simple returns, so positions aggregate exactly. |
| Log returns | ✗ | Log returns don't add across positions. At a 1-day horizon the difference is negligible anyway, so simple returns are the natural choice. |
| Absolute price changes (ΔP) | ✗ | They don't scale with price level, so a 2016 £1 move means something different on a fund now priced 3× higher. |
| **Moving-average returns (3/5/10-day)** | ✗ Mathematically unsuitable | Averaging $k$ roughly independent daily returns cuts the standard deviation by about $1/\sqrt{k}$, so VaR is understated by about **42% (3-day), 55% (5-day) and 68% (10-day)**. It also no longer measures a 1-day horizon, so it would fail a 1-day backtest systematically. |
| Overlapping multi-day sums | Later, for multi-day VaR | This is the right tool for a 10-day VaR (or use √10 scaling), not for 1-day. Possible later extension. |
| **The portfolio's actual historical monetary PnL** | ✗ for scenarios, ✅ for backtesting | It measures the risk of *past* portfolios. It mixes in deposits and withdrawals, trades and growth in size, so it can't describe today's risk. It is exactly what the backtest compares against (§4). |

### 3.7 Look-back period: stability vs responsiveness vs data

The 99% quantile of a 260-day window rests on 2–3 observations. Sampling error of the VaR estimate (relative standard error from 20,000-path simulations; "fat" means Student-t with 4 degrees of freedom, typical of daily equity returns):

| Window | Tail scenarios @ 95 / 97.5 / 99 | Rel. SE @95% (normal / fat) | @97.5% | @99% |
|---|---|---|---|---|
| 1Y (260) | 13 / 6.5 / 2.6 | 8.0% / 11.2% | 8.4% / 13.9% | **9.8% / 20.1%** |
| 2Y (520) | 26 / 13 / 5.2 | 5.6% / 8.0% | 5.9% / 9.5% | **7.0% / 13.4%** |
| 3Y (780) | 39 / 19.5 / 7.8 | 4.5% / 6.5% | 4.9% / 7.9% | 5.8% / 11.3% |
| 5Y (1,300) | 65 / 32.5 / 13 | 3.6% / 5.0% | 3.8% / 6.2% | 4.4% / 8.4% |

Trade-offs:

* **Short windows (1Y)** respond quickly to a regime change. They are noisy, though: about ±20% at 99% purely from which 2–3 days happen to be in the window. They also show **ghosting**: VaR jumps as a crisis day enters and drops in a cliff exactly 260 days later.
* **Long windows (5Y)** are stable, but slow to reflect today's volatility. They keep old regimes in the window (e.g. March 2020 until 2025) and need the most proxying (§2.2).
* **2Y** roughly halves the variance of 1Y at 99%, keeps proxy use for current holdings to about 5% of market value, and is the common practitioner compromise. (Basel's minimum is 1Y.)

**Recommendation:** store all three every day and use **2Y as the headline**. Treat this as a hypothesis for the backtest (§4.7) to test, not a fixed truth. Later option (§11-G): **filtered historical simulation**, which scales each historical return by $\sigma_{i,t}/\sigma_{i,s}$ (EWMA, λ = 0.94). It makes a long window responsive and usually reduces clustered exceptions. The store is keyed by `method` so it can sit alongside plain historical simulation.

### 3.8 Short or sparse histories: proxy, then rescale

For each instrument and window, in priority order:

1. **Actual** observed returns where they exist.
2. **Proxy** (`var_proxy` in `InvestmentDataStatic.json`): the proxy's observed GBP returns fill missing scenario days.
   * `var_proxy_mode: "fill_gaps"` (default): use the proxy only before the first observed price, or wherever the instrument is missing.
   * `var_proxy_mode: "always"`: use the proxy for the whole window, for instruments not priced daily.
   * **Automatic sparse detection:** if observed days ÷ grid days in the window is below 0.8 (configurable), the instrument is treated as `always` for that window, if a proxy exists.
   * `var_proxy_scale` (optional, default 1.0) is a static multiplier on proxy returns: $r_i(s) = \beta_i\, r_j(s)$. Estimating it automatically from overlapping observations (at the instrument's own sampling frequency, once there are at least 12 overlapping intervals) is a later enhancement (§11-G).
   * A proxy shares its instrument's scenario returns exactly, so the two get no diversification credit against each other. That errs on the conservative side.
3. **Rescale fallback** (no proxy, or the proxy is also missing): the missing position takes the market-value-weighted mean return of the *available risky* positions on that scenario day:
   $$\Pi_t(s) = \sum_{i \in A_s} V_{i,t}\,r_i(s) \;+\; V^{\text{miss}}_{t,s}\cdot\frac{\sum_{i \in A_s} V_{i,t}\,r_i(s)}{\sum_{i\in A_s} V_{i,t}}$$

**Coverage and quality (stored per date and look-back):** `actual_mv_pct`, `proxied_mv_pct`, `rescaled_mv_pct` (a position counts as proxied or rescaled if it used that treatment on any scenario day), plus `quality`:

| Quality | Default rule (configurable) | Behaviour |
|---|---|---|
| `ok` | rescaled ≤ 5% and proxied ≤ 25% of market value | Published |
| `degraded` | otherwise | Published and flagged; the backtest can filter it out |
| `insufficient` | $n < 0.8L$ or rescaled > 20% | VaR stored as null with the reason |

Example proxy entries:

```json
{ "name": "Lindsell Train Global Equity Class D - Accumulation (GBP)", "isin": "", "ticker": "0P0001WUUI.L",
  "theme": "Global", "var_proxy": "IE00BJSPMJ28", "var_proxy_mode": "fill_gaps" }
{ "name": "Scottish Widows Pension", "isin": "SWPENSION", "ticker": "",
  "theme": "Other Pension", "var_proxy": "GB00B08HD927", "var_proxy_mode": "always", "var_proxy_scale": 1.0 }
```

> `InvestmentDataStatic.json` is also read by the legacy root `PortfolioAnalysis.py`. The new fields are additive and optional, but check that it ignores unknown keys.

### 3.9 Data hygiene rules

* **Outlier guard:** any $|r_i(s)| > 25\%$ (configurable) is reported in run warnings and on the status endpoint. A config exclusion list (`identifier`, `date`) lets a confirmed bad print be replaced by proxy, then rescale. Nothing is dropped silently.
* **T-2 boundary:** VaR is computed up to the ladder's `to_date`.
* **Staleness:** the status endpoint reports the share of exact-zero returns per instrument and window, to catch stale-priced series.

---

## 4. Backtesting methodology

### 4.1 What is compared

Each as-of date $t$ yields one forecast/outcome pair: VaR$_p(t)$ against the PnL from close $t$ to close $t+1$. Two realised PnL series are stored:

| Series | Definition | Role |
|---|---|---|
| **Hypothetical PnL (HPL)** | $\mathrm{HPL}(t{+}1)=\sum_{i\in H_t}V_{i,t}\,r_i(t{+}1)$ using observed returns: the close-$t$ holdings frozen and revalued at $t+1$. | **Primary model validation** (the Basel "hypothetical" backtest). Trades, deposits, withdrawals, income and purchases on $t+1$ can't cause false exceptions. |
| **Ladder PnL (LPL)** | $\text{daily\_return}(t{+}1)\times V_t$, the same series the performance and histogram endpoints use. | "What I observed." Shown on the chart and available as a backtest basis. |

The two are close because the ladder already uses start-of-day weights. They differ through income, price basis (filled vs observed) and first-day returns on new purchases. Large gaps between them are surfaced as data-quality signals.

**This is how changing portfolio construction is handled.** Each day tests the model on *that day's* portfolio, so construction changes show up only as level shifts in VaR, never as contaminated exceptions. Comparing in GBP against same-day GBP VaR (or % against %) also handles the portfolio's growth.

### 4.2 Alignment and look-ahead

* VaR(t) uses returns up to and including $t$ and holdings at close $t$ only.
* Each stored row carries `date` (as-of) and `outcome_date` (next business day). Charts plot VaR(t) at `outcome_date`.
* The newest row's outcome is *pending* until the next run fills it in.

### 4.3 Exceptions and tests

Exception indicator: $I_{t+1} = \mathbf 1\{\text{PnL}(t{+}1) < -\mathrm{VaR}_p(t)\}$, with $\alpha = 1-p$, $N$ observations and $x$ exceptions.

**Kupiec proportion-of-failures** ($\hat\pi = x/N$, $0\ln 0 = 0$):

$$LR_{POF} = -2\ln\!\big[(1-\alpha)^{N-x}\alpha^{x}\big] + 2\ln\!\big[(1-\hat\pi)^{N-x}\hat\pi^{x}\big] \sim \chi^2_1, \qquad p\text{-value} = \operatorname{erfc}\!\big(\sqrt{LR/2}\big)$$

**Christoffersen independence**, which tests for clustering. $n_{ab}$ counts consecutive included days with $I_{t-1}=a, I_t=b$; $\pi_{01}=\frac{n_{01}}{n_{00}+n_{01}}$, $\pi_{11}=\frac{n_{11}}{n_{10}+n_{11}}$, $\pi=\frac{n_{01}+n_{11}}{\sum n_{ab}}$:

$$LR_{ind} = -2\ln\!\big[(1-\pi)^{n_{00}+n_{10}}\pi^{n_{01}+n_{11}}\big] + 2\ln\!\big[(1-\pi_{01})^{n_{00}}\pi_{01}^{n_{01}}(1-\pi_{11})^{n_{10}}\pi_{11}^{n_{11}}\big] \sim \chi^2_1$$

**Conditional coverage:** $LR_{cc} = LR_{POF} + LR_{ind} \sim \chi^2_2$, with $p$-value $= e^{-LR_{cc}/2}$. When days are filtered out (e.g. by quality), the transition chain breaks at each gap.

**Traffic light** (generalises Basel to any $N$ and $p$): with binomial CDF $F(x;N,\alpha)$, the zone is green if $F < 0.95$, yellow if $F < 0.9999$, red otherwise. For $N = 250$, $p = 99\%$ this reproduces Basel's **0–4 / 5–9 / 10+** (verified).

**Stability metrics** (to answer "is it stable?"): the standard deviation of $\ln(\mathrm{VaR}_t/\mathrm{VaR}_{t-1})$, and the count of day-on-day VaR changes above 10%, excluding days where holdings changed.

None of this needs new dependencies: `math.erfc`, `math.exp` and `math.lgamma` are enough.

### 4.4 Statistical power: why the full history matters

Probability of detecting a model whose true exception rate is **2× nominal** (Kupiec test at 5% significance):

| Confidence | N = 250 | N = 520 | N = 1,300 | N = 2,500 |
|---|---|---|---|---|
| 95% | 88% | 99% | 100% | 100% |
| 97.5% | 60% | 87% | 100% | 100% |
| 99% | **24%** | 47% | 86% | 98% |

A single year at 99% is close to uninformative. Run backtests over the **full ladder history** (SIPP ≈ 2,700 days, ISA ≈ 2,130), use 95% and 97.5% to choose the model, and use 99% plus traffic-light zones over rolling 250-day windows for monitoring.

### 4.5 Limited pricing history in practice

VaR(t) needs **price history for the instruments held at t**, not a history of *holding* them. So VaR, and the backtest, can start at the ladder's first date wherever the scenario window passes the quality rule. With a 2Y window: SIPP from 2016-04 needs prices from 2014-04, and the Morningstar fund data from 2014-01-02 covers that. 5Y rows for early dates will mostly be `degraded` or `insufficient`. That is expected and visible, not hidden.

### 4.6 Backtest outputs

For each confidence level, over the requested range: $N$, $x$, expected $N\alpha$, exception rate, $LR_{POF}$ and its $p$, $LR_{ind}$ and its $p$, $LR_{cc}$ and its $p$, zone, exception dates, mean VaR, stability metrics. Optionally a rolling 250-day exception count series. Filters: `pnl_basis` (hypothetical | ladder) and `min_quality`.

### 4.7 Choosing the look-back from evidence

For each of 1Y/2Y/5Y, over the full history:

1. Prefer windows passing POF and CC at 95% and 97.5% ($p > 0.05$).
2. Prefer fewer yellow/red rolling-250-day zones at 99%.
3. Among the windows that pass, choose by stability (§4.3) versus responsiveness: your call. The backtest response puts all of these side by side.

ES backtesting (e.g. the Acerbi–Székely Z2 test) is a possible later addition.

---

## 5. Execution model

### 5.1 Recommendation

**Precompute into a store, through an asynchronous run resource owned by the service. Scripts only trigger runs.**

* **Why not compute on GET?** It would need a ~7 s ladder read plus about 40–70 market-data calls per request, which is far too slow for an interactive, filterable UI.
* **Why not a script that does the gap detection?** "Which dates are missing or stale?" is business logic. Keeping it in the service gives one source of truth, which the status endpoint and the UI can show too. It stays testable under the constitution's Gherkin/TDD rules, avoids duplicating ladder and market-data access in PowerShell, and behaves the same whether a run is manual, scheduled or part of the e2e script.
* **Why asynchronous?** The first run per account fetches years of pre-holding history through yfinance (minutes). Later runs take seconds. A run resource covers both cases without HTTP timeouts.

### 5.2 Run lifecycle

```
POST /v1/accounts/{a}/risk/var/runs  {mode: "missing" | "full", start?, end?}
   │  202 Accepted, Location: …/runs/{run_id}   (409 if a run is already active for {a})
   ▼
single-worker executor (created in the app lifespan; runs are serialised)
   1. load ladder → exposures per date            (holdings fingerprint per date)
   2. select dates: missing ∪ stale (fingerprint ≠) ∪ rows with pending outcomes   [mode=full → all]
   3. fetch observed GBP prices: held identifiers + proxies, one call each,
      range = [earliest date − max look-back − buffer, latest date]   (market-data fill=none)
   4. build aligned returns + provenance (actual / proxy / rescale)
   5. compute VaR/ES for every look-back × confidence; HPL/LPL; fill earlier pending outcomes
   6. upsert into the store atomically (temp file + os.replace, as LadderRepository does)
   7. write the run record: status, counts, durations, warnings (proxied, rescaled, outliers, insufficient)
GET /v1/accounts/{a}/risk/var/runs/{run_id}   → queued | running | succeeded | failed (+ problem detail)
```

* **Stale detection.** Each row stores `row_fingerprint = sha256(methodology_version, var config, proxy config, sorted (identifier, round(V_i,t, 2)))`.
  * A ladder refresh that re-prices, a methodology bump, or a proxy change invalidates exactly the affected rows.
  * Restated *window* prices are not detected (that would mean fetching them anyway); `mode=full` covers that case.
* **Orphaned runs.** `uvicorn --reload` kills background work, so at startup any `running` record is marked `failed` (reason `interrupted`).
* **Observability.** Structured events: `var_run_started`, `var_run_stage` (with durations), `var_instrument_treatment` (proxied/rescaled), `var_outlier_detected`, `var_run_completed` / `var_run_failed`.

### 5.3 Scripts

* **`run_end_to_end.ps1`:** new **Phase 7 "Compute Value at Risk"** (the browser launch moves to Phase 8). For each account it POSTs a `mode=missing` run and polls until the run finishes, with a configurable timeout (default 15 min). It logs dates computed and any warnings. A failure sets `$OverallSuccess = $false` but doesn't block the browser launch.
* **`refresh-var.ps1`** (small, new): the same trigger-and-poll for ad-hoc or Task Scheduler use, without restarting the whole pipeline.
* *Deferred option:* a `var.auto_run_on_ingest` config flag that queues a run after each ladder ingest or refresh.

### 5.4 Store layout (CSV + JSON: no new dependency, human-readable like the ladder store)

```
data/{account}/var/
  meta.json        methodology_version, config snapshot, computed range, last_run_id
  daily.csv        date, outcome_date, market_value_gbp, risky_mv_gbp,
                   hypothetical_pnl_gbp, ladder_pnl_gbp, holdings_fingerprint
  estimates.csv    date, method, lookback_days, scenario_count,
                   actual_mv_pct, proxied_mv_pct, rescaled_mv_pct, quality, quality_reason,
                   var_950_gbp, var_975_gbp, var_990_gbp, es_950_gbp, es_975_gbp, es_990_gbp,
                   row_fingerprint, computed_at
  runs/{run_id}.json
data/_var/instruments.csv   identifier, first_observed_date, last_observed_date, proxy, proxy_mode,
                            last_checked  (shared across accounts; feeds the status endpoint)
```

Size: about 2,700 dates (HL-SIPP) × 3 look-backs ≈ 8,100 estimate rows per account, under 2 MB, read in tens of milliseconds. Exceptions and percentages are derived at query time and not stored. Note: wiping `data/{account}/` to re-ingest also wipes its VaR store. That's acceptable because recomputing is cheap once the market-data cache is warm.

### 5.5 Configuration (`config.yaml`)

```yaml
var:
  methodology_version: "1.0.0"
  lookbacks: {"1y": 260, "2y": 520, "5y": 1300}
  headline_lookback: "2y"
  confidence_levels: [0.95, 0.975, 0.99]
  min_observed_mv_share_per_scenario: 0.5   # holiday-scenario exclusion
  sparse_density_threshold: 0.8
  outlier_abs_return: 0.25
  quality: {ok_max_rescaled_pct: 5, ok_max_proxied_pct: 25,
            insufficient_min_scenario_ratio: 0.8, insufficient_max_rescaled_pct: 20}
  excluded_returns: []                      # [{identifier, date}]
  run_timeout_minutes: 15
```

---

## 6. Data model (entities)

| Entity | Key | Content |
|---|---|---|
| **Exposure** | (account, date) | Positions: sub_account, identifier, theme, market value; total market value; holdings fingerprint |
| **ScenarioSet** | (identifiers, window) | Aligned returns matrix $n \times m$, provenance matrix (actual/proxy/rescaled), scenario dates, excluded days |
| **VarEstimate** | (account, date, method, lookback) | Scenario count, VaR/ES at each confidence (GBP), coverage %, quality and reason, fingerprint, computed_at |
| **RealisedOutcome** | (account, date) | outcome_date, HPL, LPL (null while pending) |
| **VarRun** | (account, run_id) | mode, status, timestamps, dates computed/skipped, warnings, error |
| **InstrumentHistory** | identifier | First/last observed date, proxy configuration, last checked |
| **BacktestResult** | derived, not stored | As in §4.6 |

---

## 7. API design (`portfolio-analysis-service`)

Every response includes HATEOAS `_links` and every error is RFC 7807, per the constitution. Dates resolve exactly as in the performance and histogram endpoints (`TimeseriesDateResolver`).

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /v1/risk/var/methods` | Method metadata | Look-backs, confidence levels, measures, methodology version. Drives the UI controls (same pattern as `/v1/timeseries/attributes`). |
| `GET /v1/accounts/{a}/risk/var/status` | Coverage and freshness | Computed range against the ladder range, missing/stale/pending counts (as of the last run), last run summary, per-instrument treatment per look-back. |
| `POST /v1/accounts/{a}/risk/var/runs` | Queue a run | 202 + `Location`; 409 `var-run-in-progress` with `_links.active_run`. |
| `GET /v1/accounts/{a}/risk/var/runs[/{run_id}]` | Run status / list | 404 `var-run-not-found`. |
| `GET /v1/accounts/{a}/risk/var` | **Time series** | `start`, `end`, `lookback` (1y/2y/5y, default the headline), `confidence` (repeatable, default all). |
| `GET /v1/accounts/{a}/risk/var/backtest` | **Backtest** | `start`, `end`, `lookback`, `confidence`, `pnl_basis` (hypothetical\|ladder), `min_quality`, `include_rolling`. |

Not computed yet: return 200 with an empty `series`, plus `_links.status` and `_links.runs`. This mirrors the histogram's "a valid request with no observations is not an error". New 422 problem types are `invalid-var-lookback` and `invalid-confidence-level`.

**Series response (sketch)**

```json
{
  "account_name": "HL-SIPP", "from_date": "2024-10-01", "to_date": "2026-09-23",
  "method": "historical-simulation", "lookback": {"code": "2y", "days": 520},
  "methodology_version": "1.0.0", "confidence_levels": [0.95, 0.975, 0.99],
  "series": [{
    "date": "2026-09-22", "outcome_date": "2026-09-23",
    "market_value_gbp": 399876.12, "scenario_count": 509,
    "coverage": {"actual_mv_pct": 95.5, "proxied_mv_pct": 4.5, "rescaled_mv_pct": 0.0},
    "quality": "ok",
    "levels": [
      {"confidence": 0.95,  "var_gbp": 4120.55, "var_pct": 1.03, "es_gbp": 6010.20, "es_pct": 1.50},
      {"confidence": 0.975, "var_gbp": 5302.10, "var_pct": 1.33, "es_gbp": 7420.88, "es_pct": 1.86},
      {"confidence": 0.99,  "var_gbp": 7015.43, "var_pct": 1.75, "es_gbp": 9102.37, "es_pct": 2.28}
    ],
    "outcome": {"hypothetical_pnl_gbp": -1820.11, "ladder_pnl_gbp": -1790.02,
                "ladder_return_pct": -0.45,
                "exceptions": [{"confidence": 0.95,  "hypothetical": false, "ladder": false},
                               {"confidence": 0.975, "hypothetical": false, "ladder": false},
                               {"confidence": 0.99,  "hypothetical": false, "ladder": false}]}
  }],
  "_links": {"self": "…", "backtest": "…", "status": "…", "runs": "…", "methods": "/v1/risk/var/methods"}
}
```

*(Values are illustrative.)* About 2,600 rows for 10 years is roughly 1 MB of JSON. That's fine on localhost; requesting fewer `confidence` values trims it.

---

## 8. Incremental VaR readiness (design for later, build the seams now)

The engine is a set of **pure functions over a scenario × position PnL matrix** $P \in \mathbb R^{n\times m}$ with $P_{s,i} = V_{i,t}\,r_i(s)$, so the portfolio PnL is $\Pi = P\mathbf 1$:

```python
def scenario_pnl(exposure: Exposure, scenarios: ScenarioSet) -> PnlMatrix: ...           # n × positions
def summarise(pnl: PnlMatrix, confidences: Sequence[Decimal], total_mv: float) -> VarEstimate: ...
def contributions(pnl: PnlMatrix, confidence: Decimal, groups: Mapping[str, str]) -> list[Contribution]: ...
```

| Measure | Historical-simulation definition | Notes |
|---|---|---|
| Subset / what-if VaR | `summarise` on the columns kept (or on added hypothetical columns) | Same code path |
| Standalone VaR$_i$ | Quantile of $P_{\cdot,i}$ alone | |
| **Incremental VaR$_i$** | $\mathrm{VaR}(\Pi) - \mathrm{VaR}(\Pi - P_{\cdot,i})$ | Exact "with vs without". Cheap: one re-sort per position |
| Component VaR$_i$ (Euler) | $-\overline{P_{s,i}}$ averaged over the K scenarios ranked nearest the VaR scenario | Sums to roughly VaR; noisy with a single scenario |
| **Component ES$_i$** | $-\text{mean}_{s\in\text{tail}} P_{s,i}$ | Sums **exactly** to ES and is far more stable. Recommended as the default contribution measure |
| Marginal VaR$_i$ | Component$_i$ / $V_{i,t}$ | Per £ of exposure |
| Group (theme) | Sum columns by `theme` and apply the same formulas | `theme` is already in the static JSON |
| Combined accounts | Union of exposures by identifier → same functions | Diversification benefit = Σ account VaR − combined VaR |

All of these are computed **on demand for a single date** (a matrix of at most 1,300 × 60, in milliseconds), so they need no precomputation. Feature 014 (§11-E) should persist the aligned returns snapshot from the last run (`data/_var/returns.csv`) so these endpoints don't need market-data calls.

---

## 9. UI design (`portfolio-browser`, Risk page)

```
┌ Risk ──────────────────────────────────────────────────────────────────────────────┐
│ [ Return distribution ] [ Value at Risk ]                                            │
│ Account [HL-SIPP ▾]  From [2024-10-01] To [2026-09-23]  [10Y][1Y][3Y][5Y][All]       │
│ Confidence ☑95 ☑97.5 ☑99 │ Look-back (•2Y ○1Y ○5Y) │ Units (•£ ○%) │ PnL (•Ladder ○Hypothetical) │ ☐ Hide degraded │
├──────────────────────────────────────────────────────────┬─────────────────────────┤
│ Daily PnL vs prior-day VaR                                │ Backtest (visible range) │
│  ▁▃▁▅▂▁▃▁▂▆▁▂▁▃▁▁▂  ← bars: daily PnL (exceptions in red)  │ Lvl   Exc  Exp  POF p  CC p  Zone
│  ────────────────  −VaR 95%                               │ 95%    31  26.0  0.33  0.41   –
│  ─ ─ ─ ─ ─ ─ ─ ─   −VaR 97.5%                             │ 97.5%  15  13.0  0.58  0.72   –
│  ················   −VaR 99%     (optional ES dashed)     │ 99%     7   5.2  0.46  0.66  Green
├──────────────────────────────────────────────────────────┤ Mean VaR99  £7,015        │
│ Market value (line) + proxied/rescaled share (shaded)     │ Stability   1.9% / day    │
└──────────────────────────────────────────────────────────┴─────────────────────────┘
                                                                     (illustrative values)
```

* **Encoding:** bars show PnL plotted at `outcome_date`. The −VaR lines show VaR(t) at `outcome_date`, i.e. each bar sits against the forecast made the previous evening. Exceptions get red markers. A thin shaded band marks `degraded` dates. Step changes in the VaR lines alongside market-value changes show construction effects directly.
* **Responsiveness:** one `GET …/risk/var` per (account, range, look-back) and one `GET …/backtest`, both reading the store. The confidence, units and PnL-basis toggles re-shape client-side from a `dcc.Store` without refetching.
* **States:**
  * *Not computed:* calls `status` and shows "VaR has not been computed for this account. Run `refresh-var.ps1`".
  * *Stale:* a banner with the number of missing dates.
  * *Errors:* the same patterns as the existing Risk page.
* Periodicity controls don't apply (VaR is a daily measure) and are hidden for this view.

---

## 10. Risks, limitations and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Filled prices treated as real (if 009 slips) | VaR understated | D2 is a hard prerequisite. The 012 spec should **fail closed** if market-data doesn't support `fill=none`. |
| Adjusted-close seams / restatement (yfinance `auto_adjust=True`, cache not re-adjusted) | Spurious tail scenarios; past VaR shifts on recompute | Outlier guard plus an exclusion list; `computed_at` and fingerprints; `mode=full` after a cache rebuild. Separately: income added on top of adjusted prices in the ladder may double-count dividends, which affects LPL vs HPL. That's outside this scope but worth a look. |
| Asynchronous pricing (UK OEIC noon NAVs vs ETF closes; overseas funds lag) | 1-day correlations understated, so VaR somewhat low | Document it. The backtest will show it. A later 10-day VaR on overlapping returns reduces the effect. |
| Proxy basis risk | Mis-stated risk on proxied weight | Coverage metrics, quality flags, sibling share classes preferred; static `var_proxy_scale` now, automatic estimation later. Scottish Widows' scale is uncertain (Appendix B), so revisit it as monthly prices accumulate. |
| Sparse-priced instruments (Scottish Widows) | Their lumpy realised moves can trigger spurious exceptions on repricing days | Proxy `always`; tag exceptions that coincide with a sparse instrument's repricing. |
| Sampling noise / ghosting | Unstable 99% VaR | Multiple windows, stability metrics, FHS variant later. |
| Low power at 99% | Misleading "pass" | Full-history backtests; select on 95/97.5% (§4.4). |
| Long first run / killed background work | UI shows nothing; stuck runs | Asynchronous runs, status endpoint, orphan cleanup at startup, inception memo in market-data. |

---

## 11. Delivery plan: speckit features

Dependency order: **A → B → C → D**, with E, F and G later. Numbering continues each project's own `specs/` sequence.

### A. market-data-web-service — `009-observed-price-history` (prerequisite)

```text
/speckit-specify Add an option to the security price history endpoint (GET /securities/{identifier}/history) to return only
observed market prices, without the forward-fill/back-fill gap filling introduced in 006-price-series-fill. Add a query
parameter fill with values "all" (the default, keeping today's gap-filled behaviour and price list exactly as now) and
"none" (only dates that have a real observation from the primary source, cache or local fallback file). When currency
conversion is requested with fill=none, each observed price is converted using the gap-filled FX rate for that date, as
today. In both modes the response gains two additive fields: first_observed_date and last_observed_date for the
instrument, as far as the service knows. Separately, when
a request asks for history before the earliest cached date and the data source has no data for that earlier segment, the
cache must remember that no data exists before the earliest observation, so later requests don't call the data source
again for the same empty segment; this memory must be invalidated if a later fetch does find earlier data, and must be
visible in logs. Local-only fallback files behave the same way (fill=none returns the file's raw rows within the range).
This is needed so a Value-at-Risk calculation in portfolio-analysis-service can tell real returns from filled flat
prices; filled prices must never be presented as observations when fill=none.
```

### B. portfolio-analysis-service — `012-var-calculation-runs`

**Status: implemented** (2026-10-04), on branch `012-var-calculation-runs`. All 62 tasks in
`specs/012-var-calculation-runs/tasks.md` complete; `/speckit-analyze` findings resolved. Live-validated
against the real HL-ISA and HL-SIPP data once market-data-web-service's `009-observed-prices-fill-none`
was running: full runs completed in 14s (2,140 dates, HL-ISA) and 31s (2,721 dates, HL-SIPP), well under
the 60s target; VaR99 ≥ VaR97.5 ≥ VaR95 and ES ≥ VaR held exactly across every non-insufficient estimate;
the rescale fallback for Scottish Widows Pension, WisdomTree Battery Metals and Lindsell Train D Acc
behaved exactly as Appendix A/B predicted (no proxies are configured yet in the live identifier mapping
file). See `specs/012-var-calculation-runs/quickstart.md` §9–10 for the full record.

Deviations from this proposal, found during implementation:
- **Scenario-day inclusion counts the source actually used**, not just an instrument's own observation:
  a position using its proxy on a day counts as covered if the *proxy* was observed that day (§3.4/§3.8
  revised; found via `/speckit-analyze`). Without this, heavy proxy use would wrongly exclude otherwise-
  good scenario days.
- **Sparse-instrument density is measured only from an instrument's first observed price**, not over the
  whole window: a short-history instrument is never treated as "sparse" just because it hasn't existed
  for the full look-back (§3.8 revised; same analysis pass). FR-009 (short history) and FR-010 (sparse
  pricing) are now clearly distinct failure modes.
- **New FR-033**: every error this feature introduces, and every run record, carries a `correlation_id`
  (constitution Principle IV). The *existing* endpoints' shared `ProblemDetail` still lacks one — see the
  follow-up item below.
- `mypy`'s `python_version` was bumped from `3.11` to `3.12` in `pyproject.toml`: numpy 2.5's own `.pyi`
  stubs use PEP 695 syntax that mypy only parses under 3.12+, and numpy is this feature's first direct
  import of it. No runtime-syntax effect (research.md §14b).
- A real-data bug was found and fixed during implementation (not a design deviation, but worth recording
  per the project's "live testing catches what unit tests miss" lesson, feature 004): `VarRepository`
  crashed merging a freshly computed timezone-aware `computed_at` with one already round-tripped through
  CSV (naive) on a second commit to the same account. Fixed by normalising datetime columns to naive UTC
  consistently on read and merge.

**Follow-up for a later feature**: add `correlation_id` to the *existing* endpoints' shared
`ProblemDetail`/`_problem` helper in `app/main.py` (currently only this feature's three new error types
carry one — plan.md's Complexity Tracking table records this as an inherited, not newly introduced, gap).

```text
/speckit-specify Add a historical-simulation Value at Risk (VaR) calculation to the risk endpoint group, precomputed into a
per-account store by asynchronous calculation runs. For every business date in an account's position ladder, take the
positions held at the close of that date and their GBP market values, and build a vector of hypothetical 1-day profit and
loss by applying each historical business day's simple 1-day GBP return of each instrument (observed prices only, using
market-data-web-service history with fill=none) to today's market values. Cash has zero return. Compute look-back windows
of 260, 520 and 1300 business days (1Y, 2Y, 5Y) from the same scenarios, and for each report VaR and Expected Shortfall
at 95%, 97.5% and 99% as positive GBP losses, where VaR is the k-th largest loss with k = n - ceil(n*p) + 1 using integer
arithmetic, and ES is the Acerbi-Tasche empirical tail mean. Exclude scenario days where less than a configurable share
(default 50%) of the risky market value was observed. Instruments without enough real history use a proxy instrument
configured per instrument in the identifier mapping file (new optional fields var_proxy, var_proxy_mode with values
fill_gaps or always, and var_proxy_scale, a static multiplier on the proxy's returns defaulting to 1.0; sparse-priced
instruments below a configurable observation density are treated as always); if no
proxy is available, the missing position takes the market-value-weighted mean return of the available risky positions
for that scenario day. Every estimate records the scenario count, the share of market value that was actual, proxied and
rescaled, and a quality flag (ok, degraded, insufficient — insufficient estimates are stored without a VaR value) using
configurable thresholds. For each date also store the realised outcome on the next business day: hypothetical PnL (close
holdings revalued at next-day observed prices) and ladder PnL (the performance endpoints' daily return times the previous
day's total market value); the newest date's outcome is pending until a later run fills it. Runs are created with POST
/v1/accounts/{account}/risk/var/runs (mode "missing" or "full", optional start/end), return 202 with a run resource whose
status can be read at GET .../runs/{run_id}, and execute one at a time in the background; only one active run per
account is allowed (409 otherwise). In "missing" mode the service itself works out which dates have no estimate, whose
stored fingerprint (methodology version, VaR configuration, proxy configuration and that date's holdings) no longer
matches, or whose outcome is pending, and computes only those. Results are upserted atomically into CSV files under the
account's data directory. Add GET /v1/accounts/{account}/risk/var/status reporting computed range versus ladder range,
missing/stale/pending counts, the last run, and each instrument's history treatment per look-back. Report returns above
a configurable absolute threshold as warnings, and support a configured exclusion list of bad prices. Runs left
"running" when the service restarts are marked failed at startup. Extend run_end_to_end.ps1 with a new phase after
capital ingestion that triggers a "missing" run per account and polls it to completion, and add a small refresh-var.ps1
script that does the same on its own. Methodology reference: docs/proposals/value-at-risk.md sections 3 and 5.
```

### C. portfolio-analysis-service — `013-var-series-backtest-api`

```text
/speckit-specify Add read-only endpoints over the precomputed VaR store from feature 012. GET
/v1/accounts/{account}/risk/var returns, for a start/end date range (resolved exactly like the performance endpoints), a
look-back (1y, 2y or 5y; default the configured headline 2y) and one or more confidence levels (default all), one entry
per business date with the as-of date, the outcome date, total market value, scenario count, coverage percentages,
quality flag, and for each confidence level VaR and ES in GBP and as a percentage of total market value, plus the
realised hypothetical and ladder PnL on the outcome date and whether each was an exception (loss larger than that
level's VaR). If nothing has been computed, return an empty series with links to the status and runs resources rather
than an error. GET /v1/accounts/{account}/risk/var/backtest returns, per confidence level over the range: observation
count, exception count, expected exceptions, exception rate, Kupiec proportion-of-failures likelihood ratio and p-value,
Christoffersen independence and conditional-coverage likelihood ratios and p-values (transition chains break where days
are excluded), a traffic-light zone from the binomial distribution (green below 95% cumulative probability, yellow below
99.99%, red otherwise, which reproduces Basel's 0-4/5-9/10+ for 250 days at 99%), exception dates, mean VaR and VaR
stability (standard deviation of daily log change in VaR, excluding days when holdings changed); parameters select
pnl_basis (hypothetical, the default, or ladder), a minimum quality, and optionally a rolling 250-day exception count
series. GET /v1/risk/var/methods describes the available method, look-backs, confidence levels and measures so clients
can build controls. No new dependencies: chi-squared p-values via erfc/exp and binomial probabilities via lgamma. Responses
follow the existing HATEOAS and RFC 7807 conventions. Methodology reference: docs/proposals/value-at-risk.md section 4.
```

### D. portfolio-browser — `026-risk-var-page`

```text
/speckit-specify Add a "Value at Risk" view to the Risk page alongside the existing return histogram (e.g. as a second
tab), using the shared account selector, date range controls and shortcut buttons. Controls: confidence levels (95%,
97.5%, 99%, multi-select, populated from GET /v1/risk/var/methods), look-back (1Y/2Y/5Y, default 2Y), units (GBP or % of
market value), PnL basis (ladder or hypothetical) and a toggle to hide degraded-quality dates. The main chart shows daily
realised PnL as bars plotted on each outcome date, overlaid with the negative VaR line for each selected confidence level
taken from the previous business day's estimate, with exceptions (losses beyond VaR) highlighted in red; ES can be shown
as dashed lines. Beneath it, a smaller linked chart shows total market value and the proxied/rescaled share of market
value so changes in portfolio construction are visible. A side panel shows the backtest summary for the visible range
from GET .../risk/var/backtest: exceptions versus expected, Kupiec and conditional-coverage p-values, traffic-light zone,
mean VaR and VaR stability. Changing confidence, units or PnL basis must re-render from already-fetched data without a
new request; changing account, dates or look-back refetches. When VaR has not been computed for the account, show an
empty state explaining how to run it (using GET .../risk/var/status); when the store is behind the ladder, show a
banner with the number of missing dates. Periodicity controls do not apply to this view.
```

### E–G. Later features

| Feature | Scope (outline for a future `/speckit-specify`) |
|---|---|
| **E. PAS `014-var-contributions`** | `GET …/risk/var/contributions?date=&lookback=&confidence=&group_by=position\|theme` (standalone, incremental, component ES/VaR, marginal); `POST /v1/risk/var/evaluations` for what-if holdings or **combined accounts** (union of exposures); persist the aligned returns snapshot from runs. |
| **F. Browser `027-risk-var-contributions`** | Contribution waterfall / treemap for a selected date; what-if toggles to remove positions. |
| **G. PAS `015-var-filtered-hs`** | Volatility-scaled (EWMA λ = 0.94) historical simulation as a second `method`, backtested side by side. Also automatic proxy-scale estimation from overlapping observations at each instrument's own sampling frequency, shown on the status endpoint next to the configured value. |
| **H. PAS correlation-id-everywhere** | Add `correlation_id` to the shared `ProblemDetail`/`_problem` helper in `app/main.py`, so every *existing* endpoint's error response carries one (feature 012 added it only to its own three new error types; this closes the inherited gap recorded in that feature's plan.md Complexity Tracking table). |

---

## 12. Open questions for your review

These are defaults I chose. Confirm or change them before the specs are written:

1. **Headline look-back 2Y** (also storing 1Y and 5Y). Agree, or wait for backtest evidence before picking a headline?
2. **ES at all three levels**, or only at 97.5%?
3. **Quality thresholds** (§3.8) and the **50% holiday-scenario exclusion** (§3.4): sensible starting points?
4. **Store format CSV** (no new dependency, human-readable) vs Parquet (adds `pyarrow`). The volumes are small, so I recommend CSV.
5. **Store location** `data/{account}/var/` (wiped together with the account) vs a separate `data/_var/{account}/`. Which fits how you re-ingest ledgers?
6. **Trigger:** explicit runs plus the e2e phase now, auto-run after ingest later. OK?
7. **Primary backtest basis = hypothetical PnL**, with ladder PnL as the default *chart* view. OK?
8. **Proxy choices** to put in `InvestmentDataStatic.json`:
   * Lindsell Train D Acc (`0P0001WUUI.L`) → D Income `IE00BJSPMJ28` (same fund).
   * Pictet Clean Energy I Acc EUR (`0P0000HXSI.F`) → I Income GBP `LU0448836949` (same fund).
   * iShares Pacific ex Japan S (`GB00BN08ZQ59`) → Class H `GB00BJL5C004`, if its history is deep enough.
   * ~~Scottish Widows Pension~~ → **decided (D4)**: BlackRock Consensus 85 (`GB00B08HD927`), mode `always`, scale 1.0. Open point: keep 1.0 or set a prudent scale such as 1.5 until about 12 monthly prices exist (Appendix B)?
   * **WisdomTree Battery Metals**: candidates already in the universe include LITM.L or BATG.L.
   * For 5Y only: Ark Genomic, Schroder ISF Global Climate Change, Vanguard ActiveLife, iShares Lithium.
9. Should **combined ISA + SIPP** VaR be pulled forward into feature E, or left for later?

---

## Appendix A — Price history depth of current holdings (yfinance probe, 2026-10-03)

Window starts as of 2026-09-23: 1Y ≈ 2025-09-24, 2Y ≈ 2024-09-25, 5Y ≈ 2021-09-28. "Local" = served from market-data's local fallback file.

| Instrument | Identifier | History from | 1Y | 2Y | 5Y | Weight |
|---|---|---|---|---|---|---|
| Aegon Ethical Equity B Acc | GB0007450884 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.3% |
| Ark Genomic Revolution UCITS ETF | AAKG.DE | 2024-04-22 | ✓ | ✓ | ✗ | SIPP 1.1% |
| BNY Mellon Real Return U Acc | GB00BSPPWT88 | 2015-01-08 | ✓ | ✓ | ✓ | SIPP 3.3% |
| Barclays plc | GB0031348658 | 1988-07-01 | ✓ | ✓ | ✓ | ISA 18.3% |
| Barings Global Resources I Acc | 0P0000UUOR.L | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.4% |
| Biotech Growth Trust | BIOG.L | 1997-06-23 | ✓ | ✓ | ✓ | SIPP 0.3% |
| BlackRock Consensus 85 I Acc | GB00B08HD927 (local, daily) | 2005-08-19 | ✓ | ✓ | ✓ | SIPP 22.2% |
| BlackRock World Healthscience D5 Inc | LU2112292763 (local, daily) | 2020-02-27 | ✓ | ✓ | ✓ | SIPP 0.5% |
| CT European Select Z Acc | GB00B8BC5H23 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 2.6% |
| GS Global High Yield R Inc (Hedged) | LU0858294910 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.2% |
| HSBC EURO STOXX 50 ETF | IE00B4K6B022 | 2009-10-06 | ✓ | ✓ | ✓ | SIPP 2.7% |
| HSBC FTSE 250 Index S Acc | GB00BV8VN686 | 2015-01-27 | ✓ | ✓ | ✓ | SIPP 2.8% |
| HSBC FTSE 250 Index S Inc | GB00BV8VN462 | 2015-01-27 | ✓ | ✓ | ✓ | ISA 7.7% |
| HSBC GIF Chinese Equity BC Acc | LU0854282091 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.2% |
| IFSL Marlborough UK Micro-Cap P Acc | GB00B8F8YX59 (local, daily) | 2016-01-04 | ✓ | ✓ | ✓ | SIPP 2.2% |
| Invesco NASDAQ Biotech ETF | SBIO.L | 2014-11-07 | ✓ | ✓ | ✓ | SIPP 0.7% |
| JPM Global Macro Opportunities C Acc | 0P0000Y1OB.L | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.3% |
| JPMorgan Emerging Markets C Acc | GB0030881774 | 2019-01-02 | ✓ | ✓ | ✓ | ISA 1.8%, SIPP 4.8% |
| JPMorgan Global (Ex-UK) Bond C Acc | GB00B235J081 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 0.1% |
| JPMorgan Natural Resources C Acc | 0P0000X9FA.L | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.4% |
| L&G Battery Value-Chain ETF | BATG.L | 2018-01-18 | ✓ | ✓ | ✓ | SIPP 0.4% |
| L&G Global Healthcare & Pharma C Acc | 0P0001FT5V.L | 2020-12-01 | ✓ | ✓ | ✓ | SIPP 0.7% |
| L&G Global Technology Index C Acc | GB00BJLP1W53 | 2020-12-01 | ✓ | ✓ | ✓ | ISA 10.6% |
| **Lindsell Train Global Equity D Acc** | 0P0001WUUI.L | 2025-07-14 | ✓ | ✗ | ✗ | ISA 5.4% |
| Lindsell Train Global Equity D Inc | IE00BJSPMJ28 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 4.7% |
| Man Group plc | JE00BJ1DLW90 | 1994-10-13 | ✓ | ✓ | ✓ | ISA 33.4% |
| Man Japan CoreAlpha Professional Acc | GB00B0119B50 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 7.4% |
| Man Undervalued Assets C Acc | 0P0001038I.L | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 0.8% |
| **Pictet Clean Energy Transition I Acc (EUR)** | 0P0000HXSI.F | 2022-03-07 | ✓ | ✓ | ✗ | SIPP 2.3% |
| Pictet Clean Energy Transition I Inc (GBP) | LU0448836949 | 2014-01-02 | ✓ | ✓ | ✓ | ISA 2.2%, SIPP 0.6% |
| Sarasin Food & Agriculture P Acc | 0P0000X4D4.L | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 0.5% |
| Schroder European Climate Transition Z Acc | GB00B6S00Y77 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 0.7% |
| **Schroder ISF Global Climate Change C Acc** | LU0302446132 | 2022-03-07 | ✓ | ✓ | ✗ | SIPP 1.8% |
| **Scottish Widows Pension** | SWPENSION (local, ~8 prices) | sparse | ✗ | ✗ | ✗ | SIPP 4.1% |
| UBS S&P 500 Index C Acc | GB00BMN91T34 | 2014-11-12 | ✓ | ✓ | ✓ | ISA 1.9%, SIPP 3.0% |
| **Vanguard ActiveLife Climate Aware A Acc** | GB00BMCQRZ38 | 2021-12-08 | ✓ | ✓ | ✗ | SIPP 0.7% |
| **WisdomTree Battery Metals ETC** | AMPS.L (local, ~37 prices) | sparse | ✗ | ✗ | ✗ | SIPP 0.4% |
| Xtrackers MSCI Europe IT ESG ETF | LU0292104469 | 2008-01-02 | ✓ | ✓ | ✓ | SIPP 2.1% |
| Xtrackers Stoxx Europe 600 ETF | XSX6.L | 2009-01-20 | ✓ | ✓ | ✓ | ISA 8.8%, SIPP 1.4% |
| abrdn Global Smaller Companies S Acc | GB00BBX46522 | 2014-01-02 | ✓ | ✓ | ✓ | SIPP 1.8% |
| iShares Healthcare Innovation ETF | DRDR.L | 2016-09-08 | ✓ | ✓ | ✓ | SIPP 1.6% |
| **iShares Lithium & Battery Producers ETF** | LITM.L | 2023-10-31 | ✓ | ✓ | ✗ | SIPP 0.4% |
| iShares Electric Vehicles & Driving Tech ETF | ECAR.L | 2019-02-20 | ✓ | ✓ | ✓ | SIPP 0.7% |
| **iShares Pacific ex Japan Equity Index S Acc** | GB00BN08ZQ59 | 2022-09-26 | ✓ | ✓ | ✗ | SIPP 5.8% |
| iShares S&P 500 IT Sector ETF | IE00B3WJKG14 | 2015-11-20 | ✓ | ✓ | ✓ | ISA 5.8%, SIPP 3.3% |
| iShares Nikkei 225 ETF | CNKY.L | 2010-01-26 | ✓ | ✓ | ✓ | SIPP 3.0% |
| LF Equity Income Z Acc | zero (suspended) | — | — | — | — | 0% (excluded) |

Historical holdings (for backtest dates) will have their own coverage. The `status` endpoint reports it after the first run.

---

## Appendix B — Scottish Widows Pension proxy evidence (2026-10-03)

Scottish Widows Pension is a balanced mixed-asset pension fund with 8 local prices (about monthly, 2026-02-11 → 2026-09-07). Each candidate's return is measured over the **same intervals** (candidate price on or before each Scottish Widows date):

| Interval | Scottish Widows | BlackRock Consensus 85 | Vanguard ActiveLife 40–50% |
|---|---|---|---|
| 02-11 → 03-05 | +1.17% | +0.46% | −0.81% |
| 03-05 → 04-08 | −1.90% | −0.30% | +0.13% |
| 04-08 → 05-06 | +4.14% | +2.61% | +1.95% |
| 05-06 → 06-05 | +4.56% | +1.72% | +1.18% |
| 06-05 → 07-07 | +0.53% | +1.04% | +0.75% |
| 07-07 → 08-05 | +1.13% | +1.11% | +0.81% |
| 08-05 → 09-07 | +0.22% | +0.04% | +0.30% |
| **Correlation with Scottish Widows** | — | **0.90** | 0.64 |
| **Cumulative** | +10.10% | +6.83% | +4.37% |

* **Consensus 85 is chosen.** It has the highest correlation, and its daily local history (back to 2005) covers every look-back window. Vanguard ActiveLife's history starts in 2021-12, so it would itself need a proxy for 5Y.
* **The scale is uncertain.** Regressing Scottish Widows on Consensus 85 gives β ≈ 2.0, but with only 7 intervals the 95% confidence interval is **0.87 – 3.17**. And the absolute volatilities line up: Scottish Widows' annualised volatility from its monthly prices is about **7.8%**, close to Consensus 85's long-run daily volatility (8.9% over the last year, 9.3% over 5Y). Consensus 85 just happened to be unusually calm month to month in this window (3.5% annualised on the same intervals). That's why the starting choice is **1:1**.
* **Sensitivity:** Scottish Widows is 4.1% of SIPP's market value, so moving the scale from 1.0 to 2.0 changes SIPP VaR by roughly that weight's contribution at most (a few percent). Revisit once about 12 monthly intervals exist (around 2027-02), or when the automatic estimation in §11-G is available.
