# Quickstart: Date Range Shortcut Buttons on Overview

No new setup beyond `016-link-real-portfolio`'s own quickstart — this
feature adds no dependency, no config, no new backing-service requirement.

## Setup

```bash
cd portfolio-browser
.venv/Scripts/python -m pip install -e ".[dev]"   # no new deps vs. 016; safe to re-run
```

## Prerequisite

Same as 016: a running, populated `portfolio-analysis-service` instance
(see `specs/016-link-real-portfolio/quickstart.md`'s "Prerequisite"
section) for the manual walkthrough below.

## Run

```bash
.venv/Scripts/python app.py
```

Open `http://127.0.0.1:8050` (Overview loads by default). Once the chart's
default view has finished loading, you should see five new buttons — "YtD",
"1Y", "3Y", "5Y", "All" — next to the existing Account/From/To controls.

Manually verify each user story:

- **US1**: Click "YtD" — "from" should jump to 1st January of the current
  year, "to" stays at the existing last-completed-business-day default, and
  the chart re-renders to that range. Repeat for "1Y", "3Y", "5Y" and
  confirm each computes the expected offset from today.
- **US2**: Click "All" — "from" should jump to the selected account's
  earliest recorded date (compare against what "from" defaulted to when
  that account was first selected) and the chart shows the account's full
  history. Switch accounts, click "All" again, and confirm it now reflects
  the *new* account's earliest date, not the previous one's.
- **FR-013 (button disabling)**: Click any shortcut and, while the chart is
  visibly refreshing (`dcc.Loading` spinner active), try clicking another
  shortcut — it should have no effect until the first refresh completes,
  then become clickable again.
- **FR-008 (clamping)**: If you have (or can find) an account with less
  history than 5 years, click "5Y" on it and confirm the chart shows that
  account's *complete* history (clamped), not an error or a truncated
  request.

## Test

```bash
.venv/Scripts/python -m pytest tests/unit           # extends 016's test_overview_chart_shaping.py with _shortcut_from_date cases
.venv/Scripts/python -m pytest tests/bdd             # new overview_date_range_shortcuts.feature, plus all of 015/016's existing scenarios (regression)
```

Same Chrome/Chromium requirement as 015/016's `tests/bdd` — see those
quickstarts' notes if `pytest tests/bdd` fails at browser-launch time.

## Static analysis

```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy .
```

## Validating this feature against the spec

- User Story 1 (YtD/1Y/3Y/5Y) → `tests/bdd/features/overview_date_range_shortcuts.feature`
- User Story 2 (All) → same file
- FR-013 (disabled during refresh) → same file

All scenarios MUST pass, `ruff`/`mypy` MUST run clean, and the manual
walkthrough above MUST match before this feature is considered complete —
in addition to 015's and 016's own quickstart validations still passing
(regression), since this feature only extends already-shipped files.
