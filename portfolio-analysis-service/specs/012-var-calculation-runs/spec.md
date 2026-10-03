# Feature Specification: Historical-Simulation VaR Calculation Runs

**Feature Branch**: `012-var-calculation-runs`
**Created**: 2026-10-03
**Status**: Draft
**Input**: User description: "Add a historical-simulation Value at Risk (VaR) calculation to the risk endpoint group, precomputed into a per-account store by asynchronous calculation runs. For every business date in an account's position ladder, take the positions held at the close of that date and their GBP market values, and build a vector of hypothetical 1-day profit and loss by applying each historical business day's simple 1-day GBP return of each instrument (observed prices only, using market-data-web-service history with fill=none) to today's market values. Cash has zero return. Compute look-back windows of 260, 520 and 1300 business days (1Y, 2Y, 5Y) from the same scenarios, and for each report VaR and Expected Shortfall at 95%, 97.5% and 99% as positive GBP losses, where VaR is the k-th largest loss with k = n - ceil(n*p) + 1 using integer arithmetic, and ES is the Acerbi-Tasche empirical tail mean. Exclude scenario days where less than a configurable share (default 50%) of the risky market value was observed. Instruments without enough real history use a proxy instrument configured per instrument in the identifier mapping file (new optional fields var_proxy, var_proxy_mode with values fill_gaps or always, and var_proxy_scale, a static multiplier on the proxy's returns defaulting to 1.0; sparse-priced instruments below a configurable observation density are treated as always); if no proxy is available, the missing position takes the market-value-weighted mean return of the available risky positions for that scenario day. Every estimate records the scenario count, the share of market value that was actual, proxied and rescaled, and a quality flag (ok, degraded, insufficient — insufficient estimates are stored without a VaR value) using configurable thresholds. For each date also store the realised outcome on the next business day: hypothetical PnL (close holdings revalued at next-day observed prices) and ladder PnL (the performance endpoints' daily return times the previous day's total market value); the newest date's outcome is pending until a later run fills it. Runs are created with POST /v1/accounts/{account}/risk/var/runs (mode "missing" or "full", optional start/end), return 202 with a run resource whose status can be read at GET .../runs/{run_id}, and execute one at a time in the background; only one active run per account is allowed (409 otherwise). In "missing" mode the service itself works out which dates have no estimate, whose stored fingerprint (methodology version, VaR configuration, proxy configuration and that date's holdings) no longer matches, or whose outcome is pending, and computes only those. Results are upserted atomically into CSV files under the account's data directory. Add GET /v1/accounts/{account}/risk/var/status reporting computed range versus ladder range, missing/stale/pending counts, the last run, and each instrument's history treatment per look-back. Report returns above a configurable absolute threshold as warnings, and support a configured exclusion list of bad prices. Runs left "running" when the service restarts are marked failed at startup. Extend run_end_to_end.ps1 with a new phase after capital ingestion that triggers a "missing" run per account and polls it to completion, and add a small refresh-var.ps1 script that does the same on its own. Methodology reference: docs/proposals/value-at-risk.md sections 3 and 5."

## User Scenarios & Testing *(mandatory)*

Throughout this section, "risky market value" means the total market value of an account's non-Cash
positions on a date, and a "scenario day" is one historical business day whose instrument returns are
applied to the current holdings. Look-back windows and thresholds are configurable; scenarios that
need small hand-checkable windows say so explicitly in their Given steps.

### User Story 1 - Compute VaR and Expected Shortfall for Every Ladder Date (Priority: P1)

The account owner wants to know, for each business day in an account's history, how much the
portfolio held at that day's close could plausibly lose over the next business day. For each date
the service revalues that day's holdings under every historical scenario day in a look-back window,
producing a set of hypothetical profit-and-loss outcomes, and reports the loss at 95%, 97.5% and 99%
confidence (VaR) and the average loss beyond each of those points (Expected Shortfall), for 1-year,
2-year and 5-year look-backs.

