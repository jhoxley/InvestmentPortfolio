from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import IdentifierNotFoundError, ProviderUnavailableError

scenarios("identifier_errors.feature")


@given('the provider cannot resolve "US0000000000"')
def mock_isin_not_found(mock_identifier_provider: MagicMock) -> None:
    mock_identifier_provider.lookup_ticker.side_effect = IdentifierNotFoundError("US0000000000")


@given("the identifier provider is unavailable")
def mock_provider_unavailable(mock_identifier_provider: MagicMock) -> None:
    mock_identifier_provider.lookup_ticker.side_effect = ProviderUnavailableError()


@when(
    'a client requests the ticker for identifier "NOT-VALID-FORMAT"',
    target_fixture="response",
)
def get_invalid_format(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/NOT-VALID-FORMAT")


@when(
    'a client requests the ticker for identifier "US0000000000"',
    target_fixture="response",
)
def get_unresolvable_isin(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/US0000000000")


@when(
    'a client requests the ticker for "NOT-VALID" with type hint "ISIN"',
    target_fixture="response",
)
def get_hint_conflict(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/NOT-VALID", params={"type": "ISIN"})


@when(
    'a client requests the ticker for identifier "US0378331005"',
    target_fixture="response",
)
def get_isin_provider_down(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/US0378331005")


@then("the identifier response status is 422")
def identifier_status_422(response: object) -> None:
    assert response.status_code == 422  # type: ignore[union-attr]


@then("the identifier response status is 404")
def identifier_status_404(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]


@then("the identifier response status is 503")
def identifier_status_503(response: object) -> None:
    assert response.status_code == 503  # type: ignore[union-attr]


@then("the response contains an identifier format error")
def response_format_error(response: object) -> None:
    body = response.json()  # type: ignore[union-attr]
    assert body.get("code") == "IDENTIFIER_FORMAT_ERROR"
    assert body.get("detail")


@then("the response contains an identifier not found error")
def response_not_found_error(response: object) -> None:
    body = response.json()  # type: ignore[union-attr]
    assert body.get("code") == "IDENTIFIER_NOT_FOUND"
    assert body.get("detail")
