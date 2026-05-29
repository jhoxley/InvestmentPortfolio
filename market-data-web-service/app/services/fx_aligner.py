from bisect import bisect_left, bisect_right
from datetime import date

from app.exceptions import FxAlignmentError


class AlignedRate:
    """Result of aligning a single security date to an FX rate."""

    __slots__ = ("fill_direction", "fx_date", "rate")

    def __init__(self, rate: float, fx_date: date, fill_direction: str) -> None:
        self.rate = rate
        self.fx_date = fx_date
        self.fill_direction = fill_direction  # "exact", "forward", or "backward"


class FxAligner:
    """Maps each security trading date to the nearest available FX rate.

    Forward-fill first (most recent prior rate); backward-fill as fallback
    (nearest subsequent rate). Raises FxAlignmentError if neither is possible.
    """

    def align_rates(
        self,
        pair: str,
        security_dates: list[date],
        fx_series: list[tuple[date, float]],
    ) -> dict[date, AlignedRate]:
        fx_map = dict(fx_series)
        sorted_fx_dates = sorted(fx_map.keys())
        result: dict[date, AlignedRate] = {}

        for sec_date in security_dates:
            if sec_date in fx_map:
                result[sec_date] = AlignedRate(fx_map[sec_date], sec_date, "exact")
                continue

            idx = bisect_right(sorted_fx_dates, sec_date) - 1
            if idx >= 0:
                fx_date = sorted_fx_dates[idx]
                result[sec_date] = AlignedRate(fx_map[fx_date], fx_date, "forward")
                continue

            idx = bisect_left(sorted_fx_dates, sec_date)
            if idx < len(sorted_fx_dates):
                fx_date = sorted_fx_dates[idx]
                result[sec_date] = AlignedRate(fx_map[fx_date], fx_date, "backward")
                continue

            raise FxAlignmentError(pair=pair, security_date=sec_date)

        return result