**Why this priority**: These numbers are the whole purpose of the feature; every other story either
schedules, qualifies or exposes them.

**Independent Test**: Seed an account ladder and observed price histories with hand-chosen values,
run a full calculation, and compare the stored VaR and ES for a chosen date and look-back against
values calculated by hand.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Scenario PnL applies historical returns to the holdings at the as-of date
  Given account "test-portfolio" holds on 2026-03-02 "Equity A" worth 60000 GBP,
      "Equity B" worth 30000 GBP and Cash worth 10000 GBP
  And the look-back window is configured as 5 business days
  And the observed returns of A and B on the 5 scenario days ending 2026-03-02 are
      (-1.2%, +0.4%), (+0.5%, -2.0%), (-3.1%, -2.5%), (+0.8%, +1.1%) and (-0.2%, +0.3%)
  When a full VaR run completes for "test-portfolio"
  Then the scenario PnL values for 2026-03-02 are -600, -300, -2610, 810 and -30 GBP
  And Cash contributes nothing to any scenario

Scenario: VaR is the k-th largest loss with k = n - ceil(n*p) + 1
  Given an as-of date with 520 scenario losses of 1, 2, 3, ... 520 GBP
  When the estimate is computed for the 520-day look-back
  Then VaR at 95% is 494 GBP, at 97.5% is 507 GBP and at 99% is 515 GBP

Scenario: Expected Shortfall is the empirical tail mean
  Given an as-of date with 520 scenario losses of 1, 2, 3, ... 520 GBP
  When the estimate is computed for the 520-day look-back
  Then ES at 95% is 507.5 GBP, at 97.5% is 514 GBP
  And ES at 99% is (520 + 519 + 518 + 517 + 516 + 0.2 × 515) / 5.2 GBP

Scenario: All three look-backs come from the same scenario history
  Given an account with observed price history covering at least 1300 business days before 2026-03-02
  When a full VaR run completes
  Then 2026-03-02 has one estimate for each of the 260, 520 and 1300 business-day look-backs
  And each estimate reports VaR and ES at 95%, 97.5% and 99% as positive GBP amounts

Scenario: Low-information scenario days are excluded
  Given the look-back window is configured as 5 business days
  And on one of those scenario days only 40% of the as-of date's risky market value had an observed price
  When the estimate is computed
  Then that scenario day is excluded and the estimate records a scenario count of 4
```

---

### User Story 2 - Start a Calculation Run and Follow Its Progress (Priority: P1)

A developer or script asks the service to calculate VaR for an account. The request is acknowledged
immediately with a run identifier, the calculation proceeds in the background, and the caller can
check whether the run is queued, running, succeeded or failed, with counts and any warnings.

**Why this priority**: Calculations can take minutes the first time (long price histories must be
retrieved), so they cannot run inside an ordinary request. Without runs, nothing is ever computed.

**Independent Test**: Request a run, confirm the immediate acknowledgement and run location, poll the
run until it finishes, and confirm the store now holds estimates.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Creating a run is acknowledged immediately
  Given account "test-portfolio" has an ingested position ladder
  When a run is requested for "test-portfolio" with mode "full"
  Then the response is accepted (202) with a run identifier, status "queued" or "running",
      and a link to the run resource

Scenario: A finished run reports its outcome
  Given a run for "test-portfolio" has been requested
  When the run completes
  Then reading the run returns status "succeeded", the number of dates computed,
      start and finish times, and any warnings

Scenario: Only one active run per account
  Given a run for "test-portfolio" is queued or running
  When another run is requested for "test-portfolio"
  Then the request is rejected with a conflict (409) that links to the active run

Scenario: Runs execute one at a time
  Given runs are requested for "account-a" and then "account-b"
  When both have finished
  Then their running periods did not overlap

Scenario: A failed run records why
  Given the market data service is unavailable
  When a run for "test-portfolio" executes
  Then the run status is "failed" with a problem description naming the cause
  And no partially computed results are written to the store

Scenario: Interrupted runs are not left running
  Given a run record for "test-portfolio" shows status "running"
  When the service starts up
  Then that run's status is "failed" with reason "interrupted"

Scenario: Invalid run requests are rejected
  Given account "test-portfolio" has an ingested position ladder
  When a run is requested with mode "partial", or with start later than end
  Then the request is rejected with a client error (422) describing the problem
  And when a run is requested for an account with no ingested data the response is not-found (404)
  And when an unknown run identifier is read the response is not-found (404)
```

