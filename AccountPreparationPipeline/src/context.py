from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ExecutionContext:
    correlation_id: str
    start_time: datetime
    mode_name: str
    raw_args: tuple[str, ...]

    @classmethod
    def create(cls, mode_name: str, raw_args: list[str]) -> ExecutionContext:
        return cls(
            correlation_id=str(uuid.uuid4()),
            start_time=datetime.now(UTC),
            mode_name=mode_name,
            raw_args=tuple(raw_args),
        )
