# Phase 0 Research: Periodicity Control for Overview & Positions

**Feature**: `021-periodicity-controls` | **Date**: 2026-09-22

The spec carried no `[NEEDS CLARIFICATION]` markers into planning — its single ambiguity (whether
an explicit choice is sticky) was settled with the requester during `/speckit-specify` and is
recorded in spec.md's Clarifications. The research below resolves the *technical* unknowns, each
checked against the running code or services rather than assumed.

---

## 1. Which control widget can express "the user chose this"?

**Decision**: a `dbc.ButtonGroup` of five `dbc.Button`s, driven by `n_clicks`, with the active
interval shown by toggling each button's `outline`/`active` styling.

**Rationale**: FR-012 makes the code's ability to distinguish a user choice from a system-derived
one load-bearing. Dash fires the callbacks listening on a prop identically whether a human changed
it or another callback wrote it — this codebase already relies on that chaining behaviour, where
`overview.py::_sync_date_range_to_selected_account` writes `app-parameters-from-date.date` and
`_render_chart` fires off the write. So a `value`-only control cannot report intent; it can only
be *inferred* by comparing against the last value the system wrote, which means holding that value
in a store and depending on callback execution order for the comparison to be valid.

`n_clicks` carries no such ambiguity: it increments only on a real click, so "the user chose an
interval" is a fact the framework hands us. The sticky latch then becomes a one-line store write
with no ordering assumptions, and the derivation path never has to guess whether it is looking at
its own echo.

A secondary benefit: the parameters bar already renders the five date-range shortcuts as a
`ButtonGroup` immediately beside where this control goes, so five interval buttons read as part of
the existing design rather than as a new kind of control.

**Alternatives considered**:

- **`dbc.Select` dropdown** — rejected. Compact, and the obvious first choice, but it forces the
  last-written-value/pending-flag pattern described above. Worth noting a *false* reason not to
  use it: it was initially assumed Dash rejects a callback with the same component+prop as both
  Input and Output, which would have ruled out the single-callback compare pattern outright. Tested
  against the installed Dash 4.4.0 — such a callback is **accepted** at setup with no
  circular-dependency error. The decision therefore rests on the ambiguity of `value`, not on a
  framework prohibition.
- **`dbc.RadioItems` (inline)** — rejected for the same reason as `Select`: its only signal is
  `value`.
- **A sixth "Auto" option** — rejected during `/speckit-specify`; the requester chose exactly five
  options, and "Auto" would have made stickiness explicit at the cost of contradicting FR-002.
- **Compare-against-derived instead of a latch** (mark a choice explicit only when it differs from
  what derivation would produce) — rejected. It silently fails the case where a user deliberately
  selects the interval that derivation already chose: their choice would not latch, and the next
  date-range change would move it, violating FR-012.

**Trade-off accepted**: five buttons occupy more horizontal room than a dropdown. The parameters
bar is a `dbc.Row`, which wraps rather than clips, so the Positions bar (already the widest:
Account + From + To + shortcuts + stacked toggle + position filter) will wrap to a second line at
narrower widths. That satisfies the constitution's "no clipped content" UX standard; it is called
out here so it is a known consequence rather than a surprise in review.

---

## 2. Shared component IDs, or per-page IDs?

**Decision**: one shared *builder* (`build_periodicity_control(page_prefix, …)`) emitting
**per-page component ids** — `overview-parameters-periodicity-*` and
`positions-parameters-periodicity-*`.

**Rationale**: The existing shared controls deliberately reuse one id across routes
(`app-parameters-account`, …), on the reasoning — documented in `date_range_controls.py` — that
only one route's parameters bar is mounted at a time. That reasoning holds for the *DOM*, but not
for the *callback registry*: Dash derives an `allow_duplicate` Output's callback id by hashing the
callback's Inputs alone (`dash/_utils.py::create_callback_id`), so two pages declaring the same
Output from the same Inputs collapse into one registration and the last page imported silently
wins. That is exactly the defect found and fixed while closing feature 020, where **7 of 20
callback registrations were being discarded** and the Performance page's "ITD" shortcut was
running Positions' year-to-date mapping.

