"""Unit tests for RunScheduler implementations (InlineRunScheduler, ThreadRunScheduler)."""

import threading
import time
from collections.abc import Callable

from app.services.var.run_scheduler import InlineRunScheduler, ThreadRunScheduler


class TestInlineRunScheduler:
    """InlineRunScheduler runs submitted jobs synchronously, in the caller's thread."""

    def test_submit_runs_job_immediately_and_synchronously(self) -> None:
        """submit() returns only after the job has completed."""
        calls: list[int] = []
        scheduler = InlineRunScheduler()

        scheduler.submit(lambda: calls.append(1))

        assert calls == [1]

    def test_submit_runs_in_the_calling_thread(self) -> None:
        """The job observes the same thread identity as the caller."""
        seen_thread_id: list[int] = []
        scheduler = InlineRunScheduler()

        scheduler.submit(lambda: seen_thread_id.append(threading.get_ident()))

        assert seen_thread_id == [threading.get_ident()]


class TestThreadRunScheduler:
    """ThreadRunScheduler serialises jobs on a single background worker."""

    def test_jobs_run_one_after_another_not_overlapping(self) -> None:
        """Two submitted jobs' running intervals never overlap."""
        scheduler = ThreadRunScheduler()
        intervals: list[tuple[float, float]] = []
        lock = threading.Lock()
        done = threading.Event()

        def record(duration: float, is_last: bool) -> None:
            start = time.monotonic()
            time.sleep(duration)
            end = time.monotonic()
            with lock:
                intervals.append((start, end))
            if is_last:
                done.set()

        scheduler.submit(lambda: record(0.05, is_last=False))
        scheduler.submit(lambda: record(0.05, is_last=True))
        done.wait(timeout=5)
        scheduler.shutdown()

        assert len(intervals) == 2
        (_, end_a), (start_b, _) = intervals
        assert end_a <= start_b, "second job must not start before the first finished"

    def test_jobs_run_in_submission_order(self) -> None:
        """Submitted jobs execute in the order they were submitted."""
        scheduler = ThreadRunScheduler()
        order: list[int] = []
        done = threading.Event()

        def job(n: int, is_last: bool) -> Callable[[], None]:
            def run() -> None:
                order.append(n)
                if is_last:
                    done.set()

            return run

        for n in range(5):
            scheduler.submit(job(n, n == 4))
        done.wait(timeout=5)
        scheduler.shutdown()

        assert order == [0, 1, 2, 3, 4]

    def test_shutdown_waits_for_in_flight_work(self) -> None:
        """shutdown() blocks until any already-submitted job has finished."""
        scheduler = ThreadRunScheduler()
        finished = threading.Event()

        def slow_job() -> None:
            time.sleep(0.05)
            finished.set()

        scheduler.submit(slow_job)
        scheduler.shutdown()

        assert finished.is_set()
