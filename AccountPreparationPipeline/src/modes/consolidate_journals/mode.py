from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from src.constants import EXIT_INVALID_ARGS, EXIT_SUCCESS
from src.context import ExecutionContext
from src.modes.consolidate_journals.consolidator import ConsolidationEngine
from src.modes.consolidate_journals.constants import (
    LOG_CJ_CORRELATION_ID,
    SUMMARY_ERRORS_LABEL,
    SUMMARY_HEADER,
    SUMMARY_NONE,
    SUMMARY_SUCCESS_LABEL,
)
from src.modes.consolidate_journals.schema import ConsolidationMethod, ConsolidationSummary

_logger = logging.getLogger("pipeline.modes.consolidate_journals")


def render_summary(summary: ConsolidationSummary) -> str:
    lines: list[str] = [
        SUMMARY_HEADER,
        "",
        SUMMARY_SUCCESS_LABEL,
        f"  Files processed:  {summary.files_processed}",
        f"  Events inserted:  {summary.events_inserted}",
        f"  Events merged:    {summary.events_merged}",
        f"  Events removed:   {summary.events_removed}",
        "",
    ]

    if summary.errors:
        lines.append(f"{SUMMARY_ERRORS_LABEL} ({len(summary.errors)} total)")
        for err in summary.errors:
            if err.line_number is not None:
                lines.append(f"  [{err.file_path.name}] Line {err.line_number}: {err.message}")
            else:
                lines.append(f"  [{err.file_path.name}] {err.message}")
    else:
        lines.append(SUMMARY_ERRORS_LABEL)
        lines.append(f"  {SUMMARY_NONE}")

    return "\n".join(lines)


class ConsolidateJournalsMode:
    name = "consolidate_journals"
    description = "Merge journal fragment files into a standardised consolidated journal XLSX"

    def register_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "journal_path",
            metavar="JOURNAL_PATH",
            help=(
                "Path to the consolidated journal XLSX. "
                "Created if absent; updated in place if present."
            ),
        )
        parser.add_argument(
            "fragments_dir",
            metavar="FRAGMENTS_DIR",
            help="Directory containing journal fragment files (e.g. HL CSV exports) to process.",
        )
        parser.add_argument(
            "method",
            metavar="METHOD",
            help=(
                "Consolidation method determining how fragment files are parsed. "
                f"Accepted values: {', '.join(m.value for m in ConsolidationMethod)}."
            ),
        )
        parser.add_argument(
            "account",
            metavar="ACCOUNT",
            help=("Free-text account name written into the 'account' column of every output row."),
        )

    def execute(self, context: ExecutionContext, args: Namespace) -> int:
        correlation_id = context.correlation_id

        _logger.info(
            "consolidate_journals mode started",
            extra={LOG_CJ_CORRELATION_ID: correlation_id, "mode_name": self.name},
        )

        fragments_dir = Path(args.fragments_dir)
        if not fragments_dir.is_dir():
            _logger.error(
                "Fragments directory does not exist",
                extra={LOG_CJ_CORRELATION_ID: correlation_id, "path": str(fragments_dir)},
            )
            print(
                f"Error: fragments directory does not exist: {fragments_dir}",
                file=sys.stderr,
            )
            return EXIT_INVALID_ARGS

        try:
            method = ConsolidationMethod(args.method)
        except ValueError:
            valid = ", ".join(m.value for m in ConsolidationMethod)
            _logger.error(
                "Invalid consolidation method",
                extra={
                    LOG_CJ_CORRELATION_ID: correlation_id,
                    "method": args.method,
                    "valid": valid,
                },
            )
            print(
                f"Error: unrecognised consolidation method '{args.method}'. Valid: {valid}",
                file=sys.stderr,
            )
            return EXIT_INVALID_ARGS

        journal_path = Path(args.journal_path)
        engine = ConsolidationEngine()

        summary = engine.run(
            journal_path=journal_path,
            fragments_dir=fragments_dir,
            method=method,
            account=args.account,
        )

        _logger.info(
            "Consolidation summary",
            extra={
                LOG_CJ_CORRELATION_ID: correlation_id,
                "files_processed": summary.files_processed,
                "events_inserted": summary.events_inserted,
                "events_merged": summary.events_merged,
                "events_removed": summary.events_removed,
                "error_count": len(summary.errors),
            },
        )

        output = render_summary(summary)
        print(output)

        _logger.info(
            "consolidate_journals mode complete",
            extra={LOG_CJ_CORRELATION_ID: correlation_id},
        )
        return EXIT_SUCCESS