Per-page ids make that failure mode structurally impossible for this feature rather than merely
guarded against: each page's periodicity callbacks have distinct Outputs, so no hashing collision
can occur no matter what their Inputs are. The shared *UI* the spec asks for is delivered by
sharing the builder, which is what 018 actually meant by "shared controls".

**Alternatives considered**:

- **Shared ids plus a page-local scoping Input** (the 020 fix pattern) — workable, and the pattern
  is now established, but it buys nothing here and re-introduces a subtlety a future reader must
  understand. Prefer not creating the problem over remembering to work around it.
- **Shared ids with no scoping** — rejected: this is the 020 bug, reproduced deliberately.

**Backstop**: `tests/unit/test_callback_registration.py` (added while closing 020) asserts zero
callback registrations are overwritten at startup, and it needs no browser — so if anyone later
switches to shared ids without scoping, the unit suite fails immediately.

---

## 3. Where does the effective interval live?

**Decision**: a per-page `dcc.Store` holding `{"value": <interval>, "explicit": <bool>}`, written
by exactly two callbacks and read by everything else.

| Callback | Trigger | Behaviour |
|---|---|---|
| **click** | any of the five buttons' `n_clicks` | write `{value: clicked, explicit: true}` |
| **derive** | from-date / to-date change | if `explicit` → `PreventUpdate`; else write `{value: derived, explicit: false}` |
| **style** | store change | set each button's active/outline state from `store.value` |
| **render** (existing) | store change (new Input) + existing inputs | fetch and plot at `store.value` |

