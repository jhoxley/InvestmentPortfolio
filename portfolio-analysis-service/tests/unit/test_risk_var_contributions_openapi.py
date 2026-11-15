"""Confirms the 015 contributions endpoint appears in the live OpenAPI schema."""

from fastapi.testclient import TestClient

from app.main import app


class TestContributionsEndpointOpenApi:
    """GET /v1/accounts/{account_name}/risk/var/contributions is documented correctly."""

    def test_path_and_schema_present(self) -> None:
        """The endpoint's path and response schema appear in /openapi.json."""
        with TestClient(app) as client:
            spec = client.get("/openapi.json").json()

        path = spec["paths"]["/v1/accounts/{account_name}/risk/var/contributions"]["get"]
        assert path["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "VarContributionsResponse"
        )

        schema = spec["components"]["schemas"]["VarContributionsResponse"]
        for field in (
            "account_name",
            "lookback_code",
            "lookback_days",
            "confidence_bp",
            "group_by",
            "groups",
        ):
            assert field in schema["properties"]

        group_ref = schema["properties"]["groups"]["items"]["$ref"]
        group_schema = spec["components"]["schemas"][group_ref.rsplit("/", 1)[-1]]
        for field in (
            "key",
            "identifier",
            "market_value_gbp",
            "standalone_var_gbp",
            "incremental_var_gbp",
            "component_es_gbp",
            "marginal_var_gbp_per_gbp",
        ):
            assert field in group_schema["properties"]
