"""Unit tests for PricingEnrichmentService."""

from datetime import date

import pandas as pd
import pytest

from app.exceptions import IdentifierMappingError, PriceCoverageError
from app.models.market_data import PriceHistoryPoint
from app.services.pricing_enrichment_service import PricingEnrichmentService
from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService


def _ladder_df() -> pd.DataFrame:
    """Return a small two-sub-account, two-date base ladder for enrichment tests."""
    d1 = date(2024, 1, 2)
    d2 = date(2024, 1, 3)
    return pd.DataFrame(
        {
            "date": [d1, d1, d2, d2],
            "sub_account": ["Cash", "Equity A", "Cash", "Equity A"],
            "book_cost": [1000.0, 500.0, 1000.0, 500.0],
            "quantity": [1000.0, 10.0, 1000.0, 10.0],
            "total_income": [0.0, 0.0, 0.0, 0.0],
        }
    )


def _service(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> PricingEnrichmentService:
    """Build a PricingEnrichmentService wired to the given fakes."""
    return PricingEnrichmentService(
        mapping_repo=fake_identifier_mapping_repository,
        market_data_client=fake_market_data_service.client(),
    )


def test_cash_priced_at_one_gbp_no_mapping_lookup(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """Cash rows are priced at 1.0 GBP without any mapping lookup or client call."""
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    result = service.enrich(_ladder_df())
    cash_rows = result[result["sub_account"] == "Cash"]
    assert (cash_rows["price"] == 1.0).all()
    assert fake_market_data_service.calls_for("Cash") == []


def test_market_value_equals_price_times_quantity(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """market_value is computed as price times quantity for every row."""
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    result = service.enrich(_ladder_df())
    assert (result["market_value"] == result["price"] * result["quantity"]).all()


def test_portfolio_weight_sums_to_one_per_date(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """portfolio_weight sums to 1.0 (within tolerance) across sub-accounts for every date."""
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    result = service.enrich(_ladder_df())
    sums = result.groupby("date")["portfolio_weight"].sum()
    for total in sums:
        assert total == pytest.approx(1.0, abs=0.0001)


def test_portfolio_weight_is_zero_when_total_market_value_is_zero(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """portfolio_weight is 0 (not a division error) when a date's total market value is zero."""
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    df = pd.DataFrame(
        {
            "date": [date(2024, 1, 2)],
            "sub_account": ["Cash"],
            "book_cost": [0.0],
            "quantity": [0.0],
            "total_income": [0.0],
        }
    )
    result = service.enrich(df)
    assert result.iloc[0]["portfolio_weight"] == 0.0


def test_ticker_preferred_over_isin_when_both_present(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """When a mapping entry has both ticker and isin, ticker is used to request prices."""
    fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA", isin="GB00EXAMPLE1")
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    service.enrich(_ladder_df())
    assert len(fake_market_data_service.calls_for("EQA")) == 1
    assert fake_market_data_service.calls_for("GB00EXAMPLE1") == []


def test_missing_mapping_entry_raises_identifier_mapping_error(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """A sub-account with no mapping entry at all raises IdentifierMappingError."""
    fake_identifier_mapping_repository.set_missing("Equity A")
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    with pytest.raises(IdentifierMappingError) as exc_info:
        service.enrich(_ladder_df())
    assert "Equity A" in exc_info.value.sub_accounts


def test_mapping_entry_with_neither_isin_nor_ticker_raises(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """A mapping entry with neither ticker nor isin populated is treated as missing."""
    fake_identifier_mapping_repository.set_entry("Equity A")
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    with pytest.raises(IdentifierMappingError) as exc_info:
        service.enrich(_ladder_df())
    assert "Equity A" in exc_info.value.sub_accounts


def test_gap_in_returned_prices_raises_price_coverage_error(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """A missing date in the returned price history raises PriceCoverageError."""
    fake_market_data_service.configure_prices(
        "Equity A", [PriceHistoryPoint(date=date(2024, 1, 2), close=100.0)]
    )
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)
    with pytest.raises(PriceCoverageError) as exc_info:
        service.enrich(_ladder_df())
    assert date(2024, 1, 3) in exc_info.value.problems["Equity A"]


def test_multiple_sub_account_problems_reported_in_one_error(
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """Both a missing-mapping and a missing-price problem are named in one raised error."""
    d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
    df = pd.DataFrame(
        {
            "date": [d1, d1, d1, d2, d2, d2],
            "sub_account": ["Cash", "Equity A", "Equity D", "Cash", "Equity A", "Equity D"],
            "book_cost": [1000.0, 500.0, 500.0, 1000.0, 500.0, 500.0],
            "quantity": [1000.0, 10.0, 5.0, 1000.0, 10.0, 5.0],
            "total_income": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    fake_market_data_service.configure_prices("Equity A", [PriceHistoryPoint(date=d1, close=100.0)])
    fake_identifier_mapping_repository.set_missing("Equity D")
    service = _service(fake_identifier_mapping_repository, fake_market_data_service)

    with pytest.raises(PriceCoverageError) as exc_info:
        service.enrich(df)

    problems = exc_info.value.problems
    assert d2 in problems["Equity A"]
    assert problems["Equity D"] == []
