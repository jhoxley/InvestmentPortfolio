import datetime
from typing import Optional
from urllib.parse import quote

import pandas as pd
import requests


class MarketDataClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def resolve_ticker(self, identifier: str) -> Optional[str]:
        """Return the ticker for an ISIN/CUSIP/SEDOL, or None if not found or unresolvable."""
        try:
            resp = self._session.get(
                f"{self._base_url}/identifiers/{quote(identifier, safe='')}",
                timeout=30,
            )
            if resp.status_code in (404, 422):
                return None
            resp.raise_for_status()
            return resp.json()["ticker"]
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Market data service unavailable when resolving {identifier}: {exc}"
            ) from exc

    def get_price_history(
        self,
        ticker: str,
        from_date: datetime.date | datetime.datetime,
        to_date: datetime.date | datetime.datetime,
        multiplier: float = 1.0,
    ) -> pd.DataFrame:
        """Return a DataFrame with 'Settle date' (datetime64) and 'Close' (float) columns.
        The 'Close' price is multiplied by the given multiplier (default 1.0) to adjust for any necessary scaling.
        """
        if isinstance(from_date, datetime.datetime):
            from_date = from_date.date()
        if isinstance(to_date, datetime.datetime):
            to_date = to_date.date()

        params: dict = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        
        params["currency"] = "GBP"

        try:
            resp = self._session.get(
                f"{self._base_url}/securities/{quote(ticker, safe='')}/history",
                params=params,
                timeout=60,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Market data service error for {ticker}: {exc}") from exc

        prices = resp.json().get("prices", [])
        if not prices:
            return None

        df = pd.DataFrame([{"Settle date": p["date"], "Close": p["close"]} for p in prices])
        df["Settle date"] = pd.to_datetime(df["Settle date"])
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

        if multiplier != 1.0:
            df["Close"] = df["Close"] * multiplier

        return df
