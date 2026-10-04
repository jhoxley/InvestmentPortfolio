"""Unit tests for VarSeriesService: the read-only series endpoint's orchestration."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.config import VarSettings
from app.exceptions import (
    AccountNotFoundError,
    FutureEndDateError,
    InvalidDateRangeError,
    MissingRequiredSourceError,
)
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarMeta, VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.var_series_service import VarSeriesService


def _write_ladder(repo: LadderRepository, account: str, on: date) -> None:
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
        checksum="x",
        row_count=1,
        from_date=on,
        to_date=on,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


def _estimate_row(on: date, quality: str = "ok", **overrides: object) -> dict[str, object]:
    insufficient = quality == "insufficient"
    row: dict[str, object] = {
        "date": on,
        "method": "historical-simulation",
        "lookback_code": "2y",
        "lookback_days": 520,
        "scenario_count": 0 if insufficient else 520,
        "excluded_scenarios": 0,
        "actual_mv_pct": 100.0,
        "proxied_mv_pct": 0.0,
        "rescaled_mv_pct": 0.0,
        "quality": quality,
        "quality_reason": None if quality == "ok" else quality,
        "var_9500_gbp": None if insufficient else 100.0,
        "var_9750_gbp": None if insufficient else 125.0,
        "var_9900_gbp": None if insufficient else 150.0,
        "es_9500_gbp": None if insufficient else 120.0,
        "es_9750_gbp": None if insufficient else 150.0,
        "es_9900_gbp": None if insufficient else 180.0,
        "row_fingerprint": "fp-1",
        "methodology_version": "1.0.0",
        "run_id": "run-1",
        "computed_at": datetime.now(UTC),
    }
    row.update(overrides)
    return row


def _outcome_row(
    on: date, outcome_status: str = "realised", **overrides: object
) -> dict[str, object]:
    pending = outcome_status == "pending"
    row: dict[str, object] = {
        "date": on,
        "outcome_date": on + pd.offsets.BDay(1),
        "outcome_status": outcome_status,
        "total_value_gbp": 1000.0,
        "risky_value_gbp": 1000.0,
        "hypothetical_pnl_gbp": None if pending else -50.0,
        "ladder_pnl_gbp": None if pending else -50.0,
        "row_fingerprint": "fp-1",
        "run_id": "run-1",
        "computed_at": datetime.now(UTC),
    }
    row.update(overrides)
    return row


def _commit(
    var_repo: VarRepository, account: str, estimates: list[dict], outcomes: list[dict]
) -> None:
    var_repo.commit(
        account,
        estimates=pd.DataFrame(estimates),
        outcomes=pd.DataFrame(outcomes),
        instruments=pd.DataFrame(),
        meta=VarMeta(
            account_name=account,
            methodology_version="1.0.0",
            config_fingerprint="fp-cfg",
            last_successful_run_id="run-1",
            updated_at=datetime.now(UTC),
        ),
    )


@pytest.fixture()
def repos(tmp_path: Path) -> tuple[LadderRepository, CapitalRepository, VarRepository]:
    """Return fresh ladder/capital/var repositories over the same temp data directory."""
    return (
        LadderRepository(data_dir=tmp_path),
        CapitalRepository(data_dir=tmp_path),
        VarRepository(data_dir=tmp_path),
    )


def _service(
    repos: tuple[LadderRepository, CapitalRepository, VarRepository],
    settings: VarSettings | None = None,
) -> VarSeriesService:
    """Wire a VarSeriesService over the given repositories."""
    ladder_repo, capital_repo, var_repo = repos
    return VarSeriesService(
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
        settings=settings or VarSettings(),
    )


class TestGetSeriesHappyPath:
    """get_series() against a seeded store returns exactly the stored figures."""

    def test_exact_values_match_stored_estimate_and_outcome(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """SC-001: every value in the response matches the stored estimate/outcome exactly."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on)], [_outcome_row(on)])

        response = _service(repos).get_series(
            account_name="acct",
            start=on,
            end=on,
            lookback="2y",
            confidence_levels_bp=[9500, 9750, 9900],
            today=on,
        )

        assert len(response.series) == 1
        entry = response.series[0]
        assert entry.scenario_count == 520
        assert entry.total_value_gbp == 1000.0
        assert entry.hypothetical_pnl_gbp == -50.0
        assert entry.ladder_pnl_gbp == -50.0
        levels = {lvl.confidence_bp: lvl for lvl in entry.levels}
        assert levels[9500].var_gbp == 100.0
        assert levels[9500].var_pct == pytest.approx(10.0)
        assert levels[9900].es_gbp == 180.0

    def test_only_requested_lookback_is_returned(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Multiple look-backs stored for the same date: only the requested one appears."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(
            var_repo,
            "acct",
            [
                _estimate_row(on, lookback_code="1y", lookback_days=260, var_9500_gbp=10.0),
                _estimate_row(on, lookback_code="2y", lookback_days=520, var_9500_gbp=20.0),
            ],
            [_outcome_row(on)],
        )

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="1y",
            confidence_levels_bp=None,
            today=(on + pd.offsets.BDay(1)).date(),
        )

        assert response.lookback_code == "1y"
        assert len(response.series) == 1
        assert response.series[0].levels[0].var_gbp == 10.0

    def test_only_requested_confidence_levels_appear(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Requesting a single confidence level returns only that level's entry."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on)], [_outcome_row(on)])

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9500],
            today=(on + pd.offsets.BDay(1)).date(),
        )

        assert [lvl.confidence_bp for lvl in response.series[0].levels] == [9500]

    def test_omitting_confidence_returns_every_configured_level(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Omitting confidence_levels_bp returns every configured confidence level."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on)], [_outcome_row(on)])

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=(on + pd.offsets.BDay(1)).date(),
        )

        assert {lvl.confidence_bp for lvl in response.series[0].levels} == {9500, 9750, 9900}

    def test_insufficient_quality_row_has_null_level_fields(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-006: quality 'insufficient' still appears, but every level field is null."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on, quality="insufficient")], [_outcome_row(on)])

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=(on + pd.offsets.BDay(1)).date(),
        )

        entry = response.series[0]
        assert entry.quality == "insufficient"
        for level in entry.levels:
            assert level.var_gbp is None
            assert level.var_pct is None
            assert level.es_gbp is None
            assert level.hypothetical_exception is None

    def test_pending_outcome_row_has_null_pnl_and_exception_fields(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-007: a pending outcome nulls PnL and both exception flags, regardless of quality."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on)], [_outcome_row(on, outcome_status="pending")])

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=(on + pd.offsets.BDay(1)).date(),
        )

        entry = response.series[0]
        assert entry.hypothetical_pnl_gbp is None
        assert entry.ladder_pnl_gbp is None
        for level in entry.levels:
            assert level.hypothetical_exception is None
            assert level.ladder_exception is None

    def test_hypothetical_exception_flag_is_strict_loss_exceeding_var(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """hypothetical_exception is True only when that PnL's loss strictly exceeds VaR."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(
            var_repo,
            "acct",
            [_estimate_row(on, var_9500_gbp=100.0)],
            [_outcome_row(on, hypothetical_pnl_gbp=-150.0, ladder_pnl_gbp=-50.0)],
        )

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9500],
            today=(on + pd.offsets.BDay(1)).date(),
        )

        level = response.series[0].levels[0]
        assert level.hypothetical_exception is True
        assert level.ladder_exception is False

    def test_fr023_never_commits_or_writes_a_run(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-023: get_series() must never call VarRepository.commit() or write_run()."""
        ladder_repo, _, var_repo = repos
        on = date(2026, 3, 2)
        _write_ladder(ladder_repo, "acct", on)
        _commit(var_repo, "acct", [_estimate_row(on)], [_outcome_row(on)])

        def _fail(*args: object, **kwargs: object) -> None:
            raise AssertionError("VarSeriesService must not write to the VaR store")

        var_repo.commit = _fail  # type: ignore[method-assign]
        var_repo.write_run = _fail  # type: ignore[method-assign]

        _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=(on + pd.offsets.BDay(1)).date(),
        )


