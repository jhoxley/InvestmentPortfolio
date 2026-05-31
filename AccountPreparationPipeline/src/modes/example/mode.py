from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace

from src.constants import EXIT_SUCCESS, LOG_CORRELATION_ID, LOG_MODE_NAME
from src.context import ExecutionContext

_logger = logging.getLogger("pipeline.modes.example")


class ExampleMode:
    name = "example"
    description = "Placeholder mode for pipeline framework validation"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--message",
            required=True,
            metavar="TEXT",
            help=(
                "A text message to echo back. Required. Validates that argument "
                "passthrough and mode dispatch are functioning correctly."
            ),
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        _logger.info(
            "Example mode executing",
            extra={
                LOG_CORRELATION_ID: context.correlation_id,
                LOG_MODE_NAME: self.name,
                "mode_message": args.message,
            },
        )
        return EXIT_SUCCESS
