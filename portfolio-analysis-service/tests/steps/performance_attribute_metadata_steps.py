"""BDD step implementations for performance_attribute_metadata.feature (US4)."""

from fastapi.testclient import TestClient
from pytest_bdd import parsers, scenarios, then, when

from app.services.performance_attributes import SUPPORTED_ATTRIBUTES

scenarios("performance_attribute_metadata.feature")


@when(
    "a request is made to the performance attribute metadata endpoint",
    target_fixture="perf_metadata_response",
)
def request_performance_metadata(app_client: TestClient) -> object:
    """GET the performance attribute metadata endpoint."""
    return app_client.get("/v1/performance/attributes")


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(perf_metadata_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert perf_metadata_response.status_code == status_code, (
        f"Expected {status_code}, got {perf_metadata_response.status_code}: "
        f"{perf_metadata_response.text}"
    )


@then("the response lists all five supported performance measures: ITD, ITD (Ann.), 1Y, 3Y, and 5Y")
def check_all_measures_listed(perf_metadata_response: object) -> None:
    """Assert the returned measure-name set matches SUPPORTED_ATTRIBUTES exactly."""
    body = perf_metadata_response.json()
    names = {a["name"] for a in body["attributes"]}
    assert names == SUPPORTED_ATTRIBUTES, f"Expected {SUPPORTED_ATTRIBUTES}, got {names}"


@then("each listed performance measure includes a human-readable description and a source")
def check_descriptions_and_sources_present(perf_metadata_response: object) -> None:
    """Assert every measure has a non-empty description and source."""
    for attr in perf_metadata_response.json()["attributes"]:
        assert attr["description"], f"Empty description for measure: {attr}"
        assert attr["source"], f"Empty source for measure: {attr}"


@then('the performance metadata response body includes a "_links.self" URL')
def check_self_link_present(perf_metadata_response: object) -> None:
    """Assert the _links.self key is present."""
    assert "self" in perf_metadata_response.json()["_links"]
