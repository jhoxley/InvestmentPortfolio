"""Confirms the 013 series/backtest/methods endpoints appear in the live OpenAPI schema."""

from fastapi.testclient import TestClient

from app.main import app


class TestSeriesEndpointOpenApi:
    """GET /v1/accounts/{account_name}/risk/var is documented with the right schema."""

    def test_path_and_schema_present(self) -> None:
        """The endpoint's path and response schema appear in /openapi.json."""
        with TestClient(app) as client:
            spec = client.get("/openapi.json").json()

        path = spec["paths"]["/v1/accounts/{account_name}/risk/var"]["get"]
        assert path["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "VarSeriesResponse"
        )

        schema = spec["components"]["schemas"]["VarSeriesResponse"]
        for field in ("account_name", "lookback_code", "lookback_days", "from_date", "to_date"):
            assert field in schema["properties"]


class TestBacktestEndpointOpenApi:
    """GET /v1/accounts/{account_name}/risk/var/backtest is documented with the right schema."""

    def test_path_and_schema_present(self) -> None:
        """The endpoint's path and response schema appear in /openapi.json."""
        with TestClient(app) as client:
            spec = client.get("/openapi.json").json()

        path = spec["paths"]["/v1/accounts/{account_name}/risk/var/backtest"]["get"]
        assert path["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "VarBacktestResponse"
        )

        schema = spec["components"]["schemas"]["VarBacktestResponse"]
        for field in ("pnl_basis", "min_quality", "levels"):
            assert field in schema["properties"]


class TestMethodsEndpointOpenApi:
    """GET /v1/risk/var/methods is documented with the right schema."""

    def test_path_and_schema_present(self) -> None:
        """The endpoint's path and response schema appear in /openapi.json."""
        with TestClient(app) as client:
            spec = client.get("/openapi.json").json()

        path = spec["paths"]["/v1/risk/var/methods"]["get"]
        assert path["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "VarMethodsResponse"
        )

        schema = spec["components"]["schemas"]["VarMethodsResponse"]
        for field in ("method", "lookbacks", "confidence_levels_bp", "measures"):
            assert field in schema["properties"]
