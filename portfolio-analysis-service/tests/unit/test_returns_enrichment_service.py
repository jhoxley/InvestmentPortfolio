"""Unit tests for ReturnsEnrichmentService."""

from datetime import date

import pandas as pd
import pytest

from app.services.returns_enrichment_service import ReturnsEnrichmentService


def _row(
    row_date: date,
    sub_account: str,
    *,
    quantity: float,
    total_income: float,
    price: float,
    portfolio_weight: float,
    book_cost: float = 0.0,
) -> dict[str, object]:
    """Build a single priced-ladder-row dict for test DataFrame construction."""
    return {
        "date": row_date,
        "sub_account": sub_account,
        "book_cost": book_cost,
        "quantity": quantity,
        "total_income": total_income,
        "price": price,
        "market_value": price * quantity,
        "portfolio_weight": portfolio_weight,
    }


def _service() -> ReturnsEnrichmentService:
    """Build a ReturnsEnrichmentService instance (no constructor dependencies)."""
    return ReturnsEnrichmentService()


def _row_for(df: pd.DataFrame, sub_account: str, row_date: date) -> pd.Series:
    """Fetch the single row matching (sub_account, date) from a result DataFrame."""
    match = df[(df["sub_account"] == sub_account) & (df["date"] == row_date)]
    assert len(match) == 1, (
        f"Expected exactly one row for {sub_account}/{row_date}, got {len(match)}"
    )
    return match.iloc[0]


def test_first_recorded_date_has_zero_position_return_and_zero_weighted_return() -> None:
    """A sub-account's first-ever row has both new columns exactly 0.0."""
    df = pd.DataFrame(
        [
            _row(
                date(2024, 1, 2),
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=100.0,
                portfolio_weight=0.5,
            )
        ]
    )
    result = _service().enrich(df)
    row = _row_for(result, "Equities A", date(2024, 1, 2))
    assert row["position_return"] == 0.0
    assert row["weighted_position_return"] == 0.0


def test_position_return_matches_price_change_plus_income_per_share() -> None:
    """position_return matches spec.md's User Story 1 worked example across four dates."""
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]
    prices = [100.0, 102.0, 101.0, 103.0]
    total_income = [0.0, 0.0, 5.0, 5.0]
    df = pd.DataFrame(
        [
            _row(
                d,
                "Equities A",
                quantity=10.0,
                total_income=ti,
                price=p,
                portfolio_weight=1.0,
            )
            for d, p, ti in zip(dates, prices, total_income, strict=True)
        ]
    )
    result = _service().enrich(df)

    row_03 = _row_for(result, "Equities A", date(2024, 1, 3))
    assert row_03["position_return"] == pytest.approx((102.0 - 100.0 + 0.0) / 100.0)

    row_04 = _row_for(result, "Equities A", date(2024, 1, 4))
    assert row_04["position_return"] == pytest.approx((101.0 - 102.0 + 0.5) / 102.0)

    row_05 = _row_for(result, "Equities A", date(2024, 1, 5))
    assert row_05["position_return"] == pytest.approx((103.0 - 101.0 + 0.0) / 101.0)


def test_weighted_return_uses_previous_row_portfolio_weight_not_same_row() -> None:
    """weighted_position_return uses the T-1 portfolio_weight, not the same-date weight.

    This is the critical regression test for the spec.md "Correction 2026-07-26" defect,
    where the original (incorrect) formula used the same-date portfolio_weight.
    """
    d1, d2 = date(2024, 3, 3), date(2024, 3, 4)
    df = pd.DataFrame(
        [
            _row(
                d1,
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=100.0,
                portfolio_weight=0.55,
            ),
            _row(
                d1,
                "Equities B",
                quantity=10.0,
                total_income=0.0,
                price=100.0,
                portfolio_weight=0.45,
            ),
            _row(
                d2, "Equities A", quantity=10.0, total_income=0.0, price=102.0, portfolio_weight=0.6
            ),
            _row(
                d2, "Equities B", quantity=10.0, total_income=0.0, price=99.0, portfolio_weight=0.4
            ),
        ]
    )
    result = _service().enrich(df)

    row_a = _row_for(result, "Equities A", d2)
    assert row_a["position_return"] == pytest.approx(0.02)
    assert row_a["weighted_position_return"] == pytest.approx(0.011)
    assert row_a["weighted_position_return"] != pytest.approx(0.012)

    row_b = _row_for(result, "Equities B", d2)
    assert row_b["position_return"] == pytest.approx(-0.01)
    assert row_b["weighted_position_return"] == pytest.approx(-0.0045)
    assert row_b["weighted_position_return"] != pytest.approx(-0.004)


