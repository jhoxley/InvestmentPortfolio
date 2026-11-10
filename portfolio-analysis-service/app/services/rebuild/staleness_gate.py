"""Decides whether a resource's stored data is stale relative to a request, and by how much."""

from dataclasses import dataclass
from datetime import date

from app.services.business_day_helpers import most_recent_business_day_on_or_before


@dataclass(frozen=True)
class RebuildDecision:
    """The outcome of a staleness check for one resource."""

    rebuild_needed: bool
    rebuild_target_end: date
    """The capped end date a rebuild should extend through, regardless of whether
    `rebuild_needed` is True -- always the prior-business-day cap for `today` (FR-003)."""


class StalenessGate:
    """Computes whether a rebuild is needed and the capped target end date for it."""

    def evaluate(self, last_known_date: date, resolved_end: date, today: date) -> RebuildDecision:
        """Decide whether a rebuild is needed to satisfy a request, and its target end date.

        Args:
            last_known_date: The resource's current last-ingested-or-rebuilt date
                (`AccountMeta.to_date` / `CapitalMeta.to_date`).
            resolved_end: The request's resolved end date.
            today: The current date, used to compute the prior-business-day cap.

        Returns:
            A RebuildDecision. `rebuild_target_end` is always the prior business day
            relative to `today` (FR-003) -- a rebuild never seeks data beyond it, even
            when `resolved_end` itself requests further forward in time (that excess is
            left to the existing flat-fill read path, unchanged by this feature).
        """
        rebuild_target_end = most_recent_business_day_on_or_before(today)
        rebuild_needed = resolved_end > last_known_date
        return RebuildDecision(rebuild_needed=rebuild_needed, rebuild_target_end=rebuild_target_end)
