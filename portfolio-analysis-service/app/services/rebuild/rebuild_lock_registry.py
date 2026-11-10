"""In-process lock registry serialising rebuilds per (account, resource).

Mirrors the single-process, in-memory locking pattern already used by
`app.services.var.run_scheduler.ThreadRunScheduler` for serialising VaR runs: this is a
single-process FastAPI deployment, so an in-memory `threading.Lock` per key is sufficient
and avoids introducing a distributed-locking dependency this service doesn't otherwise need.
"""

import threading
from typing import Literal

Resource = Literal["ladder", "capital"]


class RebuildLockRegistry:
    """Lazily creates and returns one `threading.Lock` per (account_name, resource) key."""

    def __init__(self) -> None:
        """Initialise with an empty lock map, guarded by one outer lock."""
        self._locks: dict[tuple[str, Resource], threading.Lock] = {}
        self._outer_lock = threading.Lock()

    def lock_for(self, account_name: str, resource: Resource) -> threading.Lock:
        """Return the lock for a given (account_name, resource) key, creating it if needed.

        Args:
            account_name: The account identifier.
            resource: Which resource's rebuild this lock serialises ("ladder" or "capital").

        Returns:
            The `threading.Lock` instance for this key. The same key always returns the
            same Lock instance for the lifetime of this registry.
        """
        key = (account_name, resource)
        if key not in self._locks:
            with self._outer_lock:
                if key not in self._locks:
                    self._locks[key] = threading.Lock()
        return self._locks[key]


_default_registry: RebuildLockRegistry | None = None
_default_registry_lock = threading.Lock()


def get_default_rebuild_lock_registry() -> RebuildLockRegistry:
    """Return the process-wide singleton RebuildLockRegistry, creating it on first call.

    A new `RebuildLockRegistry()` per request (as FastAPI's `Depends` would otherwise
    construct) would defeat the point — each request would get its own, never-shared
    lock map. Every caller must go through this accessor to actually serialise
    concurrent rebuilds for the same (account, resource).

    Returns:
        The shared RebuildLockRegistry instance.
    """
    global _default_registry
    if _default_registry is None:
        with _default_registry_lock:
            if _default_registry is None:
                _default_registry = RebuildLockRegistry()
    return _default_registry
