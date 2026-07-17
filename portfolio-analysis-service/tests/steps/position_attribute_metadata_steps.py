"""BDD step implementations for position_attribute_metadata.feature (US3)."""

from fastapi.testclient import TestClient
from pytest_bdd import parsers, scenarios, then, when

from app.services.position_attributes import SUPPORTED_ATTRIBUTES

scenarios("position_attribute_metadata.feature")


@when(
    "a request is made to the position-attribute metadata endpoint",
    target_fixture="metadata_response",
)
def request_metadata(app_client: TestClient) -> object:
    """GET the position-attribute metadata endpoint."""
    return app_client.get("/v1/positions/attributes")


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(metadata_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert metadata_response.status_code == status_code, (
        f"Expected {status_code}, got {metadata_response.status_code}: {metadata_response.text}"
    )


@then(
    "the response lists all six supported attributes: market_value, income, book_cost, "
    "pnl, close_price, and quantity"
)
def check_all_attributes_listed(metadata_response: object) -> None:
    """Assert the returned attribute-name set matches SUPPORTED_ATTRIBUTES exactly (SC-005)."""
    body = metadata_response.json()
    names = {a["name"] for a in body["attributes"]}
    assert names == SUPPORTED_ATTRIBUTES, f"Expected {SUPPORTED_ATTRIBUTES}, got {names}"


@then('"capital" does not appear in the list')
def check_capital_absent(metadata_response: object) -> None:
    """Assert 'capital' is not among the returned attribute names."""
    names = {a["name"] for a in metadata_response.json()["attributes"]}
    assert "capital" not in names


@then("each listed attribute includes a human-readable description")
def check_descriptions_present(metadata_response: object) -> None:
    """Assert every attribute has a non-empty description."""
    for attr in metadata_response.json()["attributes"]:
        assert attr["description"], f"Empty description for attribute: {attr}"


@then('the response body includes a "_links.self" URL')
def check_self_link_present(metadata_response: object) -> None:
    """Assert the _links.self key is present."""
    assert "self" in metadata_response.json()["_links"]
