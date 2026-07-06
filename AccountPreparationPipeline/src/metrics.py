from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from src.constants import LOG_CORRELATION_ID, LOG_EVENT, LOG_MODE_NAME, METRICS_EVENT


@dataclass(frozen=True)
class MetricsRecord:
    correlation_id: str
    mode_name: str
    start_time: datetime
    end_time: datetime
    exit_status: int

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


def emit_metrics(record: MetricsRecord, logger: logging.Logger) -> None:
    logger.info(
        "Execution metrics",
        extra={
            LOG_EVENT: METRICS_EVENT,
            LOG_CORRELATION_ID: record.correlation_id,
            LOG_MODE_NAME: record.mode_name,
            "start_time": record.start_time.isoformat(),
            "end_time": record.end_time.isoformat(),
            "duration_seconds": record.duration_seconds,
            "exit_status": record.exit_status,
        },
    )
