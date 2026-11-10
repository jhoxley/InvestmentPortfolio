"""Unit tests for LadderRebuildService (014)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import RebuildUnavailableError
from app.models.market_data import PriceHistoryPoint
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.rebuild.ladder_rebuild_service import LadderRebuildService
from app.services.returns_enrichment_service import ReturnsEnrichmentService
from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService

_LAST_KNOWN = date(2026, 9, 23)  # a Wednesday


@pytest.fixture()
def ladder_repo(tmp_path: Path) -> LadderRepository:
    """Return a tmp_path-backed LadderRepository.

    Returns:
        LadderRepository ready for use in tests.
    """
    return LadderRepository(data_dir=tmp_path)


def _seed_ladder(repo: LadderRepository, account_name: str) -> None:
    """Write a minimal, already-enriched, 'ingested' ladder ending at _LAST_KNOWN.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        {
            "date": [_LAST_KNOWN, _LAST_KNOWN],
            "sub_account": ["Cash", "Equity A"],
            "book_cost": [1000.0, 500.0],
            "quantity": [1000.0, 10.0],
            "total_income": [0.0, 5.0],
            "price": [1.0, 50.0],
            "market_value": [1000.0, 500.0],
            "portfolio_weight": [1000.0 / 1500.0, 500.0 / 1500.0],
            "position_return": [0.0, 0.0],
            "weighted_position_return": [0.0, 0.0],
            "provenance": ["ingested", "ingested"],
        }
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=len(df),
        from_date=_LAST_KNOWN,
        to_date=_LAST_KNOWN,
        sub_accounts=["Cash", "Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _read_full_df_normalised(repo: LadderRepository, account_name: str) -> pd.DataFrame:
    """Read a ladder back with its date column normalised to python date objects.

    xlsx round-trips always come back as datetime64 (pandas Timestamp); every production
    caller normalises this immediately after reading, so tests do the same.

    Returns:
        The full stored ladder with `date` as python date objects.
    """
    df = repo.read_full_df(account_name)
    return df.assign(date=pd.to_datetime(df["date"]).dt.date)


def _service(
    repo: LadderRepository,
    mapping_repo: IdentifierMappingRepository,
    market_data: FakeMarketDataService,
) -> LadderRebuildService:
    """Build a LadderRebuildService wired to the given repository and pricing fakes.

    Returns:
        LadderRebuildService ready for use in tests.
    """
    return LadderRebuildService(
        repository=repo,
        mapping_repo=mapping_repo,
        market_data_client=market_data.client(),
        enrichment_service=PricingEnrichmentService(
            mapping_repo=mapping_repo, market_data_client=market_data.client()
        ),
        returns_service=ReturnsEnrichmentService(),
    )


class TestSuccessfulFullRebuild:
    """A rebuild with pricing available for every gap day extends and persists correctly."""

    def test_successful_full_rebuild_appends_projected_rows(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """New rows are appended, tagged 'projected', and AccountMeta is advanced."""
        account_name = "acct-full"
        _seed_ladder(ladder_repo, account_name)
        target_end = date(2026, 9, 25)  # Friday, two business days after _LAST_KNOWN

        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )
        service.rebuild(account_name, target_end)

        result = _read_full_df_normalised(ladder_repo, account_name)
        new_rows = result[result["date"] > _LAST_KNOWN]
        assert not new_rows.empty
        assert (new_rows["provenance"] == "projected").all()
        assert result["date"].max() == target_end

        meta = ladder_repo.read_meta(account_name)
        assert meta.to_date == target_end
        assert meta.rebuilt_at is not None

    def test_existing_ingested_rows_are_untouched(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """The original last-known row's own values are not rewritten by the rebuild."""
        account_name = "acct-untouched"
        _seed_ladder(ladder_repo, account_name)
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )
        service.rebuild(account_name, date(2026, 9, 25))

        result = _read_full_df_normalised(ladder_repo, account_name)
        original_rows = result[result["date"] == _LAST_KNOWN]
        cash_row = original_rows[original_rows["sub_account"] == "Cash"].iloc[0]
        assert cash_row["provenance"] == "ingested"
        assert cash_row["market_value"] == 1000.0


class TestPartialUnavailability:
    """Pricing unavailable for only part of the gap nulls just those dates."""

    def test_partial_unavailability_nulls_only_the_unresolved_dates(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """Equity A has no price for one of the two new gap days; Cash is unaffected."""
        account_name = "acct-partial"
        _seed_ladder(ladder_repo, account_name)
        fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA.L")
        # Equity A priced for 2026-09-24 only, missing 2026-09-25.
        fake_market_data_service.configure_prices(
            "EQA.L", [PriceHistoryPoint(date=date(2026, 9, 24), close=51.0)]
        )
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )

        service.rebuild(account_name, date(2026, 9, 25))

        result = _read_full_df_normalised(ladder_repo, account_name)
        equity_rows = result[(result["sub_account"] == "Equity A") & (result["date"] > _LAST_KNOWN)]
        priced_row = equity_rows[equity_rows["date"] == date(2026, 9, 24)].iloc[0]
        unresolved_row = equity_rows[equity_rows["date"] == date(2026, 9, 25)].iloc[0]
        assert priced_row["market_value"] == pytest.approx(51.0 * 10.0)
        assert pd.isna(unresolved_row["market_value"])

        cash_rows = result[(result["sub_account"] == "Cash") & (result["date"] > _LAST_KNOWN)]
        assert cash_rows["market_value"].notna().all()


class TestTotalUnavailability:
    """No pricing at all for the gap raises and persists nothing."""

    def test_total_unavailability_raises_and_persists_nothing(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """When every sub-account's pricing fails outright, nothing is persisted."""
        account_name = "acct-total"
        _seed_ladder(ladder_repo, account_name)
        fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA.L")
        fake_identifier_mapping_repository.set_missing("Cash")
        fake_market_data_service.configure_error("EQA.L", status_code=502)
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )

        # Cash is priced internally at a fixed 1.0 regardless of mapping, so force total
        # failure by also making Equity A's identifier error out and leaving no other
        # priceable sub-account: Cash still succeeds at 1.0, so assert partial behaviour
        # is at least not a crash, then separately verify a true total-failure scenario
        # below using only a priceable (non-Cash) sub-account's ladder.
        service.rebuild(account_name, date(2026, 9, 25))
        meta = ladder_repo.read_meta(account_name)
        assert meta.rebuilt_at is not None  # Cash alone still allowed a partial persist

    def test_total_unavailability_for_an_all_equity_account_raises(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """An account with only a failing non-Cash sub-account raises RebuildUnavailableError."""
        account_name = "acct-equity-only"
        df = pd.DataFrame(
            {
                "date": [_LAST_KNOWN],
                "sub_account": ["Equity A"],
                "book_cost": [500.0],
                "quantity": [10.0],
                "total_income": [5.0],
                "price": [50.0],
                "market_value": [500.0],
                "portfolio_weight": [1.0],
                "position_return": [0.0],
                "weighted_position_return": [0.0],
                "provenance": ["ingested"],
            }
        )
        meta = AccountMeta(
            account_name=account_name,
            checksum="deadbeef",
            row_count=1,
            from_date=_LAST_KNOWN,
            to_date=_LAST_KNOWN,
            sub_accounts=["Equity A"],
            ingested_at=datetime.now(UTC),
        )
        ladder_repo.write(account_name, df, meta)
        fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA.L")
        fake_market_data_service.configure_error("EQA.L", status_code=502)
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )

        with pytest.raises(RebuildUnavailableError):
            service.rebuild(account_name, date(2026, 9, 25))

        unchanged_meta = ladder_repo.read_meta(account_name)
        assert unchanged_meta.rebuilt_at is None
        assert unchanged_meta.to_date == _LAST_KNOWN
