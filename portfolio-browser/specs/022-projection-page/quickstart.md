# Quickstart: Projection Page (replaces Income)

## Prerequisites

1. `portfolio-browser` set up per `specs/015-create-template-python/quickstart.md`.
2. **This feature's backend capability does not exist yet** (spec Assumptions;
   `research.md`/`contracts/portfolio-analysis-api.md`). Until
   `GET /v1/accounts/{account_name}/projection` is implemented in `portfolio-analysis-service`,
   run against the fake client used by the unit/BDD test suite rather than a live service —
   there is no live-service verification step in this quickstart, unlike 021's, for exactly
   that reason.
3. At least one account with several years of recorded history, to exercise the horizon
   buttons and the "insufficient history for a return" omission rule (FR-012) meaningfully.

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps; safe to re-run
```

## 1. Income is gone, Projection is in its place

```powershell
.venv\Scripts\python -m pytest tests/unit/test_navigation.py -k projection -v
```

Open `http://127.0.0.1:8050` (once `app.py` is run) and check the nav bar: no "Income" entry
anywhere; "Projection" occupies the 4th position, same as "Income" always did.

## 2. A preset horizon button projects forward

On the Projection page, for an account with 5+ years of history: toggle on the "5Y" return,
click "10Y". The chart shows:

- one "Historical" line from the account's earliest record through its most recent record
  (the default start date).
- one "5Y" projected line continuing from that point to ten years past the start date.

## 3. Each horizon resolves relative to the *start* date, not always today

Move the start date back (say, two years), then click "10Y" again — the projected line now
ends ten years after that earlier start date, eight years from today, not ten years from
today. This is the deliberate "horizons are counted from the current start date" behaviour
flagged in the spec's checklist.

## 4. The calendar picker offers any date; a bad pick is rejected with a message, not silently

Pick a date five and a half years out — the projected line ends exactly there. Now try to pick
a date on or before the current start date: it's rejected, an inline message appears next to
the calendar control, and the chart keeps showing the last valid projection (FR-014).

## 5. Multiple returns, multiple distinguishable lines

Toggle on "3Y" and "5Y" together, click "10Y": two projected lines, both starting at the same
point (the start date's market value), each a distinct color, diverging as they run out to the
same end date.

## 6. A return with too little history is silently skipped

For an account with under three years of history, toggle on "3Y": no "3Y" line appears, no
error — the historical line (and any other selected, computable return) still renders
normally (FR-012).

## 7. Zero returns selected still shows something

Toggle every return off: the chart still shows the historical line alone — not an empty-state
message (FR-013, confirmed by this feature's own `/speckit-clarify` session).

## 8. Switching accounts resets everything

Pick a different account: start date, projection target and selected returns all revert to
that account's own defaults (FR-015), same as every other page's account-switch behaviour.

## 9. Run the tests

```powershell
.venv\Scripts\python -m pytest tests/unit -q
.venv\Scripts\python -m pytest tests/unit/test_projection_page.py -v
.venv\Scripts\python -m pytest tests/unit/test_callback_registration.py -v
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy config src app.py
```

BDD scenarios (`tests/bdd/features/projection_page.feature`) follow the same
Chrome-availability auto-skip as every other BDD feature in this repo (see
`tests/bdd/conftest.py`, closed out in the 021 follow-up) — they run for real wherever
Chrome/chromedriver are present, and report `skipped` (not failed, not hung) otherwise.

```powershell
.venv\Scripts\python -m pytest tests/bdd --headless
```
