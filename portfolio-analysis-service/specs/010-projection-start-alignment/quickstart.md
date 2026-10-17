# Quickstart: Projection Start Alignment

## Verify manually

```bash
.venv/Scripts/python -m uvicorn app.main:app
curl "http://127.0.0.1:8000/v1/accounts/HL-ISA/projection?projection_date=2026-12-31&return=3Y&start=2026-09-22&periodicity=month"
```

Expected: the `3Y` entries start at `2026-10-01` (no `2026-09-22`); `Historical` still ends at
`2026-09-01`. Repeat with `periodicity=day` — `3Y` still starts at `2026-09-22`; and with
`start=2026-10-01&periodicity=month` — `3Y` starts at `2026-10-01`.

## Run tests

```bash
.venv/Scripts/python -m pytest tests/unit/test_projection_service.py tests/steps/retrieve_projection_steps.py
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check . && .venv/Scripts/python -m mypy --strict app
```

Write the new tests first and confirm they fail before changing `projection_service.py`.