class TestGetSeriesEmptyStore:
    """get_series() for an account with no computed VaR data returns an empty series."""

    def test_no_estimates_at_all_returns_empty_series_with_links(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-008/SC-005: nothing computed -> empty series, status/runs links, not an error."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2))

        response = _service(repos).get_series(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=date(2026, 3, 3),
        )

        assert response.series == []
        assert "status" in response.links
        assert "runs" in response.links


class TestGetSeriesValidation:
    """FR-024: account/date validation errors are identical to the performance endpoints."""

    def test_unknown_account_raises_account_not_found(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An account with no ingested resource at all raises AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError):
            _service(repos).get_series(
                account_name="missing",
                start=None,
                end=None,
                lookback="2y",
                confidence_levels_bp=None,
                today=date(2026, 3, 2),
            )

    def test_capital_only_account_raises_missing_required_source(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An account with only a capital ledger (no position ladder) raises the same error."""
        from tests.risk_helpers import write_capital_only

        _, capital_repo, _ = repos
        write_capital_only(capital_repo, "capital-only")

        with pytest.raises(MissingRequiredSourceError):
            _service(repos).get_series(
                account_name="capital-only",
                start=None,
                end=None,
                lookback="2y",
                confidence_levels_bp=None,
                today=date(2026, 3, 2),
            )

    def test_future_end_date_raises(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An end date later than today raises FutureEndDateError."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2))

        with pytest.raises(FutureEndDateError):
            _service(repos).get_series(
                account_name="acct",
                start=None,
                end=date(2026, 6, 1),
                lookback="2y",
                confidence_levels_bp=None,
                today=date(2026, 3, 2),
            )

    def test_start_after_end_raises_invalid_date_range(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A start date after the end date raises InvalidDateRangeError."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2))

        with pytest.raises(InvalidDateRangeError):
            _service(repos).get_series(
                account_name="acct",
                start=date(2026, 6, 1),
                end=date(2026, 1, 1),
                lookback="2y",
                confidence_levels_bp=None,
                today=date(2026, 6, 1),
            )
