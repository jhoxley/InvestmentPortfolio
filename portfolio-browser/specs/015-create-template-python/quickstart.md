# Quickstart: Dash Application Shell

## Setup

```bash
cd portfolio-browser
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

## Configure

Copy `.env.example` to `.env` and adjust host/port/debug if needed:

```bash
cp .env.example .env
```

Edit `config/content.yaml` to change the app name, version, published date,
or navigation section labels — these are validated at startup, so a
malformed entry (e.g. two sections marked `is_default: true`) fails fast
with a clear error rather than rendering a broken page.

## Run

```bash
.venv/Scripts/python app.py
```

Then open the printed local URL (default `http://127.0.0.1:8050`) in a
browser. You should see:
- A header reading "Investment Portfolio Browser"
- A left-hand nav menu (≤20% width) with "Overview" selected by default
- A content area with a parameters/controls placeholder bar above the
  Overview page's placeholder content
- A footer showing the configured version and published date

Click other nav items (Positions, Performance, Income) to confirm the
content area updates without a full page reload, and that header/footer/nav
stay in place.

## Test

```bash
.venv/Scripts/python -m pytest tests/unit           # config validation unit tests
.venv/Scripts/python -m pytest tests/bdd             # Gherkin/BDD shell scenarios (spins up a real browser via dash_duo)
```

`tests/bdd` requires Chrome or Firefox to be installed (Dash's `dash.testing`
browser fixture only supports those two — Microsoft Edge is not supported,
even though it is Chromium-based, because its driver rejects the
`browserName: chrome` capability Dash sends). If neither is installed,
`pytest tests/bdd` will fail at browser-launch time with a
`WebDriverException`/`SessionNotCreatedException` regardless of whether the
app code is correct. See T033 for headless Chrome CI configuration.

## Static analysis

```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy .
```

## Validating this feature against the spec

- User Story 1 (shell) → `tests/bdd/features/application_shell.feature`
- User Story 2 (navigation) → `tests/bdd/features/section_navigation.feature`
- User Story 3 (footer build info) → `tests/bdd/features/build_info_footer.feature`

All three MUST pass, `ruff`/`mypy` MUST run clean, and the manual walkthrough
above MUST match before this feature is considered complete.
