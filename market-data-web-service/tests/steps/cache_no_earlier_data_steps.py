import json
import logging
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository
from app.exceptions import DataNotFoundError, ProviderUnavailableError

scenarios("cache_no_earlier_data.feature")

_SHORT_CACHED: list[tuple[date, float]] = [
    (date(2024, 1, 2), 10.00),
    (date(2024, 6, 28), 12.00),
]

_EARLIER_FOUND: list[tuple[date, float]] = [
    (date(2023, 3, 1), 8.00),
    (date(2023, 12, 29), 9.50),
]

_LATER_FOUND: list[tuple[date, float]] = [
    (date(2024, 7, 1), 13.00),
    (date(2024, 9, 30), 14.00),
]

_BOUNDARY = date(2024, 1, 2)


def _meta_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / f"{ticker}.meta.json"


def _read_boundary(cache_dir: Path, ticker: str) -> str | None:
    path = _meta_path(cache_dir, ticker)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("no_data_before")
    return str(value) if value is not None else None


def _requested_ranges(mock: MagicMock) -> list[tuple[date, date]]:
    """The (from, to) ranges the data source was actually asked for."""
    ranges: list[tuple[date, date]] = []
    for call in mock.get_price_history.call_args_list:
        args = call.args
        if len(args) >= 3:
            ranges.append((args[1], args[2]))
    return ranges


def _earlier_segment_calls(mock: MagicMock) -> list[tuple[date, date]]:
    """Calls whose requested range ends before the cached start."""
    return [(f, t) for f, t in _requested_ranges(mock) if t < _BOUNDARY]


def _later_segment_calls(mock: MagicMock) -> list[tuple[date, date]]:
    return [(f, t) for f, t in _requested_ranges(mock) if f > date(2024, 6, 28)]


@pytest.fixture()
def captured() -> list[dict[str, Any]]:
    """Scenario-scoped sink of parsed JSON log entries, filled by the request steps."""
    return []


# ── Given steps ────────────────────────────────────────────────────────────────

