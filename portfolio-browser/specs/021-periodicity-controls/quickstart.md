# Quickstart: Periodicity Control for Overview & Positions

## Prerequisites

1. `portfolio-browser` set up per `specs/015-create-template-python/quickstart.md`
   (`.venv` created, `pip install -e ".[dev]"`).
2. **A `portfolio-analysis-service` instance running its feature-008 code.** This is the one
   prerequisite that needs checking rather than assuming — see the verification step below.
3. At least one account with an ingested capital ledger and/or position ladder covering **more
   than five years**, so the derived-interval rules are actually exercised (`HL-SIPP` from
   2016-04-20 and `HL-ISA` from 2018-07-12 both qualify).

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps; safe to re-run
```

## 0. Verify the analysis service actually supports periodicity

Do this first. A service process started before feature 008 **silently ignores** the parameter —
it returns daily data with no error, so the UI would appear to work while plotting the wrong thing.

```bash
curl -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/timeseries?attribute=capital&start=2016-04-20&end=2025-12-31&periodicity=annual" \
  | head -c 200
```

| What you see | Meaning |
|---|---|
| `"periodicity":"annual"` and ~10 entries | ✅ good to go |
| no `periodicity` key, entries one business day apart | ❌ the service predates 008 — **restart it** |

A second, quicker tell: `?periodicity=fortnight` must return **422**. If it returns 200, the
service is the old build.

```bash
# restart from the analysis service directory if needed
cd ../portfolio-analysis-service
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Run

```bash
cd portfolio-browser
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050`.

## 1. The control, on both pages

On **Overview** and again on **Positions**, the parameters bar at the top now ends with a
"Periodicity" label and five buttons:

```text
Account [HL-SIPP ▾]  From [2016-04-20]  To [2026-09-21]  [YtD][1Y][3Y][5Y][All]
Periodicity  [day][week][month][quarter][ year ]
                                          ^^^^ highlighted = in effect
```

Exactly one button is ever highlighted, and it always matches what the chart is plotted at.

## 2. Long ranges are readable without touching anything

Select an account with more than five years of history. With the range at that account's full
history, the chart is plotted **annually** — about ten points rather than ~2,600 — and the `year`
button is highlighted, without you having clicked anything.

Click through the date-range shortcuts and watch the interval follow:

| Shortcut | Span | Interval derived |
|---|---|---|
| `YtD` | under a year | `day` |
| `1Y` | exactly 1 year | `day` |
| `3Y` | exactly 3 years | `month` |
| `5Y` | exactly 5 years | `quarter` |
| `All` | > 5 years | `year` |

Note `1Y`, `3Y` and `5Y` land exactly on a boundary, and each resolves to the **finer** interval —
that is deliberate (spec Assumptions), so a boundary span never loses detail.

## 3. Your choice sticks

Click `month`. Now click the `All` shortcut. The range widens to the full history and the chart
**stays monthly** — your explicit choice is not overridden (FR-012). Switch accounts: still
monthly.

This is the one behaviour worth understanding: automatic derivation applies only until you first
touch the control. After that it is yours until you change it again. A consequence: clicking `day`
and then `All` gives you a dense ~2,600-point chart — which is exactly what the page did before
this feature existed, so it is not a regression, merely not auto-rescued.

To get back to automatic behaviour, reload the page (the choice is scoped to the page visit).

## 4. Check "year" really means annual on the wire

```bash
# with the app's own logs visible, click "year" and look for the outbound request
# or query the service directly:
curl -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/timeseries?attribute=capital&start=2016-04-20&end=2025-12-31&periodicity=annual" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['periodicity'], len(d['entries']))"
# -> annual 10
```

The UI shows `year` because it reads better beside day/week/month/quarter; the service's own name
for that interval is `annual`. That mapping is data, in `config/content.yaml`, not code.

## 5. Positions specifics

- Each position is aggregated independently, and every position shares the same window dates — so
  the **stacked area graph** still stacks correctly at `month`/`quarter`/`year`.
- ⚠️ `position_return` and `weighted_position_return` at a coarse interval show the **last
  single-day return** in each period, **not** a compounded period return. That is the analysis
  service's documented behaviour and this UI deliberately does not re-derive it (Principle I).
  Treat those two attributes as daily samples, not period performance.

## 6. Run the tests

```powershell
.venv\Scripts\python -m pytest tests/unit -q            # browser-free; covers the rules
.venv\Scripts\python -m pytest tests/unit/test_periodicity_derivation.py -v
.venv\Scripts\python -m pytest tests/unit/test_callback_registration.py -v   # no dropped callbacks
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy config src app.py
```

BDD scenarios (`tests/bdd/features/overview_periodicity.feature`,
`overview_periodicity_defaults.feature`, `positions_periodicity.feature`) need **Chrome
installed** — `dash[testing]` drives a real browser:

```powershell
.venv\Scripts\python -m pytest tests/bdd --headless
```

`tests/bdd/conftest.py` auto-detects whether a Chrome/Chromium browser and chromedriver are both
present. Where they are, the scenarios run for real. Where they aren't (this includes every
environment this feature has been developed and verified in so far), every BDD item is
automatically marked `skipped` — deterministically, not a hang or a failure — so a bare `pytest`
always exits 0 regardless of whether a browser is installed. The unit suite above covers the
derivation rule, the config schema, the control's structure, the query-parameter plumbing, and
the callback registry without needing a browser at all.
