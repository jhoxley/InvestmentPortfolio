"""Unit tests for RiskService orchestration of the daily return histogram."""

from datetime import date
from pathlib import Path

import pytest

from app.exceptions import (
    AccountNotFoundError,
    FutureEndDateError,
    InvalidDateRangeError,
    MissingRequiredSourceError,
)
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services.accounts_service import AccountsService
from app.services.daily_return_series_loader import DailyReturnSeriesLoader
from app.services.performance_service import PerformanceService
from app.services.risk_service import RiskService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from tests.risk_helpers import write_capital_only, write_daily_returns, write_ladder

TODAY = date(2024, 6, 14)  # Friday, well after all fixture dates below


@pytest.fixture()
def ladder_repo(tmp_path: Path) -> LadderRepository:
    """Return a tmp_path-backed LadderRepository.

    Returns:
        LadderRepository ready for use in tests.
    """
    return LadderRepository(data_dir=tmp_path)


@pytest.fixture()
def capital_repo(tmp_path: Path) -> CapitalRepository:
    """Return a tmp_path-backed CapitalRepository.

    Returns:
        CapitalRepository ready for use in tests.
    """
    return CapitalRepository(data_dir=tmp_path)


@pytest.fixture()
def service(ladder_repo: LadderRepository, capital_repo: CapitalRepository) -> RiskService:
    """Return a RiskService wired to the tmp_path-backed repositories.

    Returns:
        RiskService ready for use in tests.
    """
    loader = DailyReturnSeriesLoader(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        date_resolver=TimeseriesDateResolver(),
    )
    return RiskService(loader=loader)


class TestHistogramBuckets:
    """The histogram counts rounded basis point buckets over the requested window."""

    def test_spec_example_buckets(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Five returns give the buckets (-25, 1), (10, 3), (11, 1)."""
        write_daily_returns(
            ladder_repo, "acct", date(2024, 1, 2), [0.0010, 0.00104, 0.0011, -0.0025, 0.0010]
        )

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 8), TODAY)

        assert response.histogram == [(-25, 1), (10, 3), (11, 1)]

    def test_portfolio_return_is_sum_of_weighted_position_returns(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """0.011 + (-0.0045) = 0.0065 contributes one observation to the 65 bp bucket."""
        write_ladder(
            ladder_repo,
            "acct",
            [
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities A",
                    "weighted_position_return": 0.011,
                },
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities B",
                    "weighted_position_return": -0.0045,
                },
            ],
        )

        response = service.get_return_histogram("acct", date(2024, 3, 4), date(2024, 3, 4), TODAY)

        assert response.histogram == [(65, 1)]

    def test_only_dates_inside_the_window_contribute(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Returns before start and after end are excluded (no look-back, FR-012)."""
        # Business days 2024-01-02 .. 2024-01-08: 10, 20, 30, 40, 50 bps
        write_daily_returns(
            ladder_repo, "acct", date(2024, 1, 2), [0.0010, 0.0020, 0.0030, 0.0040, 0.0050]
        )

        response = service.get_return_histogram("acct", date(2024, 1, 3), date(2024, 1, 5), TODAY)

        assert response.histogram == [(20, 1), (30, 1), (40, 1)]

    def test_response_echoes_account_and_resolved_dates(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """account_name, from_date and to_date describe the resolved window."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 5)

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 8), TODAY)

        assert response.account_name == "acct"
        assert response.from_date == date(2024, 1, 2)
        assert response.to_date == date(2024, 1, 8)

    def test_links_contain_self_and_accounts(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """HATEOAS links point at this resource and the accounts collection."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 3)

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 4), TODAY)

        assert response.links == {
            "self": "/v1/accounts/acct/risk/return-histogram",
            "accounts": "/v1/accounts",
        }