**Rationale**: One writer per concern and one reader-of-record means FR-011 ("the control always
shows the interval in effect") is true by construction — the buttons and the chart derive their
state from the same value, so they cannot disagree. The `explicit` latch is what implements
FR-012, and because it is only ever set by a click it can never be set by the system's own
derivation write.

**Alternatives considered**:

- **Two stores** (one for the value, one for the latch) — no benefit; a single dict keeps the two
  facts atomic in one write.
- **Deriving inside the render callback** and not storing at all — rejected: the buttons would then
  have nothing to read, so the control could not reliably display the effective interval, and the
  derive rule would run on every chart refresh rather than only on range changes.
- **Session/local storage persistence** (`dcc.Store(storage_type="session")`) — rejected as
  unrequested scope. The spec says nothing about a choice surviving a reload, and page-visit scope
  matches how every other control on these pages already behaves.

---

## 4. The derivation rule, and how a "span" is measured

**Decision**: a pure function
`derive_periodicity(from_date, to_date, thresholds) -> interval`, comparing `from_date` against
`to_date` offset back by each threshold in years, using
`date_range_controls.py::_years_before` — the helper the date-range shortcuts already use.

```
span ≤ 1 year   -> day
span ≤ 3 years  -> month
span ≤ 5 years  -> quarter
otherwise       -> year
```

**Rationale**: Reusing `_years_before` (rather than `span.days / 365.25` or a new helper) keeps
this feature's notion of "N years ago" byte-identical to the one the "1Y"/"3Y"/"5Y" shortcut
buttons already apply, including its documented leap-day fallback (29 Feb → 28 Feb). That matters
directly: clicking "5Y" must land exactly on the quarter/year boundary the rule expects, and it
does so only if both compute "five years before today" the same way. A day-count approximation
would make the boundary drift by a day or two across leap years and make the boundary tests
ambiguous.

Comparing with `<=` at each step implements the spec's "boundary belongs to the finer interval"
assumption without extra branching, and the "otherwise" arm means `week` is unreachable by
derivation (FR-009) simply because no threshold maps to it.

**Verified by execution** against the real helpers, with `today = 2026-09-22` and
`to_date = _last_business_day(today) = 2026-09-21`:

| Trigger | Resulting `from_date` | Derived |
|---|---|---|
| `YtD` shortcut | 2026-01-01 | `day` |
| `1Y` shortcut | 2025-09-22 | `day` |
| `3Y` shortcut | 2023-09-22 | `month` |
| `5Y` shortcut | 2021-09-22 | `quarter` |
| `All` on HL-SIPP | 2016-04-20 | `year` |

Exact-boundary spans confirm the finer interval wins: a span of exactly one year (2025-09-21) →
`day`, exactly three (2023-09-21) → `month`, exactly five (2021-09-21) → `quarter`. Degenerate
inputs return `day` without raising — both `from == to` and an inverted `from > to`.

Note the shortcut buttons compute their `from_date` from `today` while derivation compares against
`to_date` (= the last completed business day), so a "1Y" range is one year minus a day or two.
That lands comfortably inside the `day` band rather than teetering on the boundary, and the
inclusive comparison means the exact boundaries are well-defined regardless.

**Alternatives considered**:

- **`(to - from).days` against 365/366/1095/1826** — rejected: leap years make the boundary
  inexact and put it out of step with the shortcut buttons.
- **`dateutil.relativedelta`** — rejected: a new dependency for something a three-line stdlib
  helper already in the codebase does (Principle V favours standard libraries, and the standard
  here is the existing helper).
- **Deriving from the *account's* recorded history instead of the picked range** — rejected; the
  spec measures the effective picked range, which is also what the chart is drawn from.

---

## 5. Where the label, options and thresholds live

**Decision**: a new `periodicity:` section in `config/content.yaml`, validated fail-fast by the
existing typed `ContentConfig` loader. Option *keys* stay as module constants.

```yaml
periodicity:
  label: "Periodicity"
  options:
    - key: day
      label: day
      value: day
    - key: week
      label: week
      value: week
    - key: month
      label: month
      value: month
    - key: quarter
      label: quarter
      value: quarter
    - key: year
      label: year
      value: annual      # the service's own name for this interval
  thresholds:
    day_max_years: 1
    month_max_years: 3
    quarter_max_years: 5
```

**Rationale**: Principle IV names exactly these categories — "thresholds" and "labels used in more
than one place" — as things that MUST NOT be inlined, and both pages use these labels, so the
one-place test is met twice over. `content.yaml` + `ContentConfig` is the established mechanism
(`app_name`, `build_info`, `nav_sections` already live there with model validators), so this needs
no new machinery, and putting the `year → annual` mapping in data rather than code makes the one
label/value divergence visible at a glance.

Keeping the option *keys* as module constants follows the precedent
`date_range_controls.py` sets for its shortcut codes, which it documents as a "fixed, spec-defined
set — not user-configurable": code needs stable identifiers to branch on, and making those
editable would let a config edit break a callback.

**Validation to enforce at load**: exactly five options; unique keys, labels and values; thresholds
strictly ascending and positive; every threshold's target interval present in `options`. Failing
fast here turns a config typo into a startup error rather than a mis-plotted chart.

**Alternatives considered**:

- **Module constants for everything** — rejected: directly contravenes Principle IV for the
  thresholds and the shared labels.
- **`Settings` / `.env`** — rejected: that file is for environment-specific values (URLs, ports,
  timeouts). These are content/behaviour defaults, which is what `content.yaml` is for.
- **Fetching the option list from the service** (it publishes the enum in its OpenAPI) — rejected
  as over-engineering: it adds a startup HTTP dependency and a failure mode for a five-value list
  that changes approximately never, and the UI needs its own labels anyway (`year` ≠ `annual`).

---

## 6. Plumbing the parameter, and the deployed-service reality

**Decision**: add an optional `periodicity: str | None = None` argument to `get_timeseries()` and
`get_position_timeseries()` on both the client Protocol and the HTTP implementation, appended to
the existing params list only when set. Also capture the response's echoed `periodicity` on both
response models and log a warning when it is absent or differs from what was requested.

**Rationale**: Omitting the parameter when unset keeps every existing call site and test working
unchanged, and matches the service's own contract (008 treats an omitted parameter as `day`).

The echo check earns its place because of what the running environment showed. **Verified against
the live service on :8000**: it silently ignores `periodicity` — a request for
`periodicity=month` over 2016→2025 came back with **daily** entries, no `periodicity` field in the
body, and `periodicity=fortnight` returned **200** instead of the 422 that 008 specifies. That
service process predates the 008 implementation. So the dependency is real but not yet deployed:
the UI must be developed and tested against a **restarted** analysis service.

Against a pre-008 service the naive outcome is the worst kind of bug — the control would show
"year" while the chart plotted 2,608 daily points, with nothing anywhere saying the request was
ignored. Reading the echoed field (which 008 guarantees on every response, including `day`) turns
that silent mismatch into a logged warning, which is why the response models gain the field rather
than letting Pydantic drop it.

**Alternatives considered**:

- **Ignore the echo** — rejected for the silent-mismatch reason above.
- **Hard-fail or show an error state on mismatch** — rejected as out of proportion: the spec's
  Assumptions say the pages should continue to behave as they do today against a service without
  the capability, and a structured warning gives an operator the signal without breaking a
  usable chart.
- **Probe `/openapi.json` at startup to feature-detect** — rejected: a startup HTTP dependency and
  a second source of truth about the service's capabilities, when the per-response echo already
  tells us precisely what happened for the request we actually made.

---

## 7. Chart shaping: what changes?

**Decision**: nothing. `_overview_chart.py` and `_positions_chart.py` are untouched.

**Rationale**: 008 returns aggregated entries in the **same shape** as daily ones — the same `date`
key, the same dynamic attribute keys, and for positions the same `position` key — so the existing
figure builders plot them as-is. Verified by reading both: neither contains any resampling,
business-day, frequency or tick-spacing logic (no `bdate`/`freq`/`resample`/`dtick` anywhere), so
neither assumes a fixed point count, fixed spacing, or business-day continuity. The x-axis is
already a date axis, so coarser points simply land further apart.

Two specifics worth knowing:

- **Overview already draws `mode="lines+markers"`**, so ten annual points render as ten visible
  markers joined by lines rather than as an ambiguously sparse line. No styling change is needed
  for coarse intervals to read correctly.
- **Stacked mode on Positions works because of a guarantee 008 makes.** Plotly's `stackgroup`
  stacks traces by shared x value, so bands only align if every position reports the *same* window
  dates. 008 derives a window's date from the calendar period and the resolved range start alone —
  never from a position's own data — precisely so per-position series align. FR-014 therefore
  holds because of that upstream guarantee, not because of anything this feature does; if that
  guarantee ever regressed, stacked mode at coarse intervals is where it would show.

This is what keeps the feature small, and it is worth stating explicitly because the obvious
assumption — that coarser data needs different plotting code — is wrong here.

**Alternatives considered**:

- **Switching to bars at coarse intervals** (a column per period rather than a line) — arguably a
  better reading of period-level data, but unrequested, and Overview's existing markers already
  address the legibility concern. Noted as a possible follow-up rather than smuggled in.

---

## 8. Test strategy without a browser

**Decision**: author the BDD scenarios as the constitution requires, but deliberately place every
decidable rule behind a pure function or a registry assertion so the bulk of the feature is
verifiable without Chrome.

| Concern | Covered by | Needs a browser? |
|---|---|---|
| derivation rule, all thresholds + boundaries | `test_periodicity_derivation.py` | no |
| config schema + fail-fast validation | `test_content_config.py` | no |
| builder output: label, five options, order, per-page ids | `test_periodicity_controls.py` | no |
| `periodicity` reaches the query string; omitted when unset | `test_portfolio_analysis_client.py` | no |
| no callback registration is silently dropped | `test_callback_registration.py` | no |
| click → latch → chart re-render; styling; page parity | `periodicity_control.feature` | **yes** |

**Rationale**: Chrome is absent on the current machine, so `dash[testing]` cannot run here — the
same gap that let 020's collision ship. Pushing the rules into pure functions is not a workaround
for the missing browser so much as the correct design (Principle II keeps derivation free of I/O
anyway); the browser-free coverage is a consequence. The remaining browser-only scenarios are
genuinely about DOM interaction and must be signed off by a human or a CI runner that has Chrome.

**Alternatives considered**:

- **Driving the live app through Dash's `/_dash-update-component` HTTP endpoint**, as was done to
  verify 020's T022 — effective (it caught the real bug) and available as a fallback, but it
  hard-codes callback signatures and is not a substitute for asserting what a user actually sees.
  Recommended as a supplementary harness, not as the BDD suite.
- **Skipping BDD entirely given no browser** — not an option: Principle III is non-negotiable and
  the scenarios are the deliverable even when this machine cannot execute them.