---

### User Story 3 - Handle Instruments With Short or Sparse Price History (Priority: P2)

Some instruments have not existed for as long as the look-back window, and some are priced only about
monthly. The account owner configures, per instrument, a proxy instrument whose returns stand in for
the missing history (optionally scaled), and the service records exactly how much of each estimate
relied on real, proxied or approximated returns, flagging estimates that relied too heavily on
approximation.

**Why this priority**: Without it, missing or flat-priced history silently understates risk. It is
second only to the core calculation because results are not trustworthy without it.

**Independent Test**: Configure an instrument with a short history and a proxy, run a calculation, and
confirm that scenario days before the instrument's first price use the scaled proxy return and that
the estimate's coverage percentages and quality flag are as expected.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Proxy fills scenario days before an instrument's first observed price
  Given "Equity B" has its first observed price on 2026-02-23
  And "Equity B" is configured with proxy "Proxy P", mode "fill_gaps" and scale 1.5
  And "Proxy P" has an observed return of -2% on scenario day 2026-02-18
  When the estimate for 2026-03-02 is computed
  Then "Equity B" contributes a return of -3% on scenario day 2026-02-18
  And "Equity B" uses its own observed returns from 2026-02-24 onward

Scenario: Mode "always" uses the proxy for the whole window
  Given "Pension Fund" is configured with proxy "Balanced Proxy" and mode "always"
  When an estimate is computed
  Then every scenario return for "Pension Fund" is the proxy's return multiplied by its scale

Scenario: Sparsely priced instruments are treated as "always"
  Given "Pension Fund" has observed prices on fewer than the configured share of business days in the window
  And "Pension Fund" is configured with proxy "Balanced Proxy" and mode "fill_gaps"
  When an estimate is computed
  Then every scenario return for "Pension Fund" in that window is taken from the proxy

Scenario: No proxy available falls back to the mean of available risky positions
  Given on 2026-03-02 "Equity A" is worth 60000 GBP, "Equity C" 20000 GBP and "Equity B" 20000 GBP
  And on one scenario day A returned -1% and C returned +2%, and B has no observed or proxy return
  When the estimate is computed
  Then that scenario's PnL is -250 GBP (B takes the value-weighted mean return of A and C, -0.25%)

Scenario: Coverage and quality are recorded on every estimate
  Given an estimate where 70% of risky market value used actual returns, 26% proxied and 4% rescaled
  When the estimate is stored
  Then it records actual 70%, proxied 26% and rescaled 4% and a quality of "degraded"

Scenario: Insufficient estimates carry no VaR value
  Given an estimate where more than 20% of risky market value had to be rescaled
  When the estimate is stored
  Then its quality is "insufficient", it has a stated reason, and it carries no VaR or ES values
