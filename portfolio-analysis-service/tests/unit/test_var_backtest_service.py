"""Unit tests for VarBacktestService: the read-only backtest endpoint's orchestration."""

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
from app.services.var.var_backtest_service import VarBacktestService


def _write_ladder(repo: LadderRepository, account: str, from_date: date, to_date: date) -> None:
    days = pd.bdate_range(start=from_date, end=to_date)
    df = pd.DataFrame(
        [
            {
                "date": d.date(),
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
            for d in days
        ]
    )
    meta = AccountMeta(
        account_name=account,
        checksum="x",
        row_count=len(df),
        from_date=from_date,
        to_date=to_date,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


def _estimate_row(
    on: date, quality: str = "ok", var_9900_gbp: float = 100.0, fingerprint: str = "fp-1"
) -> dict[str, object]:
    insufficient = quality == "insufficient"
    return {
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
        "var_9500_gbp": None if insufficient else var_9900_gbp * 0.7,
        "var_9750_gbp": None if insufficient else var_9900_gbp * 0.85,
        "var_9900_gbp": None if insufficient else var_9900_gbp,
        "es_9500_gbp": None if insufficient else var_9900_gbp * 0.9,
        "es_9750_gbp": None if insufficient else var_9900_gbp * 1.0,
        "es_9900_gbp": None if insufficient else var_9900_gbp * 1.2,
        "row_fingerprint": fingerprint,
        "methodology_version": "1.0.0",
        "run_id": "run-1",
        "computed_at": datetime.now(UTC),
    }


def _outcome_row(
    on: date,
    outcome_status: str = "realised",
    hypothetical_pnl_gbp: float = -10.0,
    ladder_pnl_gbp: float = -10.0,
) -> dict[str, object]:
    pending = outcome_status == "pending"
    return {
        "date": on,
        "outcome_date": on + pd.offsets.BDay(1),
        "outcome_status": outcome_status,
        "total_value_gbp": 1000.0,
        "risky_value_gbp": 1000.0,
        "hypothetical_pnl_gbp": None if pending else hypothetical_pnl_gbp,
        "ladder_pnl_gbp": None if pending else ladder_pnl_gbp,
        "row_fingerprint": "fp-1",
        "run_id": "run-1",
        "computed_at": datetime.now(UTC),
    }


def _commit(
    var_repo: VarRepository,
    account: str,
    estimates: list[dict[str, object]],
    outcomes: list[dict[str, object]],
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
) -> VarBacktestService:
    """Wire a VarBacktestService over the given repositories."""
    ladder_repo, capital_repo, var_repo = repos
    return VarBacktestService(
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
        settings=VarSettings(),
    )


def _seed_days(
    repos: tuple[LadderRepository, CapitalRepository, VarRepository],
    account: str,
    days: pd.DatetimeIndex,
    exception_on: set[int] | None = None,
    quality_by_index: dict[int, str] | None = None,
    pending_on: set[int] | None = None,
) -> None:
    """Seed `len(days)` consecutive estimate/outcome rows, each 100 GBP VaR at 99%."""
    ladder_repo, _, var_repo = repos
    _write_ladder(ladder_repo, account, days[0].date(), days[-1].date())
    exception_on = exception_on or set()
    pending_on = pending_on or set()
    quality_by_index = quality_by_index or {}
    estimates = [
        _estimate_row(d.date(), quality=quality_by_index.get(i, "ok")) for i, d in enumerate(days)
    ]
    outcomes = [
        _outcome_row(
            d.date(),
            outcome_status="pending" if i in pending_on else "realised",
            hypothetical_pnl_gbp=-150.0 if i in exception_on else -10.0,
            ladder_pnl_gbp=-150.0 if i in exception_on else -10.0,
        )
        for i, d in enumerate(days)
    ]
    _commit(var_repo, account, estimates, outcomes)


class TestGetBacktestObservationsAndExceptions:
    """Observation and exception counting against a seeded store."""

    def test_exception_count_matches_losses_beyond_var(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Exactly the seeded exception days are counted."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=250)
        _seed_days(repos, "acct", days, exception_on={10, 20, 30, 40, 50, 60})

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=(days[-1] + pd.offsets.BDay(1)).date(),
        )

        level = response.levels[0]
        assert level.observation_count == 250
        assert level.exception_count == 6

    def test_pnl_basis_switch_changes_exception_count(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """pnl_basis='ladder' uses ladder_pnl_gbp instead of hypothetical_pnl_gbp."""
        ladder_repo, _, var_repo = repos
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        _write_ladder(ladder_repo, "acct", days[0].date(), days[-1].date())
        estimates = [_estimate_row(d.date()) for d in days]
        outcomes = [
            _outcome_row(
                d.date(),
                hypothetical_pnl_gbp=-150.0 if i == 3 else -10.0,
                ladder_pnl_gbp=-10.0,
            )
            for i, d in enumerate(days)
        ]
        _commit(var_repo, "acct", estimates, outcomes)
        today = (days[-1] + pd.offsets.BDay(1)).date()

        hypothetical = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=today,
        )
        ladder = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="ladder",
            min_quality="degraded",
            rolling=False,
            today=today,
        )

        assert hypothetical.levels[0].exception_count == 1
        assert ladder.levels[0].exception_count == 0

    def test_min_quality_ok_narrows_observation_count(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """min_quality='ok' excludes 'degraded' days from the observation count."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        quality_by_index = {i: "degraded" for i in range(3)}
        _seed_days(repos, "acct", days, quality_by_index=quality_by_index)
        today = (days[-1] + pd.offsets.BDay(1)).date()

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="ok",
            rolling=False,
            today=today,
        )

        assert response.levels[0].observation_count == 7

    def test_insufficient_and_pending_always_excluded_regardless_of_min_quality(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-011: insufficient-quality and pending-outcome days are never observations."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        quality_by_index = {0: "insufficient", 1: "insufficient", 2: "insufficient"}
        _seed_days(repos, "acct", days, quality_by_index=quality_by_index, pending_on={9})
        today = (days[-1] + pd.offsets.BDay(1)).date()

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=today,
        )

        assert response.levels[0].observation_count == 6

    def test_excluded_date_breaks_independence_transition_chain(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A min_quality-excluded day breaks the chain for its neighbours (FR-014)."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        quality_by_index = {5: "degraded"}
        # Exceptions either side of the excluded day: with the gap, the 4->6 transition
        # is never counted; without it, 4->5 and 5->6 are both counted instead.
        _seed_days(
            repos,
            "acct",
            days,
            exception_on={4, 6},
            quality_by_index=quality_by_index,
        )
        today = (days[-1] + pd.offsets.BDay(1)).date()

        with_gap = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="ok",
            rolling=False,
            today=today,
        )
        no_gap = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=today,
        )

        assert with_gap.levels[0].observation_count == 9
        assert no_gap.levels[0].observation_count == 10
        # Different observation sets (gap vs no gap) should differ in a dependent stat.
        assert (
            with_gap.levels[0].christoffersen_independence_lr
            != no_gap.levels[0].christoffersen_independence_lr
        )

    def test_rolling_option_returns_250_point_series_over_500_days(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Requesting rolling=True over 500 seeded days returns a 250-point rolling series."""
        days = pd.bdate_range(start=date(2024, 1, 2), periods=500)
        _seed_days(repos, "acct", days)
        today = (days[-1] + pd.offsets.BDay(1)).date()

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=True,
            today=today,
        )

        rolling = response.levels[0].rolling_exceptions
        assert rolling is not None
        assert len(rolling) == 500 - 250 + 1

    def test_zero_observations_returns_null_statistics_with_zero_counts(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An account/range with nothing qualifying returns 0 counts and every stat null."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 1, 5), date(2026, 1, 5))

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=date(2026, 1, 6),
        )

        level = response.levels[0]
        assert level.observation_count == 0
        assert level.exception_count == 0
        assert level.expected_exceptions is None
        assert level.exception_rate is None
        assert level.kupiec_lr is None
        assert level.zone is None
        assert level.mean_var_gbp is None
        assert level.var_stability is None

    def test_exception_dates_and_mean_var_match_seeded_values(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """exception_dates lists exactly the seeded exception days; mean_var_gbp matches."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        _seed_days(repos, "acct", days, exception_on={3, 7})
        today = (days[-1] + pd.offsets.BDay(1)).date()

        response = _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=today,
        )

        level = response.levels[0]
        expected_dates = sorted([days[3].date(), days[7].date()])
        assert sorted(level.exception_dates) == expected_dates
        assert level.mean_var_gbp == pytest.approx(100.0)

    def test_fr023_never_commits_or_writes_a_run(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """FR-023: get_backtest() must never call VarRepository.commit() or write_run()."""
        days = pd.bdate_range(start=date(2026, 1, 5), periods=10)
        _seed_days(repos, "acct", days)
        today = (days[-1] + pd.offsets.BDay(1)).date()
        _, _, var_repo = repos

        def _fail(*args: object, **kwargs: object) -> None:
            raise AssertionError("VarBacktestService must not write to the VaR store")

        var_repo.commit = _fail  # type: ignore[method-assign]
        var_repo.write_run = _fail  # type: ignore[method-assign]

        _service(repos).get_backtest(
            account_name="acct",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=[9900],
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=False,
            today=today,
        )


class TestGetBacktestValidation:
    """FR-024: account validation errors are identical to the performance endpoints."""

    def test_unknown_account_raises_account_not_found(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An unknown account raises AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError):
            _service(repos).get_backtest(
                account_name="missing",
                start=None,
                end=None,
                lookback="2y",
                confidence_levels_bp=[9900],
                pnl_basis="hypothetical",
                min_quality="degraded",
                rolling=False,
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
            _service(repos).get_backtest(
                account_name="capital-only",
                start=None,
                end=None,
                lookback="2y",
                confidence_levels_bp=[9900],
                pnl_basis="hypothetical",
                min_quality="degraded",
                rolling=False,
                today=date(2026, 3, 2),
            )

    def test_future_end_date_raises(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An end date later than today raises FutureEndDateError."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 2))

        with pytest.raises(FutureEndDateError):
            _service(repos).get_backtest(
                account_name="acct",
                start=None,
                end=date(2026, 6, 1),
                lookback="2y",
                confidence_levels_bp=[9900],
                pnl_basis="hypothetical",
                min_quality="degraded",
                rolling=False,
                today=date(2026, 3, 2),
            )

    def test_start_after_end_raises_invalid_date_range(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A start date after the end date raises InvalidDateRangeError."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 2))

        with pytest.raises(InvalidDateRangeError):
            _service(repos).get_backtest(
                account_name="acct",
                start=date(2026, 6, 1),
                end=date(2026, 1, 1),
                lookback="2y",
                confidence_levels_bp=[9900],
                pnl_basis="hypothetical",
                min_quality="degraded",
                rolling=False,
                today=date(2026, 6, 1),
            )