def test_zero_quantity_treats_income_per_share_as_zero() -> None:
    """A zero-quantity row does not raise and treats income_per_share as 0 (FR-005)."""
    d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
    df = pd.DataFrame(
        [
            _row(
                d1, "Equities A", quantity=10.0, total_income=0.0, price=100.0, portfolio_weight=0.5
            ),
            _row(
                d2, "Equities A", quantity=0.0, total_income=5.0, price=105.0, portfolio_weight=0.0
            ),
        ]
    )
    result = _service().enrich(df)
    row = _row_for(result, "Equities A", d2)
    assert row["position_return"] == pytest.approx((105.0 - 100.0 + 0.0) / 100.0)


def test_zero_previous_price_yields_zero_return_not_division_error() -> None:
    """A defensive zero-previous-price row yields 0.0, not an exception or inf/NaN."""
    d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
    df = pd.DataFrame(
        [
            _row(
                d1, "Equities A", quantity=10.0, total_income=0.0, price=0.0, portfolio_weight=0.5
            ),
            _row(
                d2, "Equities A", quantity=10.0, total_income=0.0, price=10.0, portfolio_weight=0.5
            ),
        ]
    )
    result = _service().enrich(df)
    row = _row_for(result, "Equities A", d2)
    assert row["position_return"] == 0.0
    assert row["weighted_position_return"] == 0.0


def test_cash_naturally_returns_zero_with_no_special_case() -> None:
    """Cash (constant price=1.0, no income) naturally yields 0.0 with no special-cased logic."""
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    df = pd.DataFrame(
        [
            _row(d, "Cash", quantity=1000.0, total_income=0.0, price=1.0, portfolio_weight=0.2)
            for d in dates
        ]
    )
    result = _service().enrich(df)
    for d in dates[1:]:
        row = _row_for(result, "Cash", d)
        assert row["position_return"] == 0.0
        assert row["weighted_position_return"] == 0.0


def test_gap_in_history_treated_as_new_first_date() -> None:
    """A sub-account row following a multi-week gap is treated as a fresh first date (0.0).

    LadderExpander expands to consecutive business days while a position is active, so the
    maximum real gap between two adjacent rows is 3 calendar days (Friday to Monday); a gap
    this large (~2 months) cannot occur from a single ingestion today (research.md), but this
    documents defensive behaviour per spec.md's Edge Cases and SC-002.
    """
    df = pd.DataFrame(
        [
            _row(
                date(2024, 1, 2),
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=100.0,
                portfolio_weight=0.5,
            ),
            _row(
                date(2024, 1, 3),
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=101.0,
                portfolio_weight=0.5,
            ),
            _row(
                date(2024, 3, 1),
                "Equities A",
                quantity=5.0,
                total_income=0.0,
                price=150.0,
                portfolio_weight=0.3,
            ),
        ]
    )
    result = _service().enrich(df)
    row = _row_for(result, "Equities A", date(2024, 3, 1))
    assert row["position_return"] == 0.0
    assert row["weighted_position_return"] == 0.0


def test_weekend_adjacent_rows_not_treated_as_gap() -> None:
    """A normal Friday-to-Monday 3-calendar-day gap is NOT treated as a history gap."""
    friday, monday = date(2024, 1, 5), date(2024, 1, 8)
    df = pd.DataFrame(
        [
            _row(
                friday,
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=100.0,
                portfolio_weight=0.5,
            ),
            _row(
                monday,
                "Equities A",
                quantity=10.0,
                total_income=0.0,
                price=102.0,
                portfolio_weight=0.5,
            ),
        ]
    )
    result = _service().enrich(df)
    row = _row_for(result, "Equities A", monday)
    assert row["position_return"] == pytest.approx((102.0 - 100.0 + 0.0) / 100.0)
    assert row["position_return"] != 0.0


def test_multiple_sub_accounts_computed_independently() -> None:
    """shift(1) never crosses sub-account boundaries, regardless of input row order."""
    d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
    df = pd.DataFrame(
        [
            _row(
                d1, "Equities B", quantity=5.0, total_income=0.0, price=50.0, portfolio_weight=0.3
            ),
            _row(
                d1, "Equities A", quantity=10.0, total_income=0.0, price=100.0, portfolio_weight=0.5
            ),
            _row(
                d2, "Equities A", quantity=10.0, total_income=0.0, price=110.0, portfolio_weight=0.5
            ),
            _row(
                d2, "Equities B", quantity=5.0, total_income=0.0, price=55.0, portfolio_weight=0.3
            ),
        ]
    )
    result = _service().enrich(df)

    row_a_first = _row_for(result, "Equities A", d1)
    assert row_a_first["position_return"] == 0.0

    row_b_first = _row_for(result, "Equities B", d1)
    assert row_b_first["position_return"] == 0.0

    row_a_second = _row_for(result, "Equities A", d2)
    assert row_a_second["position_return"] == pytest.approx((110.0 - 100.0) / 100.0)

    row_b_second = _row_for(result, "Equities B", d2)
    assert row_b_second["position_return"] == pytest.approx((55.0 - 50.0) / 50.0)