```

---

### User Story 4 - Record the Realised Outcome Against Each Estimate (Priority: P2)

To judge later whether the estimates were realistic, the account owner needs, for each as-of date,
what actually happened on the next business day: the hypothetical profit or loss of the as-of
date's holdings revalued at next-day prices, and the profit or loss the existing performance views
report for that day.

**Why this priority**: Required for backtesting (a separate feature) and for the planned chart of
observed PnL against VaR; storing it during the same run avoids a second slow pass over the data.

**Independent Test**: Seed two consecutive business days of holdings and prices, run a calculation,
and compare both stored outcome figures against hand calculations; confirm the latest date is pending.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Hypothetical PnL revalues the as-of holdings at next-day prices
  Given on 2026-03-02 the account holds "Equity A" worth 60000 GBP and "Equity B" worth 30000 GBP
  And on 2026-03-03 A's observed return is +1% and B's is -2%
  When a run computes 2026-03-02
  Then the outcome for 2026-03-02 has outcome date 2026-03-03 and hypothetical PnL 0 GBP

Scenario: Ladder PnL uses the performance endpoints' daily return
  Given the performance endpoints report a daily portfolio return of -0.5% for 2026-03-03
  And the account's total market value on 2026-03-02 was 100000 GBP
  When a run computes 2026-03-02
  Then the outcome for 2026-03-02 has ladder PnL -500 GBP

Scenario: The newest date's outcome is pending and is filled later
  Given the ladder's last date is 2026-03-02
  When a run completes
  Then the outcome for 2026-03-02 is pending
  And when the ladder later extends to 2026-03-03 and a "missing" run completes
  Then the outcome for 2026-03-02 is filled in
```

---

### User Story 5 - Recompute Only What Is Missing or Out of Date (Priority: P2)