@given('a cache file exists for ticker "SHORT" covering 2024-01-02 to 2024-06-28')
def seed_short(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("SHORT", _SHORT_CACHED)


@given('no cache file exists for ticker "SHORT"')
def no_cache_short(tmp_cache_dir: Path) -> None:
    assert not (tmp_cache_dir / "SHORT.csv").exists()


@given("the data source has no observations before 2024-01-02")
def source_empty_before(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.side_effect = DataNotFoundError("SHORT")
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 12.0,
        "as_of_date": date(2024, 6, 28),
        "market_state": "CLOSED",
    }


@given('the service has already recorded that no data exists before 2024-01-02 for "SHORT"')
def preset_boundary(tmp_cache_dir: Path) -> None:
    _meta_path(tmp_cache_dir, "SHORT").write_text(
        json.dumps({"no_data_before": _BOUNDARY.isoformat()}), encoding="utf-8"
    )


@given('the stored history for "SHORT" is cleared')
def clear_history(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).delete("SHORT")


@given('the data source returns observations for "SHORT" starting 2023-03-01')
def source_returns_earlier(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _EARLIER_FOUND
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 9.5,
        "as_of_date": date(2023, 12, 29),
        "market_state": "CLOSED",
    }


@given('the data source returns observations for "SHORT" after 2024-06-28')
def source_returns_later(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _LATER_FOUND
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 14.0,
        "as_of_date": date(2024, 9, 30),
        "market_state": "CLOSED",
    }


@given('the data source returns observations for "SHORT" beginning 2024-01-02')
def source_returns_from_boundary(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _SHORT_CACHED
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 12.0,
        "as_of_date": date(2024, 6, 28),
        "market_state": "CLOSED",
    }


@given("the data source is unavailable")
def source_unavailable(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.side_effect = ProviderUnavailableError()
    mock_inner_provider.get_current_price.side_effect = ProviderUnavailableError()


# ── When steps ─────────────────────────────────────────────────────────────────

@when(
    'a consumer requests price history for "SHORT" from 2023-01-02 to 2024-06-28',
    target_fixture="response",
)
def req_2023_to_jun24(
    client_with_cache: TestClient,
    captured: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> httpx.Response:
    # structlog is configured with cache_logger_on_first_use=True, so capture_logs() cannot
    # intercept a logger another scenario has already bound. The JSON is rendered through
    # stdlib logging, so caplog sees it reliably instead.
    with caplog.at_level(logging.INFO):
        response = client_with_cache.get(
            "/securities/SHORT/history", params={"from": "2023-01-02", "to": "2024-06-28"}
        )
    for record in caplog.records:
        try:
            captured.append(json.loads(record.getMessage()))
        except (ValueError, TypeError):
            continue
    return response


@when(
    'the consumer repeats the request for "SHORT" from 2023-01-02 to 2024-06-28',
    target_fixture="second_response",
)
def repeat_request(
    client_with_cache: TestClient, mock_inner_provider: MagicMock
) -> httpx.Response:
    mock_inner_provider.get_price_history.reset_mock()
    return client_with_cache.get(
        "/securities/SHORT/history", params={"from": "2023-01-02", "to": "2024-06-28"}
    )


@when(
    'a consumer requests observed-only history for "SHORT" from 2020-01-02 to 2024-06-28',
    target_fixture="response",
)
def req_observed_2020_to_jun24(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/SHORT/history",
        params={"from": "2020-01-02", "to": "2024-06-28", "fill": "none"},
    )


@when(
    'a consumer requests observed-only history for "SHORT" from 2023-01-02 to 2024-06-28',
    target_fixture="response",
)
def req_observed_2023_to_jun24(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/SHORT/history",
        params={"from": "2023-01-02", "to": "2024-06-28", "fill": "none"},
    )


@when(
    'a consumer requests price history for "SHORT" from 2023-01-02 to 2024-09-30',
    target_fixture="response",
)
def req_2023_to_sep24(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/SHORT/history", params={"from": "2023-01-02", "to": "2024-09-30"}
    )


# ── Then steps ─────────────────────────────────────────────────────────────────

@then("the response status code is 200")
def status_200(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


@then("the response status code is 503")
def status_503(response: httpx.Response) -> None:
    assert response.status_code == 503, response.text


@then("the data source was called for the earlier segment")
def called_earlier(mock_inner_provider: MagicMock) -> None:
    calls = _earlier_segment_calls(mock_inner_provider)
    assert calls, _requested_ranges(mock_inner_provider)


@then("the data source was not called for the earlier segment")
def not_called_earlier(mock_inner_provider: MagicMock) -> None:
    calls = _earlier_segment_calls(mock_inner_provider)
    assert not calls, f"earlier segment was fetched: {calls}"


@then("the data source was not called again for the earlier segment")
def not_called_again_earlier(mock_inner_provider: MagicMock) -> None:
    calls = _earlier_segment_calls(mock_inner_provider)
    assert not calls, f"earlier segment was re-fetched: {calls}"


@then("the data source was called for the later segment")
def called_later(mock_inner_provider: MagicMock) -> None:
    calls = _later_segment_calls(mock_inner_provider)
    assert calls, _requested_ranges(mock_inner_provider)


@then('the service has recorded that no data exists before 2024-01-02 for "SHORT"')
def boundary_recorded(tmp_cache_dir: Path) -> None:
    assert _read_boundary(tmp_cache_dir, "SHORT") == _BOUNDARY.isoformat()


@then('no no-earlier-data boundary is recorded for "SHORT"')
def no_boundary(tmp_cache_dir: Path) -> None:
    assert _read_boundary(tmp_cache_dir, "SHORT") is None


@then('the recorded no-earlier-data boundary for "SHORT" is 2023-03-01')
def boundary_moved(tmp_cache_dir: Path) -> None:
    assert _read_boundary(tmp_cache_dir, "SHORT") == "2023-03-01"


@then("both responses contain the same price entries")
def same_entries(response: httpx.Response, second_response: httpx.Response) -> None:
    assert second_response.status_code == 200, second_response.text
    assert response.json()["prices"] == second_response.json()["prices"]


@then("the earliest price entry is 2024-01-02")
def earliest_2024_01_02(response: httpx.Response) -> None:
    assert response.json()["prices"][0]["date"] == "2024-01-02"


@then("the earliest price entry is 2023-03-01")
def earliest_2023_03_01(response: httpx.Response) -> None:
    assert response.json()["prices"][0]["date"] == "2023-03-01"


@then(
    'a log entry records that the earlier segment fetch was skipped for "SHORT" '
    "before 2024-01-02"
)
def log_skip(captured: list[dict[str, Any]]) -> None:
    events = [e for e in captured if e.get("event") == "cache_no_earlier_data_skip"]
    assert events, [e.get("event") for e in captured]
    assert events[0]["ticker"] == "SHORT"
    assert str(events[0]["no_data_before"]) == _BOUNDARY.isoformat()


@then('a log entry records that no earlier data exists for "SHORT" before 2024-01-02')
def log_recorded(captured: list[dict[str, Any]]) -> None:
    events = [e for e in captured if e.get("event") == "cache_no_earlier_data_recorded"]
    assert events, [e.get("event") for e in captured]
    assert events[0]["ticker"] == "SHORT"
    assert str(events[0]["no_data_before"]) == _BOUNDARY.isoformat()
