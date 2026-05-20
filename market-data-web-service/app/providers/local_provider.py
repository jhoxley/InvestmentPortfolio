from datetime import date

import structlog

from app.exceptions import DataNotFoundError, ProviderUnavailableError
from app.models.fallback import FallbackEntry
from app.providers import PricingProvider

logger = structlog.get_logger(__name__)


class LocalPricingProvider(PricingProvider):
    def __init__(self, entry: FallbackEntry) -> None:
        self._entry = entry

    def get_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        import pandas as pd
        from dateutil import parser as dateutil_parser

        logger.debug(
            "local_csv_read_start", ticker=ticker, path=str(self._entry.csv_path)
        )

        try:
            df = pd.read_csv(self._entry.csv_path, dtype=str)
        except FileNotFoundError as exc:
            logger.error(
                "local_csv_not_found", ticker=ticker, path=str(self._entry.csv_path)
            )
            raise ProviderUnavailableError(
                f"Fallback CSV file not found: {self._entry.csv_path}"
            ) from exc

        if self._entry.date_column not in df.columns:
            raise ProviderUnavailableError(
                f"Date column '{self._entry.date_column}' not found in "
                f"{self._entry.csv_path}"
            )
        if self._entry.price_column not in df.columns:
            raise ProviderUnavailableError(
                f"Price column '{self._entry.price_column}' not found in "
                f"{self._entry.csv_path}"
            )

        results: list[tuple[date, float]] = []
        for _, row in df.iterrows():
            try:
                parsed_date = dateutil_parser.parse(str(row[self._entry.date_column])).date()
                price = float(row[self._entry.price_column])
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue
            results.append((parsed_date, price))

        if not results:
            logger.warning(
                "local_csv_empty", ticker=ticker, path=str(self._entry.csv_path)
            )
            raise DataNotFoundError(ticker)

        results.sort(key=lambda x: x[0])
        logger.debug(
            "local_csv_read_ok",
            ticker=ticker,
            path=str(self._entry.csv_path),
            row_count=len(results),
        )
        return results

    def get_current_price(self, ticker: str) -> dict[str, object]:
        from datetime import date as _date

        all_rows = self.get_price_history(ticker, _date(2000, 1, 1), _date.today())
        as_of_date, price = all_rows[-1]
        return {
            "price": price,
            "as_of_date": as_of_date,
            "currency": self._entry.currency,
            "market_state": None,
        }
