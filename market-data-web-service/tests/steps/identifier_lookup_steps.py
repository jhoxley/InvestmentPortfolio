from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("identifier_lookup.feature")


@given('the provider resolves "US0378331005" to ticker "AAPL" on exchange "NMS"')
def mock_isin_aapl(mock_identifier_provider: MagicMock) -> None:
    mock_identifier_provider.lookup_ticker.return_value = {
        "ticker": "AAPL",
        "security_name": "Apple Inc.",
        "exchange": "NMS",
    }


@given('the provider resolves "037833100" to ticker "AAPL" on exchange "NMS"')
def mock_cusip_aapl(mock_identifier_provider: MagicMock) -> None:
    mock_identifier_provider.lookup_ticker.return_value = {
        "ticker": "AAPL",
        "security_name": "Apple Inc.",
        "exchange": "NMS",
    }


@given('the provider resolves "B020QX2" to ticker "BARC.L" on exchange "LSE"')
def mock_sedol_barcl(mock_identifier_provider: MagicMock) -> None:
    mock_identifier_provider.lookup_ticker.return_value = {
        "ticker": "BARC.L",
        "security_name": "Barclays PLC",
        "exchange": "LSE",
    }


@when(
    'a client requests the ticker for "US0378331005"',
    target_fixture="response",
)
def get_isin_us0378331005(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/US0378331005")


@when(
    'a client requests the ticker for "037833100"',
    target_fixture="response",
)
def get_cusip_037833100(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/037833100")


@when(
    'a client requests the ticker for "B020QX2"',
    target_fixture="response",
)
def get_sedol_b020qx2(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/B020QX2")


@when(
    'a client requests the ticker for "US0378331005" with type hint "ISIN"',
    target_fixture="response",
)
def get_isin_with_hint(client_with_identifiers: TestClient) -> object:
    return client_with_identifiers.get("/identifiers/US0378331005", params={"type": "ISIN"})


@then("the identifier response status is 200")
def identifier_status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response ticker is "AAPL"')
def response_ticker_aapl(response: object) -> None:
    assert response.json()["ticker"] == "AAPL"  # type: ignore[union-attr]


@then('the response ticker is "BARC.L"')
def response_ticker_barcl(response: object) -> None:
    assert response.json()["ticker"] == "BARC.L"  # type: ignore[union-attr]


@then('the response identifier_type is "ISIN"')
def response_type_isin(response: object) -> None:
    assert response.json()["identifier_type"] == "ISIN"  # type: ignore[union-attr]


@then('the response identifier_type is "CUSIP"')
def response_type_cusip(response: object) -> None:
    assert response.json()["identifier_type"] == "CUSIP"  # type: ignore[union-attr]


@then('the response identifier_type is "SEDOL"')
def response_type_sedol(response: object) -> None:
    assert response.json()["identifier_type"] == "SEDOL"  # type: ignore[union-attr]


@then("the response security_name is non-empty")
def response_security_name_nonempty(response: object) -> None:
    assert response.json()["security_name"]  # type: ignore[union-attr]


@then("the response exchange is non-empty")
def response_exchange_nonempty(response: object) -> None:
    assert response.json()["exchange"]  # type: ignore[union-attr]
