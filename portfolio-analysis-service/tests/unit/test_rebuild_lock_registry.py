"""Unit tests for RebuildLockRegistry's per-(account, resource) serialisation (014)."""

import threading
import time

from app.services.rebuild.rebuild_lock_registry import RebuildLockRegistry


class TestSameKeySerialises:
    """Two concurrent callers for the same (account, resource) key serialise."""

    def test_same_key_serialises(self) -> None:
        """The second caller only enters its critical section after the first exits."""
        registry = RebuildLockRegistry()
        order: list[str] = []
        first_in_critical_section = threading.Event()

        def first() -> None:
            lock = registry.lock_for("acct-a", "ladder")
            with lock:
                order.append("first-start")
                first_in_critical_section.set()
                time.sleep(0.1)
                order.append("first-end")

        def second() -> None:
            first_in_critical_section.wait()
            lock = registry.lock_for("acct-a", "ladder")
            with lock:
                order.append("second-start")

        t1 = threading.Thread(target=first)
        t2 = threading.Thread(target=second)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert order == ["first-start", "first-end", "second-start"]


class TestDifferentKeysDoNotBlockEachOther:
    """Different (account, resource) keys get independent locks."""

    def test_different_account_keys_do_not_block(self) -> None:
        """Two different accounts' locks can be held simultaneously."""
        registry = RebuildLockRegistry()
        both_held = threading.Event()
        results: list[bool] = []

        def hold_a() -> None:
            with registry.lock_for("acct-a", "ladder"):
                time.sleep(0.2)

        def hold_b_and_check() -> None:
            start = time.monotonic()
            with registry.lock_for("acct-b", "ladder"):
                elapsed = time.monotonic() - start
                results.append(elapsed < 0.1)
                both_held.set()

        t1 = threading.Thread(target=hold_a)
        t1.start()
        time.sleep(0.02)
        t2 = threading.Thread(target=hold_b_and_check)
        t2.start()
        t2.join()
        t1.join()

        assert results == [True]

    def test_different_resource_keys_for_same_account_do_not_block(self) -> None:
        """The ladder and capital locks for the same account are independent."""
        registry = RebuildLockRegistry()
        ladder_lock = registry.lock_for("acct-a", "ladder")
        capital_lock = registry.lock_for("acct-a", "capital")
        assert ladder_lock is not capital_lock

    def test_same_key_returns_the_same_lock_instance(self) -> None:
        """Repeated lookups for the same key return the identical Lock object."""
        registry = RebuildLockRegistry()
        assert registry.lock_for("acct-a", "ladder") is registry.lock_for("acct-a", "ladder")
