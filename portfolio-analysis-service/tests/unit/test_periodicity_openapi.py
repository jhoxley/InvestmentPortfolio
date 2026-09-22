"""Unit tests asserting periodicity discoverability in the generated OpenAPI document."""

from typing import Any

import pytest

from app.main import app
from app.models.periodicity import SUPPORTED_PERIODICITY_VALUES

_TIMESERIES_PATH = "/v1/accounts/{account_name}/timeseries"
_POSITION_PATH = "/v1/accounts/{account_name}/position"


@pytest.fixture(scope="module")
def openapi_schema() -> dict[str, Any]:
    """Return the application's generated OpenAPI document.

    Returns:
        The full OpenAPI schema as a dict.
    """
    schema: dict[str, Any] = app.openapi()
    return schema


def _periodicity_parameter(schema: dict[str, Any], path: str) -> dict[str, Any]:
    """Extract the `periodicity` query parameter definition for a path's GET operation.

    Args:
        schema: The generated OpenAPI document.
        path: The templated path to inspect.

    Returns:
        The parameter object for `periodicity`.
    """
    parameters = schema["paths"][path]["get"]["parameters"]
    matches = [p for p in parameters if p["name"] == "periodicity"]
    assert len(matches) == 1, f"Expected one periodicity parameter on {path}, got {len(matches)}"
    return matches[0]


class TestParameterIsDiscoverable:
    """The allowed values must be machine-readable from the published contract (FR-017)."""

    @pytest.mark.parametrize("path", [_TIMESERIES_PATH, _POSITION_PATH])
    def test_parameter_is_optional_and_enumerated(
        self, openapi_schema: dict[str, Any], path: str
    ) -> None:
        """The parameter is optional and its schema enumerates all supported values.

        Args:
            openapi_schema: The generated OpenAPI document.
            path: The endpoint under test.
        """
        parameter = _periodicity_parameter(openapi_schema, path)

        assert parameter["required"] is False
        assert parameter["schema"]["enum"] == list(SUPPORTED_PERIODICITY_VALUES)

    @pytest.mark.parametrize("path", [_TIMESERIES_PATH, _POSITION_PATH])
    def test_parameter_documents_its_meaning(
        self, openapi_schema: dict[str, Any], path: str
    ) -> None:
        """The parameter carries a description naming the default behaviour.

        Args:
            openapi_schema: The generated OpenAPI document.
            path: The endpoint under test.
        """
        parameter = _periodicity_parameter(openapi_schema, path)
        description = parameter.get("description", "")

        assert "day" in description
        assert "business day" in description


class TestMetadataEndpointsAreUnchanged:
    """Only the two time series endpoints gain the parameter."""

    @pytest.mark.parametrize(
        "path",
        [
            "/v1/timeseries/attributes",
            "/v1/positions/attributes",
            "/v1/accounts/{account_name}/positions",
        ],
    )
    def test_other_endpoints_have_no_periodicity_parameter(
        self, openapi_schema: dict[str, Any], path: str
    ) -> None:
        """A non-time-series endpoint must not accept periodicity.

        Args:
            openapi_schema: The generated OpenAPI document.
            path: The endpoint under test.
        """
        parameters = openapi_schema["paths"][path]["get"].get("parameters", [])

        assert not [p for p in parameters if p["name"] == "periodicity"]


class TestResponseFieldIsAdditiveAndOptional:
    """The new response field must not be required, so existing clients stay valid."""

    @pytest.mark.parametrize("schema_name", ["TimeSeriesResponse", "PositionTimeSeriesResponse"])
    def test_periodicity_present_but_not_required(
        self, openapi_schema: dict[str, Any], schema_name: str
    ) -> None:
        """Periodicity is a declared property and absent from `required` (FR-012).

        Args:
            openapi_schema: The generated OpenAPI document.
            schema_name: The response schema under test.
        """
        model_schema = openapi_schema["components"]["schemas"][schema_name]

        assert "periodicity" in model_schema["properties"]
        assert "periodicity" not in model_schema.get("required", [])

    @pytest.mark.parametrize(
        ("schema_name", "expected_fields"),
        [
            (
                "TimeSeriesResponse",
                ["account_name", "attributes", "from_date", "to_date", "entries", "_links"],
            ),
            (
                "PositionTimeSeriesResponse",
                [
                    "account_name",
                    "attributes",
                    "positions",
                    "from_date",
                    "to_date",
                    "entries",
                    "_links",
                ],
            ),
        ],
    )
    def test_preexisting_fields_remain_required(
        self, openapi_schema: dict[str, Any], schema_name: str, expected_fields: list[str]
    ) -> None:
        """Every field that existed before this feature is still present and required.

        Args:
            openapi_schema: The generated OpenAPI document.
            schema_name: The response schema under test.
            expected_fields: The pre-existing field names.
        """
        model_schema = openapi_schema["components"]["schemas"][schema_name]
        required = model_schema.get("required", [])

        for field in expected_fields:
            assert field in model_schema["properties"], f"{field} missing from {schema_name}"
            assert field in required, f"{field} no longer required on {schema_name}"