class TestStatistics:
    """The statistics block describes the same observations as the histogram."""

    def test_count_equals_sum_of_histogram_counts(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Every observation is both counted in a bucket and in statistics.count."""
        write_daily_returns(
            ladder_repo, "acct", date(2024, 1, 2), [0.0010, 0.00104, 0.0011, -0.0025, 0.0010]
        )

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 8), TODAY)

        assert response.statistics.count == sum(count for _, count in response.histogram) == 5

    def test_statistics_use_rounded_basis_point_observations(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Two 0.00104 days round to 10 bps each, so mean is 10.0 (not the unrounded 10.4)."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.00104, 0.00104])

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 3), TODAY)

        assert response.statistics.mean == pytest.approx(10.0)
        assert response.statistics.minimum == 10
        assert response.statistics.maximum == 10

    def test_spec_example_statistics(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Returns of -10, 0, 0, 10 and 20 bps give mean 4, median 0 and mode 0."""
        write_daily_returns(
            ladder_repo, "acct", date(2024, 1, 2), [-0.0010, 0.0, 0.0, 0.0010, 0.0020]
        )

        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 8), TODAY)

        stats = response.statistics
        assert (stats.count, stats.minimum, stats.maximum, stats.mode) == (5, -10, 20, 0)
        assert stats.mean == pytest.approx(4.0)
        assert stats.median == pytest.approx(0.0)

    def test_single_day_window_has_count_one_and_undefined_dispersion(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """A start equal to end gives one observation: dispersion statistics are null."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 10)

        response = service.get_return_histogram("acct", date(2024, 1, 4), date(2024, 1, 4), TODAY)

        assert response.histogram == [(10, 1)]
        assert response.statistics.count == 1
        assert response.statistics.mean == pytest.approx(10.0)
        assert response.statistics.std_dev is None
        assert response.statistics.skewness is None
        assert response.statistics.kurtosis is None


class TestConsistencyWithPerformance:
    """The risk and performance services agree on dates and on the daily return series."""

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (None, None),
            (date(2024, 1, 3), date(2024, 1, 9)),
            (date(2024, 1, 2), date(2024, 1, 6)),  # Saturday end adjusts forward
        ],
    )
    def test_resolved_dates_match_performance_service(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        service: RiskService,
        start: date | None,
        end: date | None,
    ) -> None:
        """Identical inputs resolve to identical (from_date, to_date) in both services."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 8)
        performance = PerformanceService(
            ladder_repo=ladder_repo,
            accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
            date_resolver=TimeseriesDateResolver(),
        )

        risk_response = service.get_return_histogram("acct", start, end, TODAY)
        perf_response = performance.get_performance("acct", ["ITD"], start, end, TODAY)

        assert (risk_response.from_date, risk_response.to_date) == (
            perf_response.from_date,
            perf_response.to_date,
        )
        assert risk_response.statistics.count == len(perf_response.entries)

    def test_business_day_without_ladder_rows_counts_as_zero_bucket_observation(
        self, ladder_repo: LadderRepository, service: RiskService
    ) -> None:
        """Days after the last ladder row are zero-filled, as in the performance series."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.0010, 0.0020, 0.0030])

        # 2024-01-02..04 have data; 2024-01-05 and 2024-01-08 do not.
        response = service.get_return_histogram("acct", date(2024, 1, 2), date(2024, 1, 8), TODAY)

        assert response.histogram == [(0, 2), (10, 1), (20, 1), (30, 1)]
        assert response.statistics.count == 5


class TestErrorPropagation:
    """Errors from the shared loader surface unchanged."""

    def test_unknown_account(self, service: RiskService) -> None:
        """No ledger and no ladder gives AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError):
            service.get_return_histogram("missing", None, None, TODAY)

    def test_capital_only_account(
        self, capital_repo: CapitalRepository, service: RiskService
    ) -> None:
        """A capital ledger without a ladder gives MissingRequiredSourceError."""
        write_capital_only(capital_repo, "cap-only")

        with pytest.raises(MissingRequiredSourceError):
            service.get_return_histogram("cap-only", None, None, TODAY)

    def test_start_before_ladder(self, ladder_repo: LadderRepository, service: RiskService) -> None:
        """A start earlier than the ladder's first date gives MissingRequiredSourceError."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 3)

        with pytest.raises(MissingRequiredSourceError):
            service.get_return_histogram("acct", date(2023, 12, 1), date(2024, 1, 3), TODAY)

    def test_future_end_date(self, ladder_repo: LadderRepository, service: RiskService) -> None:
        """An end date after today gives FutureEndDateError."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 3)

        with pytest.raises(FutureEndDateError):
            service.get_return_histogram("acct", None, date(2024, 6, 15), TODAY)

    def test_start_after_end(self, ladder_repo: LadderRepository, service: RiskService) -> None:
        """A start after the end gives InvalidDateRangeError."""
        write_daily_returns(ladder_repo, "acct", date(2024, 1, 2), [0.001] * 3)

        with pytest.raises(InvalidDateRangeError):
            service.get_return_histogram("acct", date(2024, 1, 5), date(2024, 1, 3), TODAY)
