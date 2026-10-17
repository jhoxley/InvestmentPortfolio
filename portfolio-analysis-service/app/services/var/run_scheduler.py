"""Background execution of VaR calculation runs.

A single-worker scheduler serialises run execution across every account: at most one
calculation runs at a time, in submission order. This is the entire "run queue" -- there
is no separate queue data structure, since `ThreadPoolExecutor(max_workers=1)` already is
one.
"""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import structlog

logger = structlog.get_logger(__name__)


class RunScheduler(Protocol):
    """Abstraction over how a VaR calculation run's job is executed."""

    def submit(self, job: Callable[[], None]) -> None:
        """Schedule a job for execution.

        Args:
            job: A zero-argument callable. Any exception it raises is logged and
                swallowed -- a job is expected to record its own failure (e.g. by
                writing a failed VarRun record) rather than relying on the scheduler.
        """
        ...

    def shutdown(self) -> None:
        """Wait for any in-flight job to finish, then stop accepting new ones."""
        ...


class InlineRunScheduler:
    """Runs a submitted job synchronously, in the caller's own thread.

    Used by tests so that a run's full execution is observable immediately after the
    triggering HTTP call returns, with no polling or waiting required.
    """

    def submit(self, job: Callable[[], None]) -> None:
        """Run the job immediately and synchronously.

        Args:
            job: A zero-argument callable, run in the calling thread before this method
                returns.
        """
        job()

    def shutdown(self) -> None:
        """No-op: there is no background worker to wait for."""


class ThreadRunScheduler:
    """Runs submitted jobs one at a time on a single background worker thread.

    Serialises run execution across every account (FR-018): the single worker is the
    entire queue, and jobs execute strictly in submission order.
    """

    def __init__(self) -> None:
        """Create the underlying single-worker executor lazily on first use."""
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

    def _get_executor(self) -> ThreadPoolExecutor:
        """Return the lazily created single-worker executor.

        Returns:
            The process-wide ThreadPoolExecutor backing this scheduler.
        """
        if self._executor is None:
            with self._lock:
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="var-run")
        return self._executor

    def submit(self, job: Callable[[], None]) -> None:
        """Submit a job to the single background worker.

        Args:
            job: A zero-argument callable. If it raises, the exception is logged and
                swallowed so one failing job can never kill the worker thread or stop
                later submissions from running.
        """

        def _run() -> None:
            try:
                job()
            except Exception:
                logger.exception("var_run_scheduler_job_failed")

        self._get_executor().submit(_run)

    def shutdown(self) -> None:
        """Wait for any in-flight or queued job to finish, then stop the worker."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)


_default_scheduler: ThreadRunScheduler | None = None
_default_scheduler_lock = threading.Lock()


def get_default_scheduler() -> ThreadRunScheduler:
    """Return the process-wide singleton ThreadRunScheduler, creating it on first call.

    Returns:
        The shared ThreadRunScheduler instance.
    """
    global _default_scheduler
    if _default_scheduler is None:
        with _default_scheduler_lock:
            if _default_scheduler is None:
                _default_scheduler = ThreadRunScheduler()
    return _default_scheduler
