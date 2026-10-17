"""Unit tests for the VaR run endpoints' OpenAPI schema."""

from app.main import app


class TestRiskVarOpenApi:
    """app.openapi() documents the run endpoints with the expected shapes."""

    def test_run_paths_are_present(self) -> None:
        """POST/GET .../runs and GET .../runs/{run_id} appear in the schema."""
        schema = app.openapi()
        paths = schema["paths"]
        assert "/v1/accounts/{account_name}/risk/var/runs" in paths
        assert "/v1/accounts/{account_name}/risk/var/runs/{run_id}" in paths

    def test_post_returns_202(self) -> None:
        """The create-run endpoint documents a 202 response."""
        schema = app.openapi()
        post = schema["paths"]["/v1/accounts/{account_name}/risk/var/runs"]["post"]
        assert "202" in post["responses"]

    def test_post_documents_409_and_422(self) -> None:
        """The create-run endpoint documents conflict and validation responses."""
        schema = app.openapi()
        post = schema["paths"]["/v1/accounts/{account_name}/risk/var/runs"]["post"]
        assert "409" in post["responses"]
        assert "422" in post["responses"]

    def test_get_run_documents_404(self) -> None:
        """The get-run endpoint documents a not-found response."""
        schema = app.openapi()
        get = schema["paths"]["/v1/accounts/{account_name}/risk/var/runs/{run_id}"]["get"]
        assert "404" in get["responses"]

    def test_var_run_schema_has_links_correlation_and_skipped_count(self) -> None:
        """The VarRun schema documents _links, correlation_id and dates_skipped."""
        schema = app.openapi()
        var_run = schema["components"]["schemas"]["VarRun"]["properties"]
        assert "_links" in var_run
        assert "correlation_id" in var_run
        assert "dates_skipped" in var_run
