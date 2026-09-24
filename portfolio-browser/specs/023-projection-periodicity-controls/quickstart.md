# Quickstart: Projection Periodicity Control

## Run the app

```bash
.venv/Scripts/python app.py
```

Open the Projection page, pick an account, click a horizon (e.g. "20Y").

## Verify manually

1. The parameters bar shows **Periodicity** with day / week / month / quarter / year, matching Overview.
2. With a 20Y horizon and no click yet, "year" is highlighted; click "1Y" horizon and the
   highlight moves to the interval for that span, without touching the control.
3. Click "month": the chart redraws monthly; click "20Y" again — "month" stays.
4. Switch account — "month" stays; the target and return toggles reset as before.
5. While the chart is loading, the interval buttons are disabled.

## Run the tests

```bash
python -m pytest tests/unit/test_projection_page.py tests/unit/test_callback_registration.py
python -m pytest tests/bdd -k "projection"    # needs Chrome
ruff check . && mypy .
```