Routine refreshes should be quick and safe: a "missing" run computes only dates with no estimate,
dates whose inputs (methodology version, configuration, proxy configuration or that date's holdings)
have changed since they were computed, and dates whose outcome is pending. A "full" run recomputes
everything in the requested range.

**Why this priority**: Makes daily refreshes cheap and keeps stored history stable, but the feature
is still usable with full runs alone.

**Independent Test**: Run "full", then run "missing" with no changes and confirm nothing is
recomputed; change one date's holdings or a proxy setting and confirm only the affected dates are.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Nothing to do when the store is current
  Given a full run has completed for "test-portfolio" and nothing has changed since
  When a "missing" run completes
  Then it reports 0 dates computed

Scenario: New ladder dates are computed
  Given the store covers dates up to 2026-03-02 and the ladder now extends to 2026-03-04
  When a "missing" run completes
  Then estimates exist for 2026-03-03 and 2026-03-04 and earlier estimates are unchanged

Scenario: Changed holdings make a date stale
  Given a full run has completed and the ladder is re-priced so 2026-03-02's market values change
  When a "missing" run completes
  Then 2026-03-02 is recomputed and dates whose holdings did not change are not

Scenario: Configuration changes make every affected date stale
  Given a full run has completed
  When the methodology version or VaR configuration changes and a "missing" run completes
  Then every date is recomputed

Scenario: A run can be restricted to a date range
  Given account "test-portfolio" has ladder dates from 2026-01-02 to 2026-03-31
  When a "full" run is requested with start 2026-03-02 and end 2026-03-06
  Then only dates from 2026-03-02 to 2026-03-06 are recomputed
```

---

### User Story 6 - See Calculation Coverage, Freshness and Data Warnings (Priority: P3)

The account owner (and the browser UI) needs one place to see whether VaR is up to date for an
account: which date range is computed against the ladder's range, how many dates are missing, stale
or pending, how the last run went, how each instrument's history was treated in each look-back, and
any suspicious returns that were detected.

**Why this priority**: Diagnostic and supports the later UI and scripts; the calculation is usable
without it.

**Independent Test**: Run a calculation for an account with a proxied instrument and an extreme
return, then read the status and confirm each reported item.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Status compares the computed range with the ladder
  Given the ladder covers 2026-01-02 to 2026-03-31 and estimates exist up to 2026-03-27
  When the VaR status for the account is requested
  Then it reports the ladder range, the computed range, 2 missing dates and the last run's summary

Scenario: Status reports each instrument's treatment per look-back
  Given "Equity B" used actual returns in the 260-day window and its proxy in the 1300-day window
  When the VaR status is requested
  Then "Equity B" is reported as "actual" for 1Y and "proxied" for 5Y, with its proxy, mode and scale

Scenario: Status for an account never calculated
  Given account "test-portfolio" has a ladder but no VaR run has ever completed
  When the VaR status is requested
  Then it reports no computed range, every ladder date as missing, and no last run

Scenario: Extreme returns are reported as warnings
  Given the outlier threshold is 25% and "Equity A" has an observed return of +40% on 2026-02-10
  When a run completes
  Then the run and the status both list a warning for "Equity A" on 2026-02-10
  And the return is still used unless it is on the exclusion list

Scenario: Excluded bad prices are treated as missing
  Given the exclusion list contains "Equity A" on 2026-02-10 and "Equity A" has a proxy
  When an estimate whose window includes 2026-02-10 is computed
  Then "Equity A" uses its proxy's return for scenario day 2026-02-10
```

---

### User Story 7 - Refresh VaR From the Pipeline Scripts (Priority: P3)

The account owner wants VaR refreshed as part of the existing end-to-end pipeline, and to be able to
refresh it on its own without rerunning everything.

**Why this priority**: Convenience on top of the run endpoint; runs can always be triggered by hand.

**Independent Test**: Run the end-to-end pipeline and confirm a VaR phase runs after capital
ingestion, waits for each account's run, and logs the outcome; run the standalone refresh script and
confirm the same.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The end-to-end pipeline refreshes VaR after capital ingestion
  Given the end-to-end pipeline has ingested the ladders and capital ledgers
  When the VaR phase runs
  Then a "missing" run is requested for each ingested account and waited on until it finishes
  And each account's dates computed and warnings are logged
  And a failed or timed-out VaR run is logged as a failure but does not stop the browser from starting

Scenario: The standalone refresh script refreshes every account
  Given the services are running
  When the refresh script is run
  Then a "missing" run is requested and waited on for each account
  And the script exits with a non-zero status if any run failed or timed out
```

---

### Edge Cases

- **Account with only Cash on a date**: risky market value is zero; VaR and ES are 0 GBP with quality
  "ok" and coverage reported as 100% actual.
- **Positions worth zero** (e.g. a suspended fund priced at zero) are excluded from the holdings for
  that date and never cause a division by zero.
- **Two positions sharing one instrument identifier** share one return series but remain separate
  positions with their own market values.
- **First observed price of an instrument**: the return into its first observed price is never used
  as a scenario return, because the previous price would not be a real observation.
- **Instrument not observed on a scenario day within its observed history** (e.g. a market holiday):
  its return for that day is zero, and its next observed return spans the gap.
- **Look-back window longer than any available history**: scenario days with no data for any position
  are excluded; if the remaining scenario count is below the configured minimum share of the window,
  the estimate is "insufficient".
- **Proxy itself missing a return** on a scenario day: that position falls back to the rescale
  treatment for that day.
- **Proxy not resolvable** (unknown identifier): treated as no proxy, and a warning is recorded.
- **Every risky position missing on a scenario day**: that day is excluded (the observed-share rule
  already excludes it).
- **Short history inside a long window** (e.g. 1 year of daily prices in a 5-year window): the
  instrument keeps its own returns for the year it has and is proxied or rescaled only before its
  first price; it is not classed as sparse.
- **Proxied positions and scenario exclusion**: a position using its proxy on a day counts as observed
  when the proxy was observed, so heavy proxy use does not cause valid scenario days to be dropped.
- **Very small scenario counts**: k never falls below 1 and never exceeds n; the integer formula keeps
  it in range for any n ≥ 1.
- **Next business day not yet in the ladder**: outcome is pending, never estimated or zero-filled.
- **Market data service lacks observed-only history support**: the run fails with a clear reason; it
  never falls back to gap-filled prices.
- **Ladder deleted and re-ingested**: if the account's store is removed with it, the next "missing"
  run recomputes everything; otherwise only dates whose holdings changed are recomputed.
- **Run requested while the same account's run is queued**: rejected with 409, like a running one.

## Requirements *(mandatory)*

### Functional Requirements

**Scenarios and estimates**

- **FR-001**: For every business date in an account's position ladder (or in a run's requested range),
  the system MUST take the positions held at that date's close with a non-zero market value and their
  GBP market values from the ladder.
- **FR-002**: The system MUST compute each instrument's simple 1-day GBP return on each scenario day
  using only observed prices (no gap-filled or back-filled prices), as the price change from the
  instrument's previous observed price.
- **FR-003**: For each as-of date and look-back window of L business days ending on that date
  (inclusive), the scenario PnL for each scenario day MUST equal the sum over held positions of
  market value × scenario return. Cash MUST have a return of zero.
- **FR-004**: Scenario days on which less than a configurable share (default 50%) of the as-of date's
  risky market value had an observed return source MUST be excluded; the remaining count is the
  scenario count n. A position counts as observed on a day when the source used for it that day (its
  own price, or its proxy's price where the proxy is used) had a real observation; rescaled
  positions never count as observed.
- **FR-005**: The system MUST compute estimates for look-back windows of 260, 520 and 1300 business
  days by default (configurable), all from the same scenario history.
- **FR-006**: For each estimate and confidence level p in {95%, 97.5%, 99%} (configurable), VaR MUST
  be the k-th largest scenario loss with k = n − ⌈n·p⌉ + 1, computed with exact integer arithmetic,
  reported as a positive GBP amount.
- **FR-007**: For each estimate and confidence level, Expected Shortfall MUST be the empirical tail
  mean (1/m)·(sum of the ⌊m⌋ largest losses + (m − ⌊m⌋) × the next-largest loss), with
  m = n·(1 − p), reported as a positive GBP amount.

**Short and sparse histories**

- **FR-008**: Identifier mapping entries MUST accept three new optional fields: `var_proxy` (an
  identifier), `var_proxy_mode` (`fill_gaps`, the default, or `always`) and `var_proxy_scale`
  (a multiplier, default 1.0). Existing entries without them MUST behave as before.
- **FR-009**: Where an instrument has no observed return on a scenario day because the day is before
  its first observed price, or the return is on the exclusion list, and it has a proxy in
  `fill_gaps` mode, the system MUST use the proxy's observed return multiplied by the scale.
- **FR-010**: In `always` mode, and for any instrument that is sparsely priced in a window, the system
  MUST use the scaled proxy return for every scenario day in that window. An instrument is sparsely
  priced when its observed days are below a configurable share (default 80%) of the window's
  business days **on or after its first observed price** (days before its first price are a short
  history, handled by FR-009, not sparseness). A sparse instrument with no proxy MUST use the
  rescale treatment for the whole window.
- **FR-011**: Where a position still has no return for a scenario day, its scenario PnL MUST be its
  market value × the market-value-weighted mean return of the risky positions that do have a return
  that day.
- **FR-012**: Each estimate MUST record the scenario count and the percentage of risky market value
  whose returns were all actual, that used any proxy return, and that used any rescaled return
  (rescaled takes precedence over proxied when both apply).
- **FR-013**: Each estimate MUST carry a quality flag using configurable thresholds:
  "insufficient" when n is below 80% of L or rescaled exceeds 20%; otherwise "degraded" when rescaled
  exceeds 5% or proxied exceeds 25%; otherwise "ok". Insufficient estimates MUST be stored with a
  reason and without VaR or ES values.

**Realised outcomes**

- **FR-014**: For each as-of date the system MUST store the outcome date (the next business day) and
  the hypothetical PnL: sum over the as-of holdings of market value × the instrument's observed return
  on the outcome date (zero if not observed that day).
- **FR-015**: For each as-of date the system MUST store the ladder PnL: the daily portfolio return
  used by the performance endpoints for the outcome date × the as-of date's total market value
  (including Cash).
- **FR-016**: When the outcome date is beyond the ladder's last date, the outcome MUST be stored as
  pending (no values), and a later run MUST fill it once the date is available.

**Runs**

- **FR-017**: The system MUST accept `POST /v1/accounts/{account}/risk/var/runs` with a mode
  (`missing` or `full`) and optional start and end dates, and respond 202 Accepted with the run
  resource and its location without waiting for the calculation.
- **FR-018**: The system MUST execute runs in the background one at a time across all accounts, in
  the order requested.
- **FR-019**: The system MUST reject a run request with 409 Conflict when the account already has a
  queued or running run, linking to that run.
- **FR-020**: `GET /v1/accounts/{account}/risk/var/runs/{run_id}` MUST return the run's mode,
  requested range, status (queued, running, succeeded, failed), request, start and finish times,
  number of dates computed and skipped (ladder dates in the run's range that did not need
  computing), warnings, and, for a failed run, a problem description.
  `GET /v1/accounts/{account}/risk/var/runs` MUST list the account's runs, newest first.
- **FR-021**: In `missing` mode, a run MUST compute only dates that have no estimate, whose stored
  fingerprint no longer matches, or whose outcome is pending. The fingerprint covers the methodology
  version, the VaR configuration, the proxy configuration and that date's holdings (each position's
  identifier and market value to the penny). In `full` mode, a run MUST compute every date in range.
- **FR-022**: A run MUST write its results so that the store is never left partially updated: either
  all of a run's results are saved, or none are.
- **FR-023**: Results MUST be kept per account under the account's data directory, in a
  human-readable form, with one estimate per (date, look-back) and one outcome per date; a recomputed
  date replaces its previous values.
- **FR-024**: On service start-up, any run still recorded as queued or running MUST be marked failed
  with reason "interrupted".
- **FR-025**: Invalid run requests (unknown mode, start after end, invalid account name) MUST be
  rejected with 422; unknown accounts, accounts without a position ladder, and unknown run
  identifiers MUST be reported with the same problem-details conventions as the existing risk and
  performance endpoints.
- **FR-026**: If the market data service cannot supply observed-only history, or is unavailable, the
  run MUST fail with a problem description naming the cause and MUST NOT fall back to gap-filled
  prices.

**Status and data hygiene**

- **FR-027**: `GET /v1/accounts/{account}/risk/var/status` MUST report the ladder's date range, the
  computed date range, the counts of missing dates, stale dates and pending outcomes (stale as found
  by the most recent run), a summary of the last run, and, for each instrument held in the computed
  range, its identifier, first observed date, proxy settings and treatment (actual, proxied,
  rescaled) per look-back as of the last run.
- **FR-028**: Any instrument return whose absolute value exceeds a configurable threshold (default
  25%) MUST be listed as a warning (instrument, date, return) on the run and in the status; it is
  still used unless excluded.
- **FR-029**: The configuration MUST support an exclusion list of (instrument, date) prices; excluded
  returns are treated as missing (proxy, then rescale).
- **FR-030**: Every resource in this feature MUST include `_links` (at least `self`, plus the run,
  status and account links as relevant), and the system MUST log run start, each stage's duration,
  instrument treatments, outlier warnings and run completion or failure as structured events.
- **FR-033**: Every error response introduced by this feature MUST include the request's correlation
  ID alongside the standard problem-details fields. Every run MUST record the correlation ID of the
  request that created it, and a failed run's problem description MUST include that correlation ID
  and the run identifier, so background failures can be traced to the originating request and logs.

**Scripts**

- **FR-031**: The end-to-end pipeline script MUST gain a VaR phase after capital ingestion and before
  the browser starts, which requests a `missing` run for each ingested account and polls it until it
  finishes or a configurable timeout (default 15 minutes) passes, logging dates computed and
  warnings. A failure or timeout MUST be logged and counted as an overall failure without stopping
  the browser from starting.
- **FR-032**: A standalone refresh script MUST do the same for all accounts (or the accounts named),
  and exit with a non-zero status if any run fails or times out.

### Key Entities

- **Exposure**: The positions an account holds at a date's close — each position's sub-account,
  instrument identifier and GBP market value — plus the total and risky market value.
- **Scenario Day**: A historical business day in a look-back window, with each instrument's return
  and how it was obtained (actual, proxied, rescaled), or excluded for low observed coverage.
- **VaR Estimate**: For an account, as-of date and look-back: scenario count, VaR and ES at each
  confidence level (GBP), coverage percentages, quality flag and reason, fingerprint and computation
  time.
- **Realised Outcome**: For an account and as-of date: outcome date, hypothetical PnL, ladder PnL, or
  pending.
- **VaR Run**: A request to calculate an account's VaR: mode, requested range, status, timings,
  counts, warnings and any failure description.
- **Proxy Configuration**: Per instrument: proxy identifier, mode and scale.
- **Instrument History Summary**: Per instrument: first and last observed dates and treatment per
  look-back as of the last run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every hand-calculated reference case in the acceptance scenarios, stored VaR, ES,
  scenario PnL, coverage and outcome values match exactly (integers) or within 1e-9 relative
  tolerance (decimals).
- **SC-002**: Requesting a run is acknowledged in under 1 second, regardless of how much history the
  run will process.
- **SC-003**: Once the required price history is available locally, a full run for an account with
  about 10 years of daily history and about 50 positions finishes in under 60 seconds.
- **SC-004**: A `missing` run with nothing changed since the previous run recomputes 0 dates and
  finishes in under 15 seconds.
- **SC-005**: 100% of stored estimates carry a scenario count, coverage percentages and a quality
  flag; no estimate is ever computed from gap-filled prices.
- **SC-006**: After any service restart, 0 runs remain in a queued or running state.
- **SC-007**: The status for an account is returned in under 2 seconds.
- **SC-008**: The end-to-end pipeline produces VaR estimates for every ingested account with no
  manual steps.

## Assumptions

- **Dependency**: market-data-web-service provides observed-only price history (`fill=none`) and an
  instrument's first observed date, delivered by its feature `009-observed-price-history`. Until then,
  runs fail as in FR-026.
- Methodology follows `docs/proposals/value-at-risk.md` §3 and §5; decisions D1–D4 there are settled
  (configured proxies, market-data extension, per-account VaR now, Scottish Widows Pension proxied by
  BlackRock Consensus 85 at scale 1.0).
- A business day is Mon–Fri, as in the ladder; there is no holiday calendar beyond the observed-share
  exclusion in FR-004. 1 year = 260 business days, as in the performance endpoints.
- Coverage percentages and the observed-share rule use **risky** (non-Cash) market value as the
  denominator; reported VaR percentages in later features use **total** market value.
- Proxy returns are GBP returns of the proxy's observed prices; a proxy may itself be any identifier
  the market data service can price, including ones not held.
- "Sparse" is judged per instrument per window; the default observed-share threshold is 80%.
- The store lives under each account's data directory, so deleting the account's data also deletes
  its VaR results; recomputation is then automatic on the next `missing` run.
- Results are stored as plain CSV and JSON files alongside the existing ladder files; no new storage
  technology or dependency is introduced.
- Restated historical prices (e.g. dividend adjustments in the data source) are not detected by the
  fingerprint; a `full` run is the remedy.
- Read endpoints for the VaR time series and backtesting, and the browser UI, are separate features
  (013 and 026); incremental/component VaR and combined accounts are out of scope.
- The refresh script lives alongside `run_end_to_end.ps1` at the repository root and uses the same
  service address configuration.
- Authentication, authorisation and error-response conventions follow the existing endpoints.
