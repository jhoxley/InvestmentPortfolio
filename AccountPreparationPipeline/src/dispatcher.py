from __future__ import annotations

import logging
import sys
from argparse import Namespace

from src.constants import (
    EXIT_EXECUTION_FAILURE,
    EXIT_UNKNOWN_MODE,
    LOG_CORRELATION_ID,
    LOG_MODE_NAME,
)
from src.context import ExecutionContext
from src.registry import ModeRegistry

_logger = logging.getLogger("pipeline.dispatcher")


def dispatch(
    registry: ModeRegistry,
    context: ExecutionContext,
    args: Namespace,
) -> int:
    if not registry.contains(context.mode_name):
        valid_modes = ", ".join(m.name for m in registry.list_all())
        _logger.warning(
            "Unrecognised mode requested",
            extra={
                LOG_CORRELATION_ID: context.correlation_id,
                LOG_MODE_NAME: context.mode_name,
                "valid_modes": valid_modes,
            },
        )
        print(
            f"Error: unrecognised mode '{context.mode_name}'.\nValid modes: {valid_modes}",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN_MODE

    mode = registry.get(context.mode_name)
    _logger.info(
        "Dispatching to mode",
        extra={
            LOG_CORRELATION_ID: context.correlation_id,
            LOG_MODE_NAME: context.mode_name,
        },
    )

    try:
        exit_code: int = mode.execute(context, args)
    except Exception as exc:
        _logger.error(
            "Mode execution failed with unhandled exception",
            extra={
                LOG_CORRELATION_ID: context.correlation_id,
                LOG_MODE_NAME: context.mode_name,
                "error": str(exc),
            },
        )
        print(
            f"Error: mode '{context.mode_name}' failed — {exc}",
            file=sys.stderr,
        )
        return EXIT_EXECUTION_FAILURE

    _logger.info(
        "Mode execution complete",
        extra={
            LOG_CORRELATION_ID: context.correlation_id,
            LOG_MODE_NAME: context.mode_name,
            "exit_code": exit_code,
        },
    )
    return exit_code
