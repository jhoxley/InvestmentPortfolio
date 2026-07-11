"""BDD step implementations for market_data_config.feature (US4)."""

import io
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from app.api.ladder import _get_identifier_mapping_repository, _get_market_data_client
from app.config import IdentifierMappingSettings, MarketDataServiceSettings, Settings

scenarios("market_data_config.feature")


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict."""
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def _ledger_bytes() -> bytes:
    """Build a minimal valid XLSX ledger with Cash and one equity sub-account."""
    today = date.today()
    d1 = today - timedelta(days=30)
    rows = [
        {
            "date": d1,
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": d1,
            "sub_account": "Equity A",
            "book_cost": 500.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@given(
    "portfolio-analysis-service is configured with an alternate market data service location",
    target_fixture="alt_settings",
)
def alternate_market_data_location() -> Settings:
    """Build Settings with a distinctive, non-default market data service base_url."""
    return Settings(
        market_data_service=MarketDataServiceSettings(
            base_url="http://198.51.100.1:9999", timeout_seconds=5.0
        )
    )


@when("a ledger is ingested for an account requiring market data")
def ingest_requiring_market_data() -> None:
    """No-op: this scenario asserts on DI wiring directly rather than a live HTTP call."""


@then("the price-history requests are sent to the configured location")
def check_client_uses_configured_location(alt_settings: Settings) -> None:
    """Assert the DI-constructed client is bound to the configured base_url."""
    client = _get_market_data_client(settings=alt_settings)
    assert client._client.base_url == alt_settings.market_data_service.base_url


@given(
    "portfolio-analysis-service is configured with an alternate identifier mapping source",
    target_fixture="alt_settings",
)
def alternate_identifier_mapping_source(tmp_path: Path) -> Settings:
    """Build Settings pointing at a real temp mapping file with a known entry."""
    mapping_path = tmp_path / "alt-mapping.json"
    mapping_path.write_text(
        json.dumps([{"name": "Equity A", "ticker": "EQA-ALT"}]), encoding="utf-8"
    )
    return Settings(identifier_mapping=IdentifierMappingSettings(path=mapping_path))


@when("a ledger is ingested")
def ingest_generic() -> None:
    """No-op: this scenario asserts on DI wiring directly rather than a live HTTP call."""


@then("the sub-account-to-identifier lookups use the configured mapping source")
def check_repository_uses_configured_path(alt_settings: Settings) -> None:
    """Assert the DI-constructed repository reads from the configured mapping file."""
    repo = _get_identifier_mapping_repository(settings=alt_settings)
    entry = repo.lookup("Equity A")
    assert entry is not None
    assert entry.ticker == "EQA-ALT"


@given(
    "the end-to-end run script defines market data service host and port variables",
    target_fixture="e2e_script_text",
)
def e2e_script_text() -> str:
    """Read run_end_to_end.ps1's source text from the repo root, skipping if absent."""
    repo_root_script = Path(__file__).resolve().parents[3] / "run_end_to_end.ps1"
    if not repo_root_script.exists():
        pytest.skip(f"run_end_to_end.ps1 not found at {repo_root_script}")
    return repo_root_script.read_text(encoding="utf-8")


@then("the portfolio-analysis-service config block it writes uses those same variables")
def check_e2e_script_wiring(e2e_script_text: str) -> None:
    """Assert the analysis-service config block references the shared host/port variables."""
    assert "MarketDataHost" in e2e_script_text
    assert "MarketDataPort" in e2e_script_text
    marker = e2e_script_text.index("$analysisDefaultConfig")
    config_block = e2e_script_text[marker : marker + 800]
    assert "market_data_service:" in config_block
    assert "MarketDataHost" in config_block
    assert "MarketDataPort" in config_block
