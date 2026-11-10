"""Unit tests for IngestionService's supersession of a previously rebuilt span (014)."""

import io
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import MergeNotSupportedError
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.ingestion_service import IngestionService
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.returns_enrichment_service import ReturnsEnrichmentService
from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService

_INGESTED_THROUGH = date(2026, 9, 23)  # Wednesday
_PROJECTED_THROUGH = date(2026, 11, 6)  # Friday, well past _INGESTED_THROUGH


@pytest.fixture()
def ladder_repo(tmp_path: Path) -> LadderRepository:
    """Return a tmp_path-backed LadderRepository.

    Returns:
        LadderRepository ready for use in tests.
    """
    return LadderRepository(data_dir=tmp_path)


def _seed_rebuilt_ladder(repo: LadderRepository, account_name: str) -> None:
    """Write a ladder with a genuine ingested/projected split, as a real rebuild would.

    Rows up to and including _INGESTED_THROUGH are provenance='ingested'; every business
    day after that through _PROJECTED_THROUGH is provenance='projected' (held-constant
    quantity, flat price), simulating the outcome of a 014 rebuild.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
    """
    ingested_days = pd.bdate_range(end=_INGESTED_THROUGH, periods=5)
    projected_days = pd.bdate_range(start=_INGESTED_THROUGH, end=_PROJECTED_THROUGH)[
        1:
    ]  # exclude _INGESTED_THROUGH itself

    rows = []
    for d in ingested_days:
        rows.append(
            {
                "date": d.date(),
                "sub_account": "Equity A",
                "book_cost": 500.0,
                "quantity": 10.0,
                "total_income": 0.0,
                "price": 50.0,
                "market_value": 500.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
                "provenance": "ingested",
            }
        )
    for d in projected_days:
        rows.append(
            {
                "date": d.date(),
                "sub_account": "Equity A",
                "book_cost": 500.0,
                "quantity": 10.0,
                "total_income": 0.0,
                "price": 50.0,
                "market_value": 500.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
                "provenance": "projected",
            }
        )
    df = pd.DataFrame(rows)
    meta = AccountMeta(
        account_name=account_name,
        checksum="original-checksum",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
        rebuilt_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _new_ledger_bytes(rows: list[dict[str, object]]) -> bytes:
    """Serialise an uploaded ledger's rows to XLSX bytes.

    Args:
        rows: Dicts with keys date, sub_account, book_cost, quantity, total_income.

    Returns:
        XLSX file contents as bytes.
    """
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _service(
    repo: LadderRepository,
    mapping_repo: FakeIdentifierMappingRepository,
    market_data: FakeMarketDataService,
) -> IngestionService:
    """Build an IngestionService wired to the given repository and pricing fakes.

    Returns:
        IngestionService ready for use in tests.
    """
    market_data_client = market_data.client()
    return IngestionService(
        repository=repo,
        enrichment_service=PricingEnrichmentService(
            mapping_repo=mapping_repo, market_data_client=market_data_client
        ),
        returns_service=ReturnsEnrichmentService(),
    )


class TestOverlappingLedgerSupersedesTheProjectedSpan:
    """A new ledger whose range overlaps a projected span is accepted and recomputed."""

    def test_overlapping_ledger_supersedes_projected_span(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """A trade dated inside the projected span is accepted, not rejected."""
        account_name = "acct-supersede"
        _seed_rebuilt_ladder(ladder_repo, account_name)
        trade_date = date(2026, 10, 15)  # inside the projected span

        new_ledger = _new_ledger_bytes(
            [
                {
                    "date": date(2026, 9, 1),
                    "sub_account": "Equity A",
                    "book_cost": 500.0,
                    "quantity": 10.0,
                    "total_income": 0.0,
                },
                {
                    "date": trade_date,
                    "sub_account": "Equity A",
                    "book_cost": 1000.0,
                    "quantity": 20.0,
                    "total_income": 0.0,
                },
            ]
        )

        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )
        summary = service.ingest(account_name, new_ledger, today=date(2026, 11, 10))

        assert summary.status == "created"
        result = ladder_repo.read_full_df(account_name)
        result = result.assign(date=pd.to_datetime(result["date"]).dt.date)
        after_trade = result[result["date"] >= trade_date]
        # The new quantity is correctly carried forward regardless of provenance.
        assert (after_trade["quantity"] == 20.0).all()
        # The trade date itself is grounded in the newly uploaded ledger ("ingested");
        # dates beyond the new ledger's own last transaction are freshly re-projected
        # forward from it ("projected") and will need their own future rebuild/ingestion.
        trade_row = result[result["date"] == trade_date]
        assert (trade_row["provenance"] == "ingested").all()
        beyond_new_ledger = result[result["date"] > trade_date]
        assert (beyond_new_ledger["provenance"] == "projected").all()

    def test_dates_before_the_new_ledger_retain_their_original_values(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """A date entirely before the new ledger's own earliest row is unaffected."""
        account_name = "acct-supersede-prefix"
        _seed_rebuilt_ladder(ladder_repo, account_name)

        new_ledger = _new_ledger_bytes(
            [
                {
                    "date": date(2026, 10, 1),
                    "sub_account": "Equity A",
                    "book_cost": 500.0,
                    "quantity": 10.0,
                    "total_income": 0.0,
                },
                {
                    "date": date(2026, 10, 15),
                    "sub_account": "Equity A",
                    "book_cost": 1000.0,
                    "quantity": 20.0,
                    "total_income": 0.0,
                },
            ]
        )
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )

        service.ingest(account_name, new_ledger, today=date(2026, 11, 10))

        result = ladder_repo.read_full_df(account_name)
        result = result.assign(date=pd.to_datetime(result["date"]).dt.date)
        original_row = result[result["date"] == _INGESTED_THROUGH]
        assert (original_row["quantity"] == 10.0).all()
        assert (original_row["provenance"] == "ingested").all()


class TestNonOverlappingLedgerUnchangedBehaviour:
    """A new ledger with no overlap with any projected span is rejected as before."""

    def test_non_overlapping_ledger_raises_merge_not_supported(
        self,
        ladder_repo: LadderRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """A ledger confined to the already-ingested span still raises MergeNotSupportedError."""
        account_name = "acct-no-overlap"
        _seed_rebuilt_ladder(ladder_repo, account_name)

        new_ledger = _new_ledger_bytes(
            [
                {
                    "date": date(2026, 9, 1),
                    "sub_account": "Equity A",
                    "book_cost": 999.0,
                    "quantity": 99.0,
                    "total_income": 0.0,
                }
            ]
        )
        service = _service(
            ladder_repo, fake_identifier_mapping_repository, fake_market_data_service
        )

        with pytest.raises(MergeNotSupportedError):
            service.ingest(account_name, new_ledger, today=date(2026, 11, 10))

        meta = ladder_repo.read_meta(account_name)
        assert meta.checksum == "original-checksum"
