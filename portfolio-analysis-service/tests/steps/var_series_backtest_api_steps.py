"""BDD step implementations for var_series_backtest_api.feature (feature 013).

Unlike feature 012's steps, these scenarios never execute a calculation run: the VaR
store (estimates.csv / outcomes.csv) is seeded directly through VarRepository.commit(),
and the HTTP surface under test is this feature's own read-only endpoints.
"""

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import get_settings
from app.main import app
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarMeta, VarRepository

scenarios("var_series_backtest_api.feature")


@pytest.fixture()
def ladder_repo(app_client: TestClient) -> LadderRepository:
    """Return a LadderRepository over the same data directory the app under test uses."""
    settings = app.dependency_overrides[get_settings]()
    return LadderRepository(data_dir=settings.data.directory)


@pytest.fixture()
def var_repo(app_client: TestClient) -> VarRepository:
    """Return a VarRepository over the same data directory the app under test uses."""
    settings = app.dependency_overrides[get_settings]()
    return VarRepository(data_dir=settings.data.directory)


@pytest.fixture()
def context() -> dict[str, Any]:
    """Mutable scratch space shared between Given/When/Then steps for one scenario."""
    return {}


def _write_minimal_ladder(repo: LadderRepository, account: str, on: date) -> None:
    """Write a one-day ladder for `account`, just enough to pass date resolution.

    Args:
        repo: LadderRepository to write through.
        account: Target account name.
        on: The single date to seed (also used as from_date/to_date).
    """
    df = pd.DataFrame(
        [
            {
                "date": on,
                "sub_account": "Equity A",
                "book_cost": 0.0,
                "quantity": 10.0,
                "total_income": 0.0,
                "price": 100.0,
                "market_value": 1000.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
            }
        ]
    )
    meta = AccountMeta(
        account_name=account,
        checksum="var-series-bdd-test",
        row_count=len(df),
        from_date=on,
        to_date=on,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


def _estimate_row(
    on: date,
    lookback_code: str,
    lookback_days: int,
    quality: str = "ok",
    var_9500_gbp: float | None = 100.0,
    var_9900_gbp: float | None = 150.0,
    es_9500_gbp: float | None = 120.0,
    es_9900_gbp: float | None = 180.0,
    run_id: str = "run-1",
) -> dict[str, Any]:
    """Build one estimates.csv row with sensible defaults, per ESTIMATE_COLUMNS."""
    insufficient = quality == "insufficient"
    return {
        "date": on,
        "method": "historical-simulation",
        "lookback_code": lookback_code,
        "lookback_days": lookback_days,
        "scenario_count": 0 if insufficient else lookback_days,
        "excluded_scenarios": 0,
        "actual_mv_pct": 100.0,
        "proxied_mv_pct": 0.0,
        "rescaled_mv_pct": 0.0,
        "quality": quality,
        "quality_reason": None if quality == "ok" else quality,
        "var_9500_gbp": None if insufficient else var_9500_gbp,
        "var_9750_gbp": None if insufficient else 125.0,
        "var_9900_gbp": None if insufficient else var_9900_gbp,
        "es_9500_gbp": None if insufficient else es_9500_gbp,
        "es_9750_gbp": None if insufficient else 150.0,
        "es_9900_gbp": None if insufficient else es_9900_gbp,
        "row_fingerprint": "fp-1",
        "methodology_version": "1.0.0",
        "run_id": run_id,
        "computed_at": datetime.now(UTC),
    }


def _commit(
    var_repo: VarRepository, account: str, estimates: pd.DataFrame, outcomes: pd.DataFrame
) -> None:
    """Commit estimate/outcome rows under a fixed test run id and methodology version."""
    var_repo.commit(
        account,
        estimates=estimates,
        outcomes=outcomes,
        instruments=pd.DataFrame(),
        meta=VarMeta(
            account_name=account,
            methodology_version="1.0.0",
            config_fingerprint="fp-config-1",
            last_successful_run_id="run-1",
            updated_at=datetime.now(UTC),
        ),
    )


def _outcome_row(
    on: date,
    outcome_date: date,
    outcome_status: str = "realised",
    hypothetical_pnl_gbp: float | None = -50.0,
    ladder_pnl_gbp: float | None = -50.0,
    total_value_gbp: float = 1000.0,
    run_id: str = "run-1",
) -> dict[str, Any]:
    """Build one outcomes.csv row with sensible defaults, per OUTCOME_COLUMNS."""
    pending = outcome_status == "pending"
    return {
        "date": on,
        "outcome_date": outcome_date,
        "outcome_status": outcome_status,
        "total_value_gbp": total_value_gbp,
        "risky_value_gbp": total_value_gbp,
        "hypothetical_pnl_gbp": None if pending else hypothetical_pnl_gbp,
        "ladder_pnl_gbp": None if pending else ladder_pnl_gbp,
        "row_fingerprint": "fp-1",
        "run_id": run_id,
        "computed_at": datetime.now(UTC),
    }


@given(parsers.parse('account "{account}" has a completed VaR run covering {on} at look-back "{code}"'))
def completed_run_covering_date(
    account: str, on: str, code: str, ladder_repo: LadderRepository, var_repo: VarRepository
) -> None:
    """Seed a single-date estimate/outcome row for the given account and look-back."""
    on_date = date.fromisoformat(on)
    _write_minimal_ladder(ladder_repo, account, on_date)
    lookback_days = {"1y": 260, "2y": 520, "5y": 1300}[code]
    _commit(
        var_repo,
        account,
        estimates=pd.DataFrame([_estimate_row(on_date, code, lookback_days)]),
        outcomes=pd.DataFrame([_outcome_row(on_date, on_date + pd.offsets.BDay(1))]),
    )


@given(
    parsers.parse(
        'account "{account}" has completed estimates at look-backs "{c1}", "{c2}" and "{c3}" for {on}'
    )
)
def completed_estimates_multi_lookback(
    account: str,
    c1: str,
    c2: str,
    c3: str,
    on: str,
    ladder_repo: LadderRepository,
    var_repo: VarRepository,
) -> None:
    """Seed the same date at three different look-backs, with distinguishably different VaR."""
    on_date = date.fromisoformat(on)
    _write_minimal_ladder(ladder_repo, account, on_date)
    lookback_days = {"1y": 260, "2y": 520, "5y": 1300}
    rows = [
        _estimate_row(on_date, code, lookback_days[code], var_9500_gbp=100.0 + i * 10)
        for i, code in enumerate((c1, c2, c3))
    ]
    _commit(
        var_repo,
        account,
        estimates=pd.DataFrame(rows),
        outcomes=pd.DataFrame([_outcome_row(on_date, on_date + pd.offsets.BDay(1))]),
    )


@given(
    parsers.parse(
        'account "{account}" has a completed estimate for {on} at 95%, 97.5% and 99%'
    )
)
def completed_estimate_all_confidence(
    account: str, on: str, ladder_repo: LadderRepository, var_repo: VarRepository
) -> None:
    """Seed one date's estimate with all three confidence levels populated."""
    on_date = date.fromisoformat(on)
    _write_minimal_ladder(ladder_repo, account, on_date)
    _commit(
        var_repo,
        account,
        estimates=pd.DataFrame([_estimate_row(on_date, "2y", 520)]),
        outcomes=pd.DataFrame([_outcome_row(on_date, on_date + pd.offsets.BDay(1))]),
    )


@given(parsers.parse('account "{account}" has an ingested position ladder but no completed VaR run'))
def ladder_only_no_var_run(account: str, ladder_repo: LadderRepository) -> None:
    """Seed only a ladder; the VaR store for this account stays empty."""
    _write_minimal_ladder(ladder_repo, account, date(2026, 3, 2))


@given(
    parsers.parse(
        "a stored estimate for {on} with 95% VaR of {var_gbp:d} GBP"
    )
)
def stored_estimate_with_var(
    on: str, var_gbp: int, context: dict[str, Any], ladder_repo: LadderRepository
) -> None:
    """Record the as-of date and 95% VaR for the following outcome step to use."""
    on_date = date.fromisoformat(on)
    _write_minimal_ladder(ladder_repo, "var-acct", on_date)
    context["on_date"] = on_date
    context["var_9500_gbp"] = float(var_gbp)


@given(parsers.parse("the stored outcome's hypothetical PnL for that date is {pnl:d} GBP"))
def stored_outcome_hypothetical_pnl(
    pnl: int, context: dict[str, Any], var_repo: VarRepository
) -> None:
    """Commit the estimate/outcome pair now that both the VaR and PnL are known."""
    on_date: date = context["on_date"]
    _commit(
        var_repo,
        "var-acct",
        estimates=pd.DataFrame(
            [_estimate_row(on_date, "2y", 520, var_9500_gbp=context["var_9500_gbp"])]
        ),
        outcomes=pd.DataFrame(
            [
                _outcome_row(
                    on_date,
                    on_date + pd.offsets.BDay(1),
                    hypothetical_pnl_gbp=float(pnl),
                    ladder_pnl_gbp=float(pnl),
                )
            ]
        ),
    )


@when(
    parsers.parse(
        'the VaR series is requested for "{account}" from {start} to {end} at look-back "{code}"'
    )
)
def request_series_range_lookback(
    account: str, start: str, end: str, code: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request with an explicit range and look-back."""
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var",
        params={"start": start, "end": end, "lookback": code},
    )


@when(parsers.parse('the VaR series is requested for "{account}" at look-back "{code}"'))
def request_series_lookback(
    account: str, code: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request with only a look-back specified."""
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var", params={"lookback": code}
    )


@when(parsers.parse('the VaR series is requested for "{account}" with confidence {pct} only'))
def request_series_single_confidence(
    account: str, pct: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request with exactly one confidence level."""
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var", params={"confidence": pct.rstrip("%")}
    )


@when(parsers.parse('the VaR series is requested for "{account}" with no confidence parameter'))
def request_series_no_confidence(
    account: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request omitting confidence entirely."""
    context["response"] = app_client.get(f"/v1/accounts/{account}/risk/var")


@when(parsers.parse('the VaR series is requested for "{account}" with look-back "{code}"'))
def request_series_with_invalid_lookback(
    account: str, code: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request with a (possibly unsupported) look-back code."""
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var", params={"lookback": code}
    )


@when(parsers.parse('the VaR series is requested for "{account}" with confidence "{pct}"'))
def request_series_with_confidence_string(
    account: str, pct: str, context: dict[str, Any], app_client: TestClient
) -> None:
    """Issue the series request with a (possibly unsupported) confidence value."""
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var", params={"confidence": pct.rstrip("%")}
    )


@given(parsers.parse("a request with start {start} and end {end}"))
def record_invalid_range(start: str, end: str, context: dict[str, Any]) -> None:
    """Record an explicit start/end pair for the next series request."""
    context["start"] = start
    context["end"] = end


@given("an account that has only a capital ledger")
def account_with_only_capital_ledger(app_client: TestClient) -> None:
    """Ingest a capital ledger (but no position ladder) for 'capital-only-acct'."""
    from app.repositories.capital_repository import CapitalRepository
    from tests.risk_helpers import write_capital_only

    settings = app.dependency_overrides[get_settings]()
    write_capital_only(CapitalRepository(data_dir=settings.data.directory), "capital-only-acct")


@when(parsers.parse('the VaR series is requested for that account'))
def request_series_for_capital_only_account(context: dict[str, Any], app_client: TestClient) -> None:
    """Issue the series request for the capital-only account seeded above."""
    context["response"] = app_client.get("/v1/accounts/capital-only-acct/risk/var")


@given(parsers.parse('no account named "{account}" exists'))
def no_such_account(account: str) -> None:
    """No-op Given: the account is simply never seeded."""


@when(parsers.parse('the VaR series is requested for "{account}"'))
def request_series_default(account: str, context: dict[str, Any], app_client: TestClient) -> None:
    """Issue the series request, using any start/end recorded by a prior Given step."""
    params: dict[str, str] = {}
    if "start" in context:
        params["start"] = context["start"]
    if "end" in context:
        params["end"] = context["end"]
    context["response"] = app_client.get(f"/v1/accounts/{account}/risk/var", params=params)


@then(
    parsers.parse(
        "the single returned entry's scenario count, coverage, quality, VaR and ES at "
        "every confidence level match the stored estimate exactly"
    )
)
def assert_series_entry_matches_estimate(context: dict[str, Any]) -> None:
    """Check the one returned entry's figures against the seeded estimate row."""
    body = context["response"].json()
    assert len(body["series"]) == 1
    entry = body["series"][0]
    assert entry["scenario_count"] == 520
    assert entry["actual_mv_pct"] == 100.0
    assert entry["quality"] == "ok"
    levels = {lvl["confidence_bp"]: lvl for lvl in entry["levels"]}
    assert levels[9500]["var_gbp"] == 100.0
    assert levels[9900]["var_gbp"] == 150.0


@then("its hypothetical and ladder PnL match the stored outcome exactly")
def assert_series_entry_matches_outcome(context: dict[str, Any]) -> None:
    """Check the one returned entry's PnL against the seeded outcome row."""
    entry = context["response"].json()["series"][0]
    assert entry["hypothetical_pnl_gbp"] == -50.0
    assert entry["ladder_pnl_gbp"] == -50.0


@then(parsers.parse('the returned entry\'s figures are the "{code}" estimate, not "2y" or "5y"'))
def assert_series_entry_is_code(code: str, context: dict[str, Any]) -> None:
    """Check the single returned entry used the requested look-back's figures."""
    body = context["response"].json()
    assert body["lookback_code"] == code
    entry = body["series"][0]
    expected = {"1y": 100.0, "2y": 110.0, "5y": 120.0}[code]
    assert entry["levels"][0]["var_gbp"] == expected


@then("the returned entry includes only the 95% VaR/ES figures")
def assert_series_entry_only_95(context: dict[str, Any]) -> None:
    """Check exactly one confidence level, 95%, is present."""
    entry = context["response"].json()["series"][0]
    assert [lvl["confidence_bp"] for lvl in entry["levels"]] == [9500]


@then("the returned entry includes every configured confidence level")
def assert_series_entry_all_levels(context: dict[str, Any]) -> None:
    """Check every configured confidence level (95/97.5/99) is present."""
    entry = context["response"].json()["series"][0]
    assert {lvl["confidence_bp"] for lvl in entry["levels"]} == {9500, 9750, 9900}


@then(parsers.parse("the response is {status:d} with an empty series"))
def assert_response_status_empty_series(status: int, context: dict[str, Any]) -> None:
    """Check the status code and an empty series list."""
    assert context["response"].status_code == status
    assert context["response"].json()["series"] == []


@then("the response links to the account's VaR status and runs resources")
def assert_response_links_status_and_runs(context: dict[str, Any]) -> None:
    """Check the _links object names both the status and runs resources."""
    links = context["response"].json()["_links"]
    assert "status" in links
    assert "runs" in links


@then(parsers.parse("that date's 95% entry reports the hypothetical PnL as an exception"))
def assert_exception_flagged(context: dict[str, Any]) -> None:
    """Check the 95% level's hypothetical_exception flag is True."""
    body = context["response"].json()
    entry = body["series"][0]
    level = next(lvl for lvl in entry["levels"] if lvl["confidence_bp"] == 9500)
    assert level["hypothetical_exception"] is True


@then(parsers.parse("the request is rejected with a client error naming the supported look-backs"))
def assert_rejected_naming_lookbacks(context: dict[str, Any]) -> None:
    """Check a 422 invalid-var-query response names the supported look-back codes."""
    resp = context["response"]
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"].endswith("invalid-var-query")
    assert "correlation_id" in body
    for code in ("1y", "2y", "5y"):
        assert code in body["detail"]


@then(
    parsers.parse(
        "the request is rejected with a client error naming the supported confidence levels"
    )
)
def assert_rejected_naming_confidence(context: dict[str, Any]) -> None:
    """Check a 422 invalid-var-query response names the supported confidence levels."""
    resp = context["response"]
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"].endswith("invalid-var-query")
    for pct in ("95", "97.5", "99"):
        assert pct in body["detail"]


@then(
    parsers.parse(
        "the response is a not-found error, consistent with the performance and VaR run endpoints"
    )
)
def assert_not_found(context: dict[str, Any]) -> None:
    """Check a 404 account-not-found response."""
    resp = context["response"]
    assert resp.status_code == 404
    assert resp.json()["type"].endswith("account-not-found")


@then("the request is rejected with a client error describing the invalid date range")
def assert_rejected_invalid_date_range(context: dict[str, Any]) -> None:
    """Check a 422 invalid-date-range response."""
    resp = context["response"]
    assert resp.status_code == 422
    assert resp.json()["type"].endswith("invalid-date-range")


@then("the request is rejected with a client error consistent with the performance endpoints")
def assert_rejected_missing_source(context: dict[str, Any]) -> None:
    """Check a 422 missing-required-source response."""
    resp = context["response"]
    assert resp.status_code == 422
    assert resp.json()["type"].endswith("missing-required-source")
