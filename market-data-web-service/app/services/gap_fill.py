from datetime import date, timedelta

import structlog

logger = structlog.get_logger(__name__)


class GapFillService:
    """Fills Mon-Fri business day gaps in a price or rate series."""

    def fill(
        self,
        observations: list[tuple[date, float]],
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, float]]:
        """Return a complete Mon-Fri series for [from_date, to_date].

        - Empty observations → returns [].
        - Dates before the first observation → back-filled with first price.
        - Dates after the last observation or within gaps → forward-filled.
        - Weekend days are never included in the output.
        """
        if not observations:
            return []

        obs_map: dict[date, float] = dict(observations)
        first_obs_price = min(observations, key=lambda x: x[0])[1]

        result: list[tuple[date, float]] = []
        last_price: float | None = None
        current = from_date

        while current <= to_date:
            if current.weekday() < 5:
                if current in obs_map:
                    last_price = obs_map[current]
                    result.append((current, last_price))
                elif last_price is None:
                    result.append((current, first_obs_price))
                else:
                    result.append((current, last_price))
            current += timedelta(days=1)

        gaps_filled = len(result) - len([o for o in observations if from_date <= o[0] <= to_date])
        logger.info(
            "gap_fill_applied",
            from_date=str(from_date),
            to_date=str(to_date),
            raw_observations=len(observations),
            filled_count=len(result),
            gaps_filled=max(gaps_filled, 0),
        )

        return result
