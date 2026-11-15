"""Shared "check staleness, serialise, rebuild if needed" orchestration (014).

Every date-range-bearing read service (TimeSeriesService, PositionTimeSeriesService,
PerformanceService, DailyReturnSeriesLoader) calls `ensure_fresh()` right after resolving
its request's date range and before reading the stored ladder/capital frame. Factored out
once so the staleness check, lock acquisition, post-lock re-check (FR-005/US2), and the
FR-013 total-unavailability fallback are implemented identically everywhere, rather than
duplicated per service.
"""

from collections.abc import Callable
from datetime import date
from typing import Literal, Protocol

import structlog

from app.exceptions import RebuildUnavailableError
from app.services.rebuild.rebuild_lock_registry import RebuildLockRegistry
from app.services.rebuild.staleness_gate import StalenessGate

logger = structlog.get_logger(__name__)

Resource = Literal["ladder", "capital"]


class Rebuilder(Protocol):
    """Abstraction over LadderRebuildService/CapitalRebuildService for ensure_fresh()."""

    def rebuild(self, account_name: str, rebuild_target_end: date) -> None:
        """Extend the stored resource through rebuild_target_end.

        Args:
            account_name: The account whose resource is stale.
            rebuild_target_end: The capped target end date.

        Raises:
            RebuildUnavailableError: If no pricing at all could be sourced (ladder only).
        """
        ...


def ensure_fresh(
    *,
    account_name: str,
    resource: Resource,
    last_known_date: date,
    resolved_end: date,
    today: date,
    lock_registry: RebuildLockRegistry,
    staleness_gate: StalenessGate,
    rebuilder: Rebuilder,
    read_last_known_date: Callable[[], date],
) -> None:
    """Rebuild `resource` for `account_name` if the resolved request is stale.

    Args:
        account_name: The account identifier.
        resource: Which resource this check is for ("ladder" or "capital").
        last_known_date: The resource's last-ingested-or-rebuilt date as already known to
            the caller (a cheap pre-check, avoiding a lock acquisition when clearly fresh).
        resolved_end: The request's resolved end date.
        today: The current date.
        lock_registry: The shared RebuildLockRegistry.
        staleness_gate: The shared StalenessGate.
        rebuilder: The LadderRebuildService or CapitalRebuildService to invoke.
        read_last_known_date: Re-reads the resource's current last-known date. Called only
            after the lock is acquired, so a caller that waited on another rebuild sees its
            result and correctly skips re-rebuilding (FR-005, US2).
    """
    decision = staleness_gate.evaluate(last_known_date, resolved_end, today)
    if not decision.rebuild_needed:
        return

    lock = lock_registry.lock_for(account_name, resource)
    with lock:
        current_last_known = read_last_known_date()
        decision = staleness_gate.evaluate(current_last_known, resolved_end, today)
        if not decision.rebuild_needed:
            logger.info(
                "rebuild_skipped_already_fresh", account_name=account_name, resource=resource
            )
            return

        logger.info(
            "rebuild_triggered",
            account_name=account_name,
            resource=resource,
            rebuild_target_end=str(decision.rebuild_target_end),
        )
        try:
            rebuilder.rebuild(account_name, decision.rebuild_target_end)
        except RebuildUnavailableError:
            logger.warning(
                "rebuild_fallback_total_unavailable", account_name=account_name, resource=resource
            )
            return
        logger.info("rebuild_complete", account_name=account_name, resource=resource)
