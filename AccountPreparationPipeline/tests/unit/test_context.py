from __future__ import annotations

import uuid
from datetime import UTC

from src.context import ExecutionContext


def test_create_generates_valid_uuid4() -> None:
    ctx = ExecutionContext.create(mode_name="test", raw_args=["test"])
    try:
        parsed = uuid.UUID(ctx.correlation_id, version=4)
    except ValueError as exc:
        raise AssertionError(f"correlation_id is not a valid UUID4: {ctx.correlation_id}") from exc
    assert str(parsed) == ctx.correlation_id


def test_create_sets_utc_aware_timestamp() -> None:
    ctx = ExecutionContext.create(mode_name="test", raw_args=[])
    assert ctx.start_time.tzinfo is not None
    assert ctx.start_time.tzinfo == UTC


def test_create_preserves_mode_name() -> None:
    ctx = ExecutionContext.create(mode_name="example", raw_args=[])
    assert ctx.mode_name == "example"


def test_create_preserves_raw_args() -> None:
    args = ["example", "--message", "hello"]
    ctx = ExecutionContext.create(mode_name="example", raw_args=args)
    assert ctx.raw_args == tuple(args)


def test_context_is_immutable() -> None:
    ctx = ExecutionContext.create(mode_name="test", raw_args=[])
    try:
        ctx.mode_name = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AssertionError:
        raise
    except Exception:
        pass


def test_two_contexts_have_different_correlation_ids() -> None:
    ctx1 = ExecutionContext.create(mode_name="test", raw_args=[])
    ctx2 = ExecutionContext.create(mode_name="test", raw_args=[])
    assert ctx1.correlation_id != ctx2.correlation_id
