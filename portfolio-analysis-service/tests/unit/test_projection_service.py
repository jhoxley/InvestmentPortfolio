"""Unit tests for ProjectionService orchestration, date resolution, and the historical series.

Also covers, from User Story 1 onward, the compounding-formula correctness of each
projected series (022).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import (
    AccountNotFoundError,
    InvalidProjectionRangeError,
    MissingRequiredSourceError,
    PositionLadderNotIngestedError,
    UnsupportedAttributeError,
)
from app.models.periodicity import Periodicity
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.projection_service import ProjectionService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.timeseries_service import TimeSeriesService

_FIXTURE_START = date(2016, 1, 4)
_FIXTURE_END = date(2020, 1, 2)  # ~4 years — enough for a computable 3Y measure (780 days)
_DAILY_RETURN = 0.0003
_MARKET_VALUE_START = 10000.0
_MARKET_VALUE_STEP = 2.0


def _write_ladder(repo: LadderRepository, account_name: str) -> AccountMeta:
    """Write a synthetic multi-year single-position ladder with both value columns populated.

    Both market_value and weighted_position_return are set, so both the historical series
    (market_value) and the performance measures (weighted_position_return) can be exercised
    from the same fixture.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.

    Returns:
        The written AccountMeta (from_date/to_date, etc.).
    """
    business_days = pd.bdate_range(start=_FIXTURE_START, end=_FIXTURE_END)
    df = pd.DataFrame(
        [
            {
                "date": day.date(),
                "sub_account": "Cash",
                "book_cost": 0.0,
                "quantity": 1.0,
                "total_income": 0.0,
                "price": 1.0,
                "market_value": _MARKET_VALUE_START + i * _MARKET_VALUE_STEP,
                "portfolio_weight": 1.0,
                "position_return": _DAILY_RETURN,
                "weighted_position_return": _DAILY_RETURN,
            }
            for i, day in enumerate(business_days)
        ]
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="cafebabe",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=["Cash"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)
    return meta


def _write_capital_only(repo: CapitalRepository, account_name: str) -> None:
    """Write a minimal capital ledger so an account is 'known' but has no position ladder."""
    df = pd.DataFrame(
        [{"date": date(2016, 1, 4), "capital": 1000.0, "income": 0.0, "book_value": 900.0}]
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=date(2016, 1, 4),
        to_date=date(2016, 1, 4),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


@pytest.fixture()
def ladder_repo(tmp_path: Path) -> LadderRepository:
    """Return a tmp_path-backed LadderRepository."""
    return LadderRepository(data_dir=tmp_path)


@pytest.fixture()
def capital_repo(tmp_path: Path) -> CapitalRepository:
    """Return a tmp_path-backed CapitalRepository."""
    return CapitalRepository(data_dir=tmp_path)


@pytest.fixture()
def service(
    ladder_repo: LadderRepository, capital_repo: CapitalRepository
) -> ProjectionService:
    """Return a ProjectionService wired to the tmp_path-backed repositories."""
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return ProjectionService(ladder_repo=ladder_repo, accounts_service=accounts_service)


@pytest.fixture()
def timeseries_service(
    ladder_repo: LadderRepository, capital_repo: CapitalRepository
) -> TimeSeriesService:
    """A real TimeSeriesService, used only as the cross-check oracle in T002(e)."""
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return TimeSeriesService(
        ladder_repo=ladder_repo,
        capital_repo=capital_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
    )


class TestOmittedStartDefaultsToLaddersToDate:
    """Test omitted start defaults to ladders to date."""
    def test_omitted_start_defaults_to_ladders_to_date(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test omitted start defaults to ladders to date."""
        meta = _write_ladder(ladder_repo, "known")

        response = service.get_projection(
            "known", projection_date=date(2030, 1, 2), returns=[], start=None
        )

        assert response.entries[-1].date == meta.to_date


