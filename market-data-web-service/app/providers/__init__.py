from abc import ABC, abstractmethod
from datetime import date


class PricingProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> dict[str, object]:
        ...

    @abstractmethod
    def get_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        ...
