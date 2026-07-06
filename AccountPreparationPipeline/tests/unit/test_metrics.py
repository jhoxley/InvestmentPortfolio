from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from src.constants import METRICS_EVENT
from src.metrics import MetricsRecord, emit_metrics


def _make_record(duration_secs: float = 1.5, exit_status: int = 0) -> MetricsRecord:
    start = datetime(2026, 5, 31, 10, 0, 0, tzinfo=UTC)
    end = start + timedelta(seconds=duration_secs)
    return MetricsRecord(
        correlation_id="test-id",
        mode_name="example",
        start_time=start,
        end_time=end,
        exit_status=exit_status,
    )


def test_duration_seconds_computed_correctly() -> None:
    record = _make_record(duration_secs=2.5)
    assert record.duration_seconds == pytest.approx(2.5)


def test_duration_seconds_zero() -> None:
    start = datetime(2026, 5, 31, 10, 0, 0, tzinfo=UTC)
    record = MetricsRecord(
        correlation_id="id",
        mode_name="m",
        start_time=start,
        end_time=start,
        exit_status=0,
    )
    assert record.duration_seconds == pytest.approx(0.0)


def test_emit_metrics_logs_info_record(caplog: pytest.LogCaptureFixture) -> None:
    record = _make_record()
    logger = logging.getLogger("test.metrics")
    with caplog.at_level(logging.INFO, logger="test.metrics"):
        emit_metrics(record, logger)
    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.levelno == logging.INFO


def test_emit_metrics_includes_event_field(caplog: pytest.LogCaptureFixture) -> None:
    record = _make_record()
    logger = logging.getLogger("test.metrics.event")
    with caplog.at_level(logging.INFO, logger="test.metrics.event"):
        emit_metrics(record, logger)
    assert hasattr(caplog.records[0], "event")
    assert caplog.records[0].event == METRICS_EVENT  # type: ignore[attr-defined]


def test_emit_metrics_includes_correlation_id(caplog: pytest.LogCaptureFixture) -> None:
    record = _make_record()
    logger = logging.getLogger("test.metrics.corr")
    with caplog.at_level(logging.INFO, logger="test.metrics.corr"):
        emit_metrics(record, logger)
    assert caplog.records[0].correlation_id == "test-id"  # type: ignore[attr-defined]
