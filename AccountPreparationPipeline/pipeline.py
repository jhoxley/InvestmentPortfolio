#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from src.constants import (
    DEFAULT_LOG_LEVEL,
    EXIT_SUCCESS,
    EXIT_UNKNOWN_MODE,
    LOG_CORRELATION_ID,
    LOG_MODE_NAME,
)
from src.context import ExecutionContext
from src.dispatcher import dispatch
from src.logging_config import configure_logging
from src.metrics import MetricsRecord, emit_metrics
from src.modes.consolidate_journals.mode import ConsolidateJournalsMode
from src.modes.example.mode import ExampleMode
from src.registry import ModeRegistry


def _build_registry() -> ModeRegistry:
    registry = ModeRegistry()
    registry.register(ExampleMode())
    registry.register(ConsolidateJournalsMode())
    return registry


def _build_parser(registry: ModeRegistry) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Account Preparation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=DEFAULT_LOG_LEVEL,
        dest="log_level",
        help="Minimum log level for structured output (default: %(default)s).",
    )

    subparsers = parser.add_subparsers(
        title="Available modes",
        dest="mode",
        metavar="<mode>",
    )

    for mode in registry.list_all():
        sub = subparsers.add_parser(
            mode.name,
            help=mode.description,
            description=mode.description,
        )
        mode.register_arguments(sub)

    return parser


def _extract_mode_candidate(argv: list[str]) -> str | None:
    for arg in argv:
        if not arg.startswith("-"):
            return arg
    return None


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    registry = _build_registry()
    parser = _build_parser(registry)

    if not argv:
        parser.print_help()
        return EXIT_SUCCESS

    candidate = _extract_mode_candidate(argv)
    if candidate is not None and not registry.contains(candidate):
        valid_modes = ", ".join(m.name for m in registry.list_all())
        print(
            f"Error: unrecognised mode '{candidate}'.\nValid modes: {valid_modes}",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN_MODE

    args = parser.parse_args(argv)

    if args.mode is None:
        parser.print_help()
        return EXIT_SUCCESS

    logger = configure_logging(args.log_level)

    context = ExecutionContext.create(mode_name=args.mode, raw_args=argv)

    logger.info(
        "Pipeline started",
        extra={
            LOG_CORRELATION_ID: context.correlation_id,
            LOG_MODE_NAME: context.mode_name,
        },
    )

    exit_code = dispatch(registry, context, args)
    end_time = datetime.now(UTC)

    metrics = MetricsRecord(
        correlation_id=context.correlation_id,
        mode_name=context.mode_name,
        start_time=context.start_time,
        end_time=end_time,
        exit_status=exit_code,
    )
    emit_metrics(metrics, logger)

    logger.info(
        "Pipeline finished",
        extra={
            LOG_CORRELATION_ID: context.correlation_id,
            LOG_MODE_NAME: context.mode_name,
            "exit_code": exit_code,
        },
    )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
