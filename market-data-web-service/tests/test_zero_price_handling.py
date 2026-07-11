from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.exceptions import DataNotFoundError
from app.models.fallback import FallbackEntry
from app.providers.local_provider import LocalPricingProvider
from app.providers.yfinance_provider import YFinanceProvider


def _write_csv(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    csv_path = tmp_path / "prices.csv"
    lines = ["Date,Close"] + [f"{d},{c}" for d, c in rows]
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path


def _entry(csv_path: Path, use_local_only: bool) -> FallbackEntry:
    return FallbackEntry(
        csv_path=csv_path,
        currency="GBP",
        date_column="Date",
        price_column="Close",
        use_local_only=use_local_only,
    )


# --- LocalPricingProvider: use_local_only=True allows zero/negative through ---


def test_local_only_true_keeps_zero_price(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("2025-01-02", "0"), ("2025-01-06", "0")])
    provider = LocalPricingProvider(_entry(csv_path, use_local_only=True))

    result = provider.get_price_history(
        "PRIV01", date(2025, 1, 1), date(2025, 1, 10)
    )

    assert result == [(date(2025, 1, 2), 0.0), (date(2025, 1, 6), 0.0)]


def test_local_only_true_keeps_negative_price(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("2025-01-02", "-5.00")])
    provider = LocalPricingProvider(_entry(csv_path, use_local_only=True))

    result = provider.get_price_history(
        "PRIV01", date(2025, 1, 1), date(2025, 1, 10)
    )

    assert result == [(date(2025, 1, 2), -5.00)]


def test_local_only_true_current_price_can_be_zero(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("2025-01-02", "100.00"), ("2025-01-06", "0")])
    provider = LocalPricingProvider(_entry(csv_path, use_local_only=True))

    raw = provider.get_current_price("PRIV01")

    assert raw["price"] == 0.0
    assert raw["as_of_date"] == date(2025, 1, 6)


# --- LocalPricingProvider: use_local_only=False (triggered fallback) still filters ---


def test_local_only_false_filters_zero_price(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("2025-01-02", "100.00"), ("2025-01-06", "0")])
    provider = LocalPricingProvider(_entry(csv_path, use_local_only=False))

    result = provider.get_price_history(
        "PRIV01", date(2025, 1, 1), date(2025, 1, 10)
    )

    assert result == [(date(2025, 1, 2), 100.00)]


def test_local_only_false_all_zero_raises_not_found(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("2025-01-02", "0"), ("2025-01-06", "0")])
    provider = LocalPricingProvider(_entry(csv_path, use_local_only=False))

    with pytest.raises(DataNotFoundError):
        provider.get_price_history("PRIV01", date(2025, 1, 1), date(2025, 1, 10))


# --- YFinanceProvider: zero/negative closes are always filtered, regardless of source ---


def _mock_history_df(rows: list[tuple[str, float]]) -> pd.DataFrame:
    index = pd.to_datetime([d for d, _ in rows])
    return pd.DataFrame({"Close": [c for _, c in rows]}, index=index)


@patch("app.providers.yfinance_provider.yf.Ticker")
def test_yfinance_history_filters_zero_close(mock_ticker_cls: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_history_df(
        [("2025-01-02", 100.00), ("2025-01-03", 0.0), ("2025-01-06", 110.00)]
    )
    mock_ticker_cls.return_value = mock_ticker

    result = YFinanceProvider().get_price_history(
        "AAPL", date(2025, 1, 1), date(2025, 1, 10)
    )

    assert result == [(date(2025, 1, 2), 100.00), (date(2025, 1, 6), 110.00)]


@patch("app.providers.yfinance_provider.yf.Ticker")
def test_yfinance_history_all_zero_raises_not_found(mock_ticker_cls: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_history_df(
        [("2025-01-02", 0.0), ("2025-01-03", 0.0)]
    )
    mock_ticker_cls.return_value = mock_ticker

    with pytest.raises(DataNotFoundError):
        YFinanceProvider().get_price_history("AAPL", date(2025, 1, 1), date(2025, 1, 10))


@patch("app.providers.yfinance_provider.yf.Ticker")
def test_yfinance_current_price_filters_zero_close(mock_ticker_cls: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_history_df(
        [("2025-01-05", 0.0), ("2025-01-06", 110.00)]
    )
    mock_ticker.fast_info.currency = "USD"
    mock_ticker.info = {"marketState": "REGULAR"}
    mock_ticker_cls.return_value = mock_ticker

    raw = YFinanceProvider().get_current_price("AAPL")

    assert raw["price"] == 110.00
    assert raw["as_of_date"] == date(2025, 1, 6)


@patch("app.providers.yfinance_provider.yf.Ticker")
def test_yfinance_current_price_all_zero_raises_not_found(mock_ticker_cls: MagicMock) -> None:
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _mock_history_df(
        [("2025-01-05", 0.0), ("2025-01-06", 0.0)]
    )
    mock_ticker_cls.return_value = mock_ticker

    with pytest.raises(DataNotFoundError):
        YFinanceProvider().get_current_price("AAPL")