class TestExplicitStartOnNonBusinessDayResolvesForward:
    """Test explicit start on non business day resolves forward."""
    def test_explicit_start_on_non_business_day_resolves_forward(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test explicit start on non business day resolves forward."""
        _write_ladder(ladder_repo, "known")
        # 2018-01-06 is a Saturday; the next business day is 2018-01-08 (Monday).
        response = service.get_projection(
            "known", projection_date=date(2030, 1, 2), returns=[], start=date(2018, 1, 6)
        )

        assert response.entries[-1].date == date(2018, 1, 8)


class TestExplicitStartBeyondToDateIsCappedBack:
    """Test explicit start beyond to date is capped back."""
    def test_explicit_start_beyond_to_date_is_capped_back(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test explicit start beyond to date is capped back."""
        meta = _write_ladder(ladder_repo, "known")

        response = service.get_projection(
            "known", projection_date=date(2030, 1, 2), returns=[], start=date(2025, 1, 1)
        )

        assert response.entries[-1].date == meta.to_date


class TestExplicitStartBeforeFromDateRaisesMissingRequiredSourceError:
    """Test explicit start before from date raises missing required source error."""
    def test_explicit_start_before_from_date_raises_missing_required_source_error(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test explicit start before from date raises missing required source error."""
        _write_ladder(ladder_repo, "known")

        with pytest.raises(MissingRequiredSourceError):
            service.get_projection(
                "known", projection_date=date(2030, 1, 2), returns=[], start=date(2010, 1, 1)
            )


class TestHistoricalSeriesMatchesTimeSeriesServicesOwnMarketValueAggregation:
    """Test historical series matches time series services own market value aggregation."""
    def test_historical_series_matches_timeseries_services_own_aggregation(
        self,
        ladder_repo: LadderRepository,
        service: ProjectionService,
        timeseries_service: TimeSeriesService,
    ) -> None:
        """Test historical series matches timeseries services own aggregation."""
        _write_ladder(ladder_repo, "known")
        resolved_start = date(2018, 6, 1)

        projection_response = service.get_projection(
            "known", projection_date=date(2030, 1, 2), returns=[], start=resolved_start
        )
        oracle_response = timeseries_service.get_series(
            "known", ["market_value"], None, resolved_start, today=date(2024, 6, 14)
        )

        projected_by_date = {e.date: e.model_dump()["market_value"] for e in projection_response.entries}
        oracle_by_date = {e.date: e.model_dump()["market_value"] for e in oracle_response.entries}
        assert projected_by_date == oracle_by_date


class TestAccountWithNoResourceAtAllRaisesAccountNotFoundError:
    """Test account with no resource at all raises account not found error."""
    def test_account_with_no_resource_at_all_raises_account_not_found_error(
        self, service: ProjectionService
    ) -> None:
        """Test account with no resource at all raises account not found error."""
        with pytest.raises(AccountNotFoundError):
            service.get_projection("unknown", projection_date=date(2030, 1, 2), returns=[])


class TestAccountWithCapitalButNoLadderRaisesPositionLadderNotIngestedError:
    """Test account with capital but no ladder raises position ladder not ingested error."""
    def test_account_with_capital_but_no_ladder_raises_position_ladder_not_ingested_error(
        self, capital_repo: CapitalRepository, service: ProjectionService
    ) -> None:
        """Test account with capital but no ladder raises position ladder not ingested error."""
        _write_capital_only(capital_repo, "capital-only")

        with pytest.raises(PositionLadderNotIngestedError):
            service.get_projection(
                "capital-only", projection_date=date(2030, 1, 2), returns=[]
            )


class TestProjectionDateNotLaterThanStartRaisesInvalidProjectionRangeError:
    """Test projection date not later than start raises invalid projection range error."""
    def test_projection_date_equal_to_start_raises(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test projection date equal to start raises."""
        meta = _write_ladder(ladder_repo, "known")

        with pytest.raises(InvalidProjectionRangeError):
            service.get_projection("known", projection_date=meta.to_date, returns=[])

    def test_projection_date_before_start_raises(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test projection date before start raises."""
        _write_ladder(ladder_repo, "known")

        with pytest.raises(InvalidProjectionRangeError):
            service.get_projection(
                "known", projection_date=date(2015, 1, 1), start=date(2018, 6, 1), returns=[]
            )


# --- User Story 1: single-return projection ---------------------------------


class TestSingleReturnProducesOneHistoricalAndOneProjectedSeries:
    """Test single return produces one historical and one projected series."""
    def test_single_return_produces_one_historical_and_one_projected_series(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test single return produces one historical and one projected series."""
        _write_ladder(ladder_repo, "known")
        resolved_start = date(2019, 6, 3)
        projection_date = date(2020, 6, 1)

        response = service.get_projection(
            "known", projection_date=projection_date, returns=["3Y"], start=resolved_start
        )

        assert set(response.positions) == {"Historical", "3Y"}
        historical_entries = [e for e in response.entries if e.position == "Historical"]
        projected_entries = [e for e in response.entries if e.position == "3Y"]
        assert historical_entries[-1].date == resolved_start
        assert projected_entries[0].date == resolved_start
        assert projected_entries[-1].date == projection_date


class TestProjectedSeriesBeginsAtHistoricalSeriesFinalValue:
    """Test projected series begins at historical series final value."""
    def test_projected_series_begins_at_historical_series_final_value(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test projected series begins at historical series final value."""
        _write_ladder(ladder_repo, "known")
        resolved_start = date(2019, 6, 3)

        response = service.get_projection(
            "known", projection_date=date(2020, 6, 1), returns=["3Y"], start=resolved_start
        )

        historical_final = next(
            e for e in response.entries if e.position == "Historical" and e.date == resolved_start
        )
        projected_first = next(
            e for e in response.entries if e.position == "3Y" and e.date == resolved_start
        )
        assert historical_final.model_dump()["market_value"] == pytest.approx(
            projected_first.model_dump()["market_value"]
        )


class TestProjectedSeriesCompoundsTheRequestedReturnsOwnHistoricalRate:
    """Test projected series compounds the requested returns own historical rate."""
    def test_projected_series_compounds_the_requested_returns_own_historical_rate(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """V(t) = V0 * (1 + (1 + annualized_return) ** (1/260) - 1) ** t, t = elapsed business days."""
        from app.services.daily_portfolio_return import compute_daily_portfolio_return
        from app.services.performance_metrics import compute_performance_measures

        meta = _write_ladder(ladder_repo, "known")
        resolved_start = date(2019, 6, 3)
        projection_date = date(2019, 6, 10)  # a handful of business days out

        ladder_df = ladder_repo.read_full_df("known")
        daily_returns_df = compute_daily_portfolio_return(
            ladder_df, from_date=meta.from_date, through_date=resolved_start
        )
        measures_df = compute_performance_measures(daily_returns_df)
        expected_r = measures_df.loc[measures_df["date"] == resolved_start, "3Y"].iloc[0]
        expected_daily_rate = (1 + expected_r) ** (1 / 260) - 1

        response = service.get_projection(
            "known", projection_date=projection_date, returns=["3Y"], start=resolved_start
        )

        projected = sorted(
            (e for e in response.entries if e.position == "3Y"), key=lambda e: e.date
        )
        v0 = next(
            e for e in response.entries if e.position == "Historical" and e.date == resolved_start
        ).model_dump()["market_value"]
        for t, entry in enumerate(projected):
            expected_value = v0 * (1 + expected_daily_rate) ** t
            assert entry.model_dump()["market_value"] == pytest.approx(expected_value)


# --- User Story 2: multiple returns, silent omission, zero returns ----------


class TestMultipleReturnsEachProduceTheirOwnSeriesFromASharedStartingPoint:
    """Test multiple returns each produce their own series from a shared starting point."""
    def test_multiple_returns_produce_distinct_series_sharing_a_start(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test multiple returns produce distinct series sharing a start."""
        _write_ladder(ladder_repo, "known")
        resolved_start = date(2019, 6, 3)

        response = service.get_projection(
            "known",
            projection_date=date(2020, 6, 1),
            returns=["1Y", "3Y"],
            start=resolved_start,
        )

        assert set(response.positions) == {"Historical", "1Y", "3Y"}
        starts = {
            e.position: e.model_dump()["market_value"]
            for e in response.entries
            if e.position in ("1Y", "3Y") and e.date == resolved_start
        }
        assert starts["1Y"] == pytest.approx(starts["3Y"])


class TestReturnWithInsufficientHistoryIsSilentlyOmitted:
    """Test return with insufficient history is silently omitted."""
    def test_return_with_insufficient_history_is_silently_omitted(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test return with insufficient history is silently omitted."""
        _write_ladder(ladder_repo, "known")
        # Only ~2.5 years elapsed by this start date — not enough for a computable 5Y measure.
        resolved_start = date(2018, 6, 1)

        response = service.get_projection(
            "known", projection_date=date(2020, 6, 1), returns=["5Y", "1Y"], start=resolved_start
        )

        assert "5Y" not in response.positions
        assert "1Y" in response.positions


class TestZeroReturnsReturnsHistoricalSeriesAlone:
    """Test zero returns returns historical series alone."""
    def test_zero_returns_returns_historical_series_alone(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test zero returns returns historical series alone."""
        _write_ladder(ladder_repo, "known")

        response = service.get_projection(
            "known", projection_date=date(2020, 6, 1), returns=[], start=date(2019, 6, 3)
        )

        assert response.positions == ["Historical"]


# --- Unsupported return name --------------------------------------------------


class TestUnsupportedReturnRaisesUnsupportedAttributeError:
    """Test unsupported return raises unsupported attribute error."""
    def test_unsupported_return_raises_unsupported_attribute_error(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test unsupported return raises unsupported attribute error."""
        _write_ladder(ladder_repo, "known")

        with pytest.raises(UnsupportedAttributeError):
            service.get_projection(
                "known", projection_date=date(2030, 1, 2), returns=["bogus"]
            )


# --- Periodicity applied to both legs (Polish, T022) -------------------------


class TestPeriodicityIsAppliedToBothHistoricalAndProjectedLegs:
    """Test periodicity is applied to both historical and projected legs."""
    def test_annual_periodicity_buckets_both_legs(
        self, ladder_repo: LadderRepository, service: ProjectionService
    ) -> None:
        """Test annual periodicity buckets both legs."""
        _write_ladder(ladder_repo, "known")
        resolved_start = date(2019, 6, 3)
        projection_date = date(2022, 6, 1)

        response = service.get_projection(
            "known",
            projection_date=projection_date,
            returns=["3Y"],
            start=resolved_start,
            periodicity=Periodicity.ANNUAL,
        )

        historical_dates = sorted(e.date for e in response.entries if e.position == "Historical")
        projected_dates = sorted(e.date for e in response.entries if e.position == "3Y")
        # Far fewer than one point per business day on each leg.
        assert len(historical_dates) < 5
        assert len(projected_dates) < 5
        assert len(set(historical_dates) & set(projected_dates)) == 0 or resolved_start in (
            set(historical_dates) & set(projected_dates)
        )
