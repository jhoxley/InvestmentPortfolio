"""Unit tests for building per-date position exposures from a position ladder."""

from collections.abc import Callable
from datetime import date

import pandas as pd
import pytest

from app.models.market_data import IdentifierMappingEntry
from app.services.var.exposures import build_exposures


def _lookup(
    entries: dict[str, IdentifierMappingEntry],
) -> Callable[[str], IdentifierMappingEntry | None]:
    return lambda sub_account: entries.get(sub_account)


def _ladder_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {
        "book_cost": 0.0,
        "total_income": 0.0,
        "price": 1.0,
        "portfolio_weight": 0.0,
        "position_return": 0.0,
        "weighted_position_return": 0.0,
    }
    return pd.DataFrame([{**base, **row} for row in rows])


class TestBuildExposures:
    """build_exposures() turns ladder rows into per-date Exposure objects."""

    def test_cash_excluded_from_positions_but_recorded(self) -> None:
        """Cash contributes to cash_value and total_value but is not a position."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Cash",
                    "quantity": 1000.0,
                    "market_value": 1000.0,
                },
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A",
                    "quantity": 10.0,
                    "market_value": 5000.0,
                },
            ]
        )
        lookup = _lookup({"Equity A": IdentifierMappingEntry(name="Equity A", ticker="EQA.L")})

        exposures = build_exposures(df, lookup)

        exp = exposures[date(2026, 3, 2)]
        assert exp.cash_value == pytest.approx(1000.0)
        assert [p.identifier for p in exp.positions] == ["EQA.L"]
        assert exp.risky_value == pytest.approx(5000.0)
        assert exp.total_value == pytest.approx(6000.0)

    def test_zero_market_value_position_excluded(self) -> None:
        """A non-Cash position with market_value 0 is excluded from positions and risky_value."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Cash",
                    "quantity": 1000.0,
                    "market_value": 1000.0,
                },
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Dead Fund",
                    "quantity": 100.0,
                    "market_value": 0.0,
                },
            ]
        )
        lookup = _lookup({"Dead Fund": IdentifierMappingEntry(name="Dead Fund", ticker="DEAD.L")})

        exposures = build_exposures(df, lookup)

        exp = exposures[date(2026, 3, 2)]
        assert exp.positions == ()
        assert exp.risky_value == pytest.approx(0.0)
        assert exp.total_value == pytest.approx(1000.0)

    def test_zero_quantity_position_excluded(self) -> None:
        """A non-Cash position with quantity 0 is excluded even if market_value is nonzero."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Cash",
                    "quantity": 1000.0,
                    "market_value": 1000.0,
                },
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A",
                    "quantity": 0.0,
                    "market_value": 5.0,
                },
            ]
        )
        lookup = _lookup({"Equity A": IdentifierMappingEntry(name="Equity A", ticker="EQA.L")})

        exposures = build_exposures(df, lookup)

        assert exposures[date(2026, 3, 2)].positions == ()

    def test_identifier_prefers_ticker_over_isin(self) -> None:
        """A position's identifier is ticker if set, else isin (same rule as pricing)."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A",
                    "quantity": 10.0,
                    "market_value": 100.0,
                },
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity B",
                    "quantity": 10.0,
                    "market_value": 100.0,
                },
            ]
        )
        lookup = _lookup(
            {
                "Equity A": IdentifierMappingEntry(name="Equity A", ticker="EQA.L", isin="GB00EQA"),
                "Equity B": IdentifierMappingEntry(name="Equity B", isin="GB00EQB"),
            }
        )

        exposures = build_exposures(df, lookup)
        by_sub_account = {
            p.sub_account: p.identifier for p in exposures[date(2026, 3, 2)].positions
        }

        assert by_sub_account["Equity A"] == "EQA.L"
        assert by_sub_account["Equity B"] == "GB00EQB"

    def test_two_sub_accounts_sharing_one_identifier_stay_separate_positions(self) -> None:
        """Two sub-accounts mapped to the same identifier remain two distinct positions."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A Class 1",
                    "quantity": 10.0,
                    "market_value": 100.0,
                },
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A Class 2",
                    "quantity": 20.0,
                    "market_value": 200.0,
                },
            ]
        )
        lookup = _lookup(
            {
                "Equity A Class 1": IdentifierMappingEntry(name="Equity A Class 1", ticker="EQA.L"),
                "Equity A Class 2": IdentifierMappingEntry(name="Equity A Class 2", ticker="EQA.L"),
            }
        )

        exposures = build_exposures(df, lookup)
        positions = exposures[date(2026, 3, 2)].positions

        assert len(positions) == 2
        assert {p.sub_account for p in positions} == {"Equity A Class 1", "Equity A Class 2"}
        assert exposures[date(2026, 3, 2)].risky_value == pytest.approx(300.0)

    def test_multiple_dates_each_get_their_own_exposure(self) -> None:
        """build_exposures() returns one Exposure per distinct ladder date."""
        df = _ladder_df(
            [
                {
                    "date": date(2026, 3, 2),
                    "sub_account": "Equity A",
                    "quantity": 10.0,
                    "market_value": 100.0,
                },
                {
                    "date": date(2026, 3, 3),
                    "sub_account": "Equity A",
                    "quantity": 10.0,
                    "market_value": 110.0,
                },
            ]
        )
        lookup = _lookup({"Equity A": IdentifierMappingEntry(name="Equity A", ticker="EQA.L")})

        exposures = build_exposures(df, lookup)

        assert set(exposures.keys()) == {date(2026, 3, 2), date(2026, 3, 3)}
        assert exposures[date(2026, 3, 3)].risky_value == pytest.approx(110.0)
