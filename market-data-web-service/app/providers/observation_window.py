from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ObservationWindow:
    """Earliest and latest dates the service knows a real observation for an instrument.

    Derived from real observations only, never from gap-filled values, and never clipped to a
    requested range.
    """

    first_observed_date: date
    last_observed_date: date


@runtime_checkable
class ObservationWindowSource(Protocol):
    """Optional capability: report an instrument's known observation window.

    Deliberately separate from PricingProvider. A stateless source such as YFinanceProvider
    cannot answer what the service knows overall, so forcing this onto the provider ABC would
    mean a meaningless implementation there (Interface Segregation). Callers must treat the
    capability as optional and fall back to deriving extremes from the series they received.
    """

    def observation_window(self, ticker: str) -> ObservationWindow | None:
        ...
