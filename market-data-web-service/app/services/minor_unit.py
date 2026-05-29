from datetime import date

import structlog

_logger = structlog.get_logger(__name__)

_MINOR_UNIT_MAP: dict[str, tuple[str, float]] = {
    "GBp": ("GBP", 100.0),
    "USd": ("USD", 100.0),
}


class SubUnitNormaliser:
    def is_minor_unit(self, currency: str) -> bool:
        if len(currency) < 3:
            return False
        # First two chars → uppercase; third char case is the minor/major discriminator.
        canonical = currency[:2].upper() + currency[2]
        return canonical in _MINOR_UNIT_MAP

    def normalise(self, currency: str, price: float) -> tuple[str, float]:
        if not self.is_minor_unit(currency):
            return currency, price
        canonical = currency[:2].upper() + currency[2]
        major_code, divisor = _MINOR_UNIT_MAP[canonical]
        _logger.debug(
            "sub_unit_normalised",
            from_currency=currency,
            to_currency=major_code,
            divisor=divisor,
        )
        return major_code, price / divisor

    def normalise_series(
        self,
        currency: str,
        series: list[tuple[date, float]],
    ) -> tuple[str, list[tuple[date, float]]]:
        if not self.is_minor_unit(currency):
            return currency, series
        canonical = currency[:2].upper() + currency[2]
        major_code, divisor = _MINOR_UNIT_MAP[canonical]
        _logger.debug(
            "sub_unit_series_normalised",
            from_currency=currency,
            to_currency=major_code,
            divisor=divisor,
            count=len(series),
        )
        return major_code, [(d, v / divisor) for d, v in series]
