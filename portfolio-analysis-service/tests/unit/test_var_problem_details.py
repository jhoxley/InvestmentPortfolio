"""Unit tests for the VaR feature's RFC 7807 problem responses (FR-033, correlation_id)."""

import json

import structlog.contextvars
from starlette.requests import Request

from app.main import _var_problem


def _fake_request(path: str = "/v1/accounts/acct/risk/var/runs") -> Request:
    """Build a minimal Starlette Request with a given path, enough for _problem/_var_problem."""
    return Request(scope={"type": "http", "path": path, "headers": []})


class TestVarProblem:
    """_var_problem() extends the standard RFC 7807 fields with correlation_id."""

    def test_includes_correlation_id_from_bound_contextvars(self) -> None:
        """When a correlation_id is bound via structlog contextvars, it appears in the body."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id="corr-123")
        try:
            response = _var_problem(
                _fake_request(),
                409,
                "var-run-in-progress",
                "VaR Run In Progress",
                "Account 'acct' already has a run in progress.",
            )
        finally:
            structlog.contextvars.clear_contextvars()

        body = json.loads(response.body)
        assert body["correlation_id"] == "corr-123"
        assert body["type"] == "https://portfolio-analysis/errors/var-run-in-progress"
        assert body["status"] == 409

    def test_includes_extra_fields(self) -> None:
        """Extra fields (e.g. _links.active_run) are merged into the body."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id="corr-456")
        try:
            response = _var_problem(
                _fake_request(),
                409,
                "var-run-in-progress",
                "VaR Run In Progress",
                "detail",
                extra={"_links": {"active_run": "/v1/accounts/acct/risk/var/runs/r1"}},
            )
        finally:
            structlog.contextvars.clear_contextvars()

        body = json.loads(response.body)
        assert body["_links"]["active_run"] == "/v1/accounts/acct/risk/var/runs/r1"

    def test_missing_correlation_id_defaults_to_empty_string(self) -> None:
        """With no bound correlation_id (e.g. called outside request middleware), it's empty."""
        structlog.contextvars.clear_contextvars()
        response = _var_problem(
            _fake_request(), 422, "invalid-var-run-request", "Invalid VaR Run Request", "detail"
        )

        body = json.loads(response.body)
        assert body["correlation_id"] == ""

    def test_invalid_var_query_includes_correlation_id(self) -> None:
        """The 013 series/backtest/methods query-validation slug also carries correlation_id."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id="corr-789")
        try:
            response = _var_problem(
                _fake_request("/v1/accounts/acct/risk/var"),
                422,
                "invalid-var-query",
                "Invalid VaR Query",
                "lookback '3y' is not one of the configured look-backs: 1y, 2y, 5y",
            )
        finally:
            structlog.contextvars.clear_contextvars()

        body = json.loads(response.body)
        assert body["correlation_id"] == "corr-789"
        assert body["type"] == "https://portfolio-analysis/errors/invalid-var-query"
        assert body["status"] == 422
