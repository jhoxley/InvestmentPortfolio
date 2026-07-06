from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

import pandas as pd

from src.constants import EXIT_INVALID_ARGS, EXIT_SUCCESS
from src.context import ExecutionContext
from src.modes.create_capital_ledger.constants import (
    COMPLETION_MSG,
    LOG_CCL_CORRELATION_ID,
)
from src.modes.create_capital_ledger.engine import CapitalLedgerEngine

_logger = logging.getLogger("pipeline.modes.create_capital_ledger")


class CreateCapitalLedgerMode:
    name = "create_capital_ledger"
    description = "Build a date-level capital summary from a create_ledger output XLSX"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "input_path",
            metavar="INPUT_PATH",
            help="Path to a ledger XLSX produced by create_ledger.",
        )
        parser.add_argument(
            "output_path",
            metavar="OUTPUT_PATH",
            help="Path for the capital ledger output XLSX. Parent directory must exist.",
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        input_path = Path(args.input_path)
        output_path = Path(args.output_path)

        _logger.info(
            "create_capital_ledger started",
            extra={
                LOG_CCL_CORRELATION_ID: context.correlation_id,
                "input_path": str(input_path),
                "output_path": str(output_path),
            },
        )

        if not input_path.exists():
            _logger.error(
                "Invalid input ledger",
                extra={"detail": f"Input file not found: {input_path}"},
            )
            return EXIT_INVALID_ARGS

        df = pd.read_excel(input_path, engine="openpyxl")

        try:
            result = CapitalLedgerEngine().run(df)
        except ValueError as exc:
            _logger.error("Invalid input ledger", extra={"detail": str(exc)})
            return EXIT_INVALID_ARGS

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result.to_excel(writer, index=False)

        rows = len(result)
        _logger.info(
            COMPLETION_MSG,
            extra={
                LOG_CCL_CORRELATION_ID: context.correlation_id,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "rows_written": rows,
            },
        )

        return EXIT_SUCCESS
