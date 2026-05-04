# Research: Security Pricing API

**Feature**: 001-security-pricing-api
**Date**: 2026-05-04
**Status**: Complete — all unknowns resolved

---

## Decision 1: Web Framework

**Decision**: FastAPI (Python)

**Rationale**: FastAPI is specified directly by the user and is the right choice for this project. It provides:
- Automatic OpenAPI/Swagger schema generation from Pydantic models (satisfies Principle VI)
- Async-first design compatible with I/O-bound yfinance calls
- Built-in request validation via Pydantic (satisfies FR-005 validation requirements)
- Interactive Swagger UI at `/docs` with zero additional configuration (satisfies FR-010)
- Type annotation enforcement aligns with Principle IV (mypy strict mode)

**Alternatives considered**: Flask (no built-in OpenAPI), Django REST Framework (heavier, not needed for a local single-service tool).

---

## Decision 2: Data Provider

**Decision**: `yfinance` package — direct use via a dedicated provider module

**Rationale**: Specified by the user and the only requirement. `yfinance` wraps the Yahoo Finance API and returns pandas DataFrames with OHLCV data. Key behaviours to handle in the provider layer:
- `yfinance.Ticker(ticker).fast_info` — fastest path for current price
- `yfinance.Ticker(ticker).history(start=..., end=...)` — returns DataFrame for historical series
- Zero prices are possible for delisted/unknown tickers — must be filtered (FR-006)
- Network failures raise exceptions — must be caught and mapped to 503 responses (FR-005)

**Alternatives considered**: Direct Yahoo Finance HTTP calls (fragile, no library support), other data providers (out of scope per spec).

---

## Decision 3: BDD Testing Framework

**Decision**: `pytest-bdd` with `pytest` as the test runner

**Rationale**: `pytest-bdd` implements Gherkin scenario execution within the standard pytest ecosystem. This means:
- `.feature` files use standard Gherkin syntax matching the spec scenarios
- Step definitions are Python functions decorated with `@given`, `@when`, `@then`
- Tests are run with `pytest tests/` — a single CLI command (satisfies user requirement for CLI-executable BDD tests)
- The `httpx` library (with `TestClient` from FastAPI) is used for end-to-end HTTP calls within BDD steps
- All Gherkin scenarios from the spec map directly to `.feature` files

**Alternatives considered**: `behave` (separate runner, less pytest integration), `radish` (niche, small community).

---

## Decision 4: Structured Logging

**Decision**: `structlog` with JSON output to both console and rotating file

**Rationale**: `structlog` is the industry-standard structured logging library for Python. It provides:
- JSON-formatted log entries out of the box
- Context binding (attach `ticker`, `endpoint`, `duration` to all log entries within a request)
- Compatible with Python's `logging` stdlib (can be used alongside FastAPI's default logging)
- Log files written to a configurable `logs/` directory; log rotation via `logging.handlers.RotatingFileHandler`

**Alternatives considered**: Python stdlib `logging` + manual JSON formatting (verbose, error-prone), `loguru` (good, but structlog more widely adopted for structured JSON).

---

## Decision 5: Linting and Static Analysis

**Decision**: `ruff` (linting + formatting) + `mypy` (type checking), configured in `pyproject.toml`

**Rationale**:
- `ruff` replaces `flake8`, `isort`, `black` with a single fast tool; single config in `pyproject.toml` (Principle IV)
- `mypy` in strict mode enforces the type annotations required by FastAPI/Pydantic
- Both tools run in the same command (`ruff check . && mypy app/`) for pre-commit and CI gates

**Alternatives considered**: `flake8` + `black` (two tools, more config); `pylint` (slower, more opinionated).

---

## Decision 6: No Caching in v1

**Decision**: All data fetched live from yfinance on each request; no local cache

**Rationale**: Matches spec assumption. Simplifies the implementation significantly. The performance targets (SC-001: < 3s for current price, SC-002: < 5s for 12 months history) are achievable via direct yfinance calls under normal network conditions. Caching can be added in a future version if needed.

**Alternatives considered**: In-memory cache with TTL (adds complexity, unnecessary for single-user local tool), parquet file cache (already used in the parent portfolio tool — over-engineered for this service).

---

## Decision 7: OpenAPI Contract Strategy

**Decision**: FastAPI auto-generates the OpenAPI schema at runtime; the schema is also exported to `openapi.yaml` and committed to the repository

**Rationale**: FastAPI generates a fully compliant OpenAPI 3.1.0 schema from Pydantic models automatically, which means the code *is* the contract — no drift. The `openapi.yaml` file is generated once at project init via `python -c "..."` and committed so it is available for review and tooling without running the server.

**Process**: `openapi.yaml` (the initial contract skeleton) is authored and committed before endpoint implementation begins, satisfying Principle VI. FastAPI runtime schema at `/openapi.json` serves as the live, always-accurate version.
