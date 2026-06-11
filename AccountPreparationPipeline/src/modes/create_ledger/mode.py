from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

import pandas as pd

from src.constants import EXIT_INVALID_ARGS, EXIT_SUCCESS
from src.context import ExecutionContext
from src.modes.consolidate_journals.constants import NUMBER_FORMAT_QUANTITY, NUMBER_FORMAT_VALUE
from src.modes.create_ledger.constants import (
    COMPLETION_MSG,
    LEDGER_COL_ACCOUNT_QUANTITY,
    LEDGER_COL_ACCOUNT_VALUE,
    LEDGER_COL_TRANSACTION_ID,
    LEDGER_COL_TRANSACTION_QUANTITY,
    LEDGER_COL_TRANSACTION_VALUE,
    LEDGER_COLUMNS,
    LOG_CL_CORRELATION_ID,
)
from src.modes.create_ledger.engine import LedgerEngine
from src.modes.create_ledger.transaction_id import _normalise_date

_logger = logging.getLogger("pipeline.modes.create_ledger")


def _load_prior_ids(
    output_path: Path,
) -> dict[tuple[str, str, str, str], str]:
    if not output_path.exists():
        return {}
    try:
        df = pd.read_excel(output_path, engine="openpyxl")
        if "Transaction ID" not in df.columns:
            return {}
        result: dict[tuple[str, str, str, str], str] = {}
        for _, row in df.iterrows():
            key = (
                _normalise_date(row["date"]),
                str(row["account"]),
                str(row["sub_account"]),
                str(row["reference"]),
            )
            result[key] = str(row["Transaction ID"])
        return result
    except Exception:
        return {}


class CreateLedgerMode:
    name = "create_ledger"
    description = "Compute running position balances from a consolidated journal"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "input_path",
            metavar="INPUT_PATH",
            help="Path to an existing consolidated journal XLSX produced by consolidate_journals.",
        )
        parser.add_argument(
            "output_path",
            metavar="OUTPUT_PATH",
            help="Path for the ledger output XLSX. Parent directory must exist.",
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        input_path = Path(args.input_path)
        output_path = Path(args.output_path)

        _logger.info(
            "create_ledger started",
            extra={
                LOG_CL_CORRELATION_ID: context.correlation_id,
                "input_path": str(input_path),
                "output_path": str(output_path),
            },
        )

        if not input_path.exists():
            _logger.error(
                "Invalid input journal",
                extra={"detail": f"Input file not found: {input_path}"},
            )
            return EXIT_INVALID_ARGS

        df = pd.read_excel(input_path, engine="openpyxl")
        prior_ids = _load_prior_ids(output_path)

        try:
            result = LedgerEngine().run(df, prior_ids=prior_ids)
        except ValueError as exc:
            _logger.error("Invalid input journal", extra={"detail": str(exc)})
            return EXIT_INVALID_ARGS

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result.to_excel(writer, index=False)
            ws = writer.sheets["Sheet1"]
            for col_name, fmt in [
                (LEDGER_COL_ACCOUNT_VALUE, NUMBER_FORMAT_VALUE),
                (LEDGER_COL_TRANSACTION_VALUE, NUMBER_FORMAT_VALUE),
                (LEDGER_COL_ACCOUNT_QUANTITY, NUMBER_FORMAT_QUANTITY),
                (LEDGER_COL_TRANSACTION_QUANTITY, NUMBER_FORMAT_QUANTITY),
            ]:
                col_idx = LEDGER_COLUMNS.index(col_name) + 1
                for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                    for cell in row:
                        cell.number_format = fmt

            tid_col_idx = LEDGER_COLUMNS.index(LEDGER_COL_TRANSACTION_ID) + 1
            for row in ws.iter_rows(min_row=2, min_col=tid_col_idx, max_col=tid_col_idx):
                for cell in row:
                    cell.number_format = "@"

        rows = len(result)
        _logger.info(
            COMPLETION_MSG,
            extra={
                LOG_CL_CORRELATION_ID: context.correlation_id,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "rows_processed": rows,
                "rows_written": rows,
            },
        )

        return EXIT_SUCCESS
