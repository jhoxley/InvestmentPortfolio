from datetime import date
from typing import Protocol

import structlog

from app.models.fill import FillMode
from app.services.gap_fill import GapFillService

logger = structlog.get_logger(__name__)


class SeriesFiller(Protocol):
    """Shapes a raw observation series into the series the client asked for.

    GapFillService satisfies this protocol structurally — its existing `fill` method has
    exactly this signature — so no edit to it was needed to add a second strategy.
    """

    def fill(
        self,
        observations: list[tuple[date, float]],
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, float]]:
        ...


class ObservedOnlyFiller:
    """Returns only real observations, clipped to the requested range.

    Manufactures no dates: the output's dates are always a subset of the input's, which is
    the invariant behind FR-005 and FR-008. Weekend-dated observations are retained — a real
    observation is an observation, and only the Mon-Fri grid is a gap-fill construct.
    """

    def fill(
        self,
        observations: list[tuple[date, float]],
        from_date: date,
        to_date: date,
    ) -> list[tuple[date, float]]:
        # De-duplicate by date keeping the last value, matching CacheRepository.write.
        deduped: dict[date, float] = dict(observations)

        result = sorted(
            (d, v) for d, v in deduped.items() if from_date <= d <= to_date
        )

        logger.info(
            "observed_only_applied",
            from_date=str(from_date),
            to_date=str(to_date),
            raw_observations=len(observations),
            returned_count=len(result),
        )

        return result


class FillStrategyResolver:
    """Maps a FillMode to the strategy that implements it."""

    def __init__(self, gap_fill: GapFillService, observed_only: ObservedOnlyFiller) -> None:
        self._strategies: dict[FillMode, SeriesFiller] = {
            FillMode.ALL: gap_fill,
            FillMode.NONE: observed_only,
        }

    def resolve(self, mode: FillMode) -> SeriesFiller:
        return self._strategies[mode]
