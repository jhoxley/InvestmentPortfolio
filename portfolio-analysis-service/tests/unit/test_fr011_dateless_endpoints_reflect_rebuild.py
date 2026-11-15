"""FR-011 coverage: date-less endpoints reflect a rebuild triggered elsewhere (014).

These endpoints take no date range of their own and so never evaluate staleness or
trigger a rebuild themselves -- they simply read whatever is currently persisted. This
test proves that once another endpoint (here, /timeseries or /position) triggers and
persists a rebuild, these endpoints' next read already shows the advanced state, with no
production code of their own needing to know about rebuilds at all.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.models.market_data import PriceHistoryPoint
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from tests.conftest import FakeMarketDataService

_LAST_INGESTED = date(2026, 9, 23)
_REQUEST_END = date(2026, 9, 25)


def _seed_ladder(tmp_path: Path, account_name: str) -> None:
    """Write a minimal stale ladder directly into app_client's own data directory.

    Args:
        tmp_path: The same tmp_path the app_client fixture roots its data directory in.
        account_name: Target account name.
    """
    ladder_repo = LadderRepository(data_dir=tmp_path / "data")
    df = pd.DataFrame(
        {
            "date": [_LAST_INGESTED],
            "sub_account": ["Equity A"],
            "book_cost": [500.0],
            "quantity": [10.0],
            "total_income": [0.0],
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
        from_date=_LAST_INGESTED,
        to_date=_LAST_INGESTED,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    ladder_repo.write(account_name, df, meta)


class TestDatelessEndpointsReflectARebuildTriggeredElsewhere:
    """Ladder summary, accounts list, and positions enumeration show the rebuilt state."""

    def test_ladder_summary_reflects_rebuild(
        self,
        tmp_path: Path,
        app_client: TestClient,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """GET .../ladder shows the advanced to_date after a rebuild triggered by /timeseries."""
        _seed_ladder(tmp_path, "HL-ISA")
        fake_market_data_service.configure_prices(
            "Equity A", [PriceHistoryPoint(date=date(2026, 9, 24), close=51.0)]
        )

        timeseries_resp = app_client.get(
            "/v1/accounts/HL-ISA/timeseries",
            params=[
                ("attribute", "market_value"),
                ("start", str(_LAST_INGESTED)),
                ("end", str(_REQUEST_END)),
            ],
        )
        assert timeseries_resp.status_code == 200

        ladder_summary = app_client.get("/v1/accounts/HL-ISA/ladder")
        assert ladder_summary.status_code == 200
        assert date.fromisoformat(ladder_summary.json()["to_date"]) >= date(2026, 9, 24)

    def test_accounts_list_reflects_rebuild(
        self,
        tmp_path: Path,
        app_client: TestClient,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """GET /v1/accounts shows the advanced to_date after a rebuild triggered elsewhere."""
        _seed_ladder(tmp_path, "HL-SIPP")
        fake_market_data_service.configure_prices(
            "Equity A", [PriceHistoryPoint(date=date(2026, 9, 24), close=51.0)]
        )

        position_resp = app_client.get(
            "/v1/accounts/HL-SIPP/position",
            params=[
                ("attribute", "market_value"),
                ("start", str(_LAST_INGESTED)),
                ("end", str(_REQUEST_END)),
            ],
        )
        assert position_resp.status_code == 200

        accounts_resp = app_client.get("/v1/accounts")
        assert accounts_resp.status_code == 200
        entry = next(a for a in accounts_resp.json()["accounts"] if a["account_name"] == "HL-SIPP")
        assert date.fromisoformat(entry["position_ladder"]["to_date"]) >= date(2026, 9, 24)

    def test_positions_enumeration_reflects_rebuild_with_no_date_params(
        self,
        tmp_path: Path,
        app_client: TestClient,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """GET .../positions (plural, no date range) reflects the rebuild by construction."""
        _seed_ladder(tmp_path, "HL-POSITIONS")
        fake_market_data_service.configure_prices(
            "Equity A", [PriceHistoryPoint(date=date(2026, 9, 24), close=51.0)]
        )

        position_resp = app_client.get(
            "/v1/accounts/HL-POSITIONS/position",
            params=[
                ("attribute", "market_value"),
                ("start", str(_LAST_INGESTED)),
                ("end", str(_REQUEST_END)),
            ],
        )
        assert position_resp.status_code == 200

        positions_resp = app_client.get("/v1/accounts/HL-POSITIONS/positions")
        assert positions_resp.status_code == 200
        entry = next(p for p in positions_resp.json()["positions"] if p["position"] == "Equity A")
        assert date.fromisoformat(entry["to_date"]) >= date(2026, 9, 24)
