from __future__ import annotations

import logging
import uuid
from argparse import ArgumentParser, Namespace
from pathlib import Path

import pandas as pd

from src.constants import EXIT_INVALID_ARGS, EXIT_SUCCESS
from src.context import ExecutionContext
from src.modes.create_subaccount_ledger.constants import (
    CASH_SUB_ACCOUNT,
    COMPLETION_MSG,
    LEDGER_COL_SUB_ACCOUNT,
    LOG_CORRELATION_ID,
)
from src.modes.create_subaccount_ledger.engine import SubAccountLedgerEngine

_logger = logging.getLogger("pipeline.modes.create_subaccount_ledger")


class CreateSubAccountLedgerMode:
    name = "create_subaccount_ledger"
    description = "Consolidate one or more ledger XLSX files into a sub-account summary"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "output_path",
            metavar="OUTPUT_PATH",
            help="Path for the sub-account ledger output XLSX.",
        )
        parser.add_argument(
            "--capital",
            nargs="+",
            required=True,
            metavar="LEDGER",
            help="One or more capital ledger XLSX files.",
        )
        parser.add_argument(
            "--income",
            nargs="*",
            default=[],
            metavar="LEDGER",
            help="Zero or more income ledger XLSX files.",
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        correlation_id = str(uuid.uuid4())[:8]
        output_path = Path(args.output_path)
        capital_paths = [Path(p) for p in args.capital]
        income_paths = [Path(p) for p in (args.income or [])]

        _logger.info(
            "create_subaccount_ledger started",
            extra={
                LOG_CORRELATION_ID: correlation_id,
                "capital_file_count": len(capital_paths),
                "income_file_count": len(income_paths),
                "output_path": str(output_path),
            },
        )

        for path in capital_paths:
            if not path.exists():
                _logger.error(
                    "Capital ledger file not found",
                    extra={LOG_CORRELATION_ID: correlation_id, "missing_file": str(path)},
                )
                print(f"Error: capital ledger not found: {path}", flush=True)
                return EXIT_INVALID_ARGS

        capital_dfs = [pd.read_excel(p, engine="openpyxl") for p in capital_paths]

        income_dfs_raw = [pd.read_excel(p, engine="openpyxl") for p in income_paths]
        income_dfs = [
            df[df[LEDGER_COL_SUB_ACCOUNT] != CASH_SUB_ACCOUNT].reset_index(drop=True)
            for df in income_dfs_raw
        ]

        result = SubAccountLedgerEngine().run(capital_dfs=capital_dfs, income_dfs=income_dfs)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result.to_excel(writer, index=False)

        rows_written = len(result)
        _logger.info(
            COMPLETION_MSG,
            extra={
                LOG_CORRELATION_ID: correlation_id,
                "rows_written": rows_written,
                "output_path": str(output_path),
            },
        )

        return EXIT_SUCCESS
