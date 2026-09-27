"""Unit tests asserting the risk return-histogram endpoint is documented in the OpenAPI schema."""

from typing import Any

import pytest

from app.main import app

_PATH = "/v1/accounts/{account_name}/risk/return-histogram"


@pytest.fixture(scope="module")
def openapi_schema() -> dict[str, Any]:
    """Return the application's generated OpenAPI document.

    Returns:
        The full OpenAPI schema as a dict.
    """
    schema: dict[str, Any] = app.openapi()
    return schema


def test_path_is_documented_as_a_get_tagged_risk(openapi_schema: dict[str, Any]) -> None:
    """The endpoint appears under the Risk tag as a GET operation."""
    operation = openapi_schema["paths"][_PATH]["get"]

    assert operation["tags"] == ["Risk"]


def test_start_and_end_are_optional_query_parameters(openapi_schema: dict[str, Any]) -> None:
    """Both dates are optional query parameters; account_name is a required path parameter."""
    parameters = {p["name"]: p for p in openapi_schema["paths"][_PATH]["get"]["parameters"]}

    assert parameters["account_name"]["in"] == "path"
    assert parameters["account_name"]["required"] is True
    for name in ("start", "end"):
        assert parameters[name]["in"] == "query"
        assert parameters[name]["required"] is False


def test_response_schema_is_the_return_histogram_response(openapi_schema: dict[str, Any]) -> None:
    """The 200 response references ReturnHistogramResponse with histogram and statistics."""
    ok = openapi_schema["paths"][_PATH]["get"]["responses"]["200"]
    ref = ok["content"]["application/json"]["schema"]["$ref"]

    assert ref.endswith("/ReturnHistogramResponse")
    properties = openapi_schema["components"]["schemas"]["ReturnHistogramResponse"]["properties"]
    assert {"account_name", "from_date", "to_date", "histogram", "statistics", "_links"} <= set(
        properties
    )


def test_histogram_items_are_pairs_of_integers(openapi_schema: dict[str, Any]) -> None:
    """Each histogram item is a two-element array of integers."""
    histogram = openapi_schema["components"]["schemas"]["ReturnHistogramResponse"]["properties"][
        "histogram"
    ]
    item = histogram["items"]

    assert item["type"] == "array"
    assert item["minItems"] == item["maxItems"] == 2
    assert [entry["type"] for entry in item["prefixItems"]] == ["integer", "integer"]
