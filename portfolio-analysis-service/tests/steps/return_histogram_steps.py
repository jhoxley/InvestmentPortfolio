"""BDD step implementations for return_histogram.feature (US1-US4)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import get_settings
from app.main import app
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from tests.risk_helpers import write_capital_only, write_daily_returns, write_ladder

scenarios("return_histogram.feature")


@pytest.fixture()
def ladder_repo(app_client: TestClient) -> LadderRepository:
    """Return a LadderRepository over the same data directory the app under test uses.

    Args:
        app_client: TestClient whose settings override points at a temporary data directory.

    Returns:
        LadderRepository for writing controlled ladders directly.
    """
    settings = app.dependency_overrides[get_settings]()
    return LadderRepository(data_dir=settings.data.directory)


def _parse_floats(text: str) -> list[float]:
    """Parse a phrase like '0.0010, 0.00104 and -0.0025' into floats.

    Args:
        text: Comma/"and" separated numbers.

    Returns:
        The numbers in order.
    """
    return [float(part) for part in text.replace(" and ", ",").split(",") if part.strip()]


@given(
    parsers.parse(
        'account "{account_name}" has daily portfolio returns of {returns} on consecutive '
        "business days from {start}"
    ),
    target_fixture="account_name",
)
def account_with_daily_returns(
    account_name: str, returns: str, start: str, ladder_repo: LadderRepository
) -> str:
    """Write a one-sub-account ladder with the given daily returns."""
    write_daily_returns(
        ladder_repo, account_name, date.fromisoformat(start), _parse_floats(returns)
    )
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has sub-accounts "{sub_a}" and "{sub_b}" with weighted position '
        "returns {ret_a} and {ret_b} on {on_date}"
    ),
    target_fixture="account_name",
)
def account_with_two_sub_accounts(
    account_name: str,
    sub_a: str,
    sub_b: str,
    ret_a: str,
    ret_b: str,
    on_date: str,
    ladder_repo: LadderRepository,
) -> str:
    """Write a ladder with two sub-accounts on a single date."""
    day = date.fromisoformat(on_date)
    write_ladder(
        ladder_repo,
        account_name,
        [
            {"date": day, "sub_account": sub_a, "weighted_position_return": float(ret_a)},
            {"date": day, "sub_account": sub_b, "weighted_position_return": float(ret_b)},
        ],
    )
    return account_name


@when(
    parsers.parse("the return histogram is requested from {start} to {end}"),
    target_fixture="hist_response",
)
def request_histogram(account_name: str, start: str, end: str, app_client: TestClient) -> object:
    """GET the return histogram endpoint for an explicit window."""
    return app_client.get(
        f"/v1/accounts/{account_name}/risk/return-histogram",
        params={"start": start, "end": end},
    )


@then(parsers.parse("the histogram response status is {status_code:d}"))
def check_status(hist_response: object, status_code: int) -> None:
    """Assert the HTTP status code."""
    assert hist_response.status_code == status_code, hist_response.text  # type: ignore[attr-defined]


@then(parsers.parse('the histogram buckets are "{expected}"'))
def check_buckets(hist_response: object, expected: str) -> None:
    """Assert the histogram list equals the expected 'bucket:count' pairs, in order."""
    pairs = [tuple(int(x) for x in item.split(":")) for item in expected.split(", ")]
    body = hist_response.json()  # type: ignore[attr-defined]
    assert [tuple(p) for p in body["histogram"]] == pairs


@then(
    parsers.parse(
        "the statistics report count {count:d}, minimum {minimum:d}, maximum {maximum:d}, "
        "mean {mean:g}, median {median:g} and mode {mode:d}"
    )
)
def check_basic_statistics(
    hist_response: object,
    count: int,
    minimum: int,
    maximum: int,
    mean: float,
    median: float,
    mode: int,
) -> None:
    """Assert the basic location statistics."""
    stats = hist_response.json()["statistics"]  # type: ignore[attr-defined]
    assert stats["count"] == count
    assert stats["minimum"] == minimum
    assert stats["maximum"] == maximum
    assert stats["mean"] == pytest.approx(mean)
    assert stats["median"] == pytest.approx(median)
    assert stats["mode"] == mode


@then(
    "each standard deviation band has a multiple equal to sigma times the standard deviation "
    "and edges at the mean minus and plus that multiple"
)
def check_std_dev_bands(hist_response: object) -> None:
    """Assert the sigma bands are consistent with std_dev and mean."""
    stats = hist_response.json()["statistics"]  # type: ignore[attr-defined]
    assert [band["sigma"] for band in stats["std_dev_bands"]] == [1, 2, 3]
    for band in stats["std_dev_bands"]:
        assert band["multiple"] == pytest.approx(band["sigma"] * stats["std_dev"])
        assert band["lower"] == pytest.approx(stats["mean"] - band["multiple"])
        assert band["upper"] == pytest.approx(stats["mean"] + band["multiple"])


@then("the statistics count equals the sum of all histogram bucket counts")
def check_count_matches_histogram(hist_response: object) -> None:
    """Assert statistics.count equals the total of the histogram counts."""
    body = hist_response.json()  # type: ignore[attr-defined]
    assert body["statistics"]["count"] == sum(count for _, count in body["histogram"])


@given(
    parsers.parse('no account named "{account_name}" exists'),
    target_fixture="account_name",
)
def no_such_account(account_name: str) -> str:
    """Name an account that has never been ingested."""
    return account_name


@given(
    parsers.parse('account "{account_name}" has only a capital ledger'),
    target_fixture="account_name",
)
def capital_only_account(account_name: str, app_client: TestClient) -> str:
    """Write a capital ledger for the account, with no position ladder."""
    settings = app.dependency_overrides[get_settings]()
    write_capital_only(CapitalRepository(data_dir=settings.data.directory), account_name)
    return account_name


@when(
    "the return histogram is requested with no start or end date",
    target_fixture="hist_response",
)
def request_histogram_no_dates(account_name: str, app_client: TestClient) -> object:
    """GET the return histogram endpoint with no date parameters."""
    return app_client.get(f"/v1/accounts/{account_name}/risk/return-histogram")


@when(
    parsers.parse(
        'the performance endpoint is requested for attribute "{attribute}" from {start} to {end}'
    ),
    target_fixture="perf_response",
)
def request_performance(
    account_name: str, attribute: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for a single attribute and explicit window."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[("attribute", attribute), ("start", start), ("end", end)],
    )


@when(
    parsers.parse(
        'the performance endpoint is requested for attribute "{attribute}" with no start or end date'
    ),
    target_fixture="perf_response",
)
def request_performance_no_dates(
    account_name: str, attribute: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for a single attribute with default dates."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance", params=[("attribute", attribute)]
    )


@then("the histogram response is a problem details document")
def check_problem_details(hist_response: object) -> None:
    """Assert the response uses RFC 7807 problem+json."""
    assert "application/problem+json" in hist_response.headers["content-type"]  # type: ignore[attr-defined]


@then(parsers.parse("the histogram to_date is {expected}"))
def check_to_date(hist_response: object, expected: str) -> None:
    """Assert the resolved to_date of the histogram response."""
    assert hist_response.json()["to_date"] == expected  # type: ignore[attr-defined]


@then("the histogram statistics count equals the number of performance entries")
def check_count_equals_performance_entries(hist_response: object, perf_response: object) -> None:
    """Assert both endpoints observe the same business days."""
    assert perf_response.status_code == 200, perf_response.text  # type: ignore[attr-defined]
    hist = hist_response.json()  # type: ignore[attr-defined]
    perf = perf_response.json()  # type: ignore[attr-defined]
    assert hist["statistics"]["count"] == len(perf["entries"])


@then("the histogram and performance responses have the same from_date and to_date")
def check_same_dates(hist_response: object, perf_response: object) -> None:
    """Assert both endpoints resolved the same window."""
    hist = hist_response.json()  # type: ignore[attr-defined]
    perf = perf_response.json()  # type: ignore[attr-defined]
    assert (hist["from_date"], hist["to_date"]) == (perf["from_date"], perf["to_date"])


@then(
    "the statistics have one observation with undefined standard deviation, skewness and kurtosis"
)
def check_single_observation_statistics(hist_response: object) -> None:
    """Assert dispersion statistics are null for a single observation."""
    stats = hist_response.json()["statistics"]  # type: ignore[attr-defined]
    assert stats["count"] == 1
    assert stats["mean"] == pytest.approx(20.0)
    assert stats["std_dev"] is None
    assert stats["std_dev_bands"] == []
    assert stats["skewness"] is None
    assert stats["kurtosis"] is None
