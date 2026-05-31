from __future__ import annotations

import logging
from pathlib import Path

from src.modes.consolidate_journals.constants import LOG_CJ_CORRELATION_ID, LOG_CJ_FILE
from src.modes.consolidate_journals.journal_store import JournalStore
from src.modes.consolidate_journals.parsers.base import FragmentParser
from src.modes.consolidate_journals.parsers.hl import HLFragmentParser
from src.modes.consolidate_journals.schema import (
    ConsolidationMethod,
    ConsolidationSummary,
    ParseError,
)

_logger = logging.getLogger("pipeline.modes.consolidate_journals.consolidator")


def _get_parser(method: ConsolidationMethod) -> FragmentParser:
    if method is ConsolidationMethod.HL:
        return HLFragmentParser()
    raise ValueError(f"No parser registered for method {method!r}")


def _fragment_files(fragments_dir: Path, method: ConsolidationMethod) -> list[Path]:
    if method is ConsolidationMethod.HL:
        return sorted(fragments_dir.glob("*.csv"))
    return sorted(fragments_dir.iterdir())


class ConsolidationEngine:
    def run(
        self,
        journal_path: Path,
        fragments_dir: Path,
        method: ConsolidationMethod,
        account: str,
    ) -> ConsolidationSummary:
        store = JournalStore.load(journal_path)
        parser = _get_parser(method)
        files = _fragment_files(fragments_dir, method)

        total_inserted = 0
        total_merged = 0
        all_errors: list[ParseError] = []

        _logger.info(
            "Consolidation started",
            extra={
                LOG_CJ_CORRELATION_ID: "",
                "method": method.value,
                "fragments_dir": str(fragments_dir),
                "file_count": len(files),
            },
        )

        for file_path in files:
            _logger.info("Parsing fragment", extra={LOG_CJ_FILE: str(file_path)})
            result = parser.parse(file_path, account)

            for err in result.errors:
                _logger.warning(
                    "Fragment parse error",
                    extra={
                        LOG_CJ_FILE: str(file_path),
                        "line": err.line_number,
                        "detail": err.message,
                    },
                )
            all_errors.extend(result.errors)

            if result.events:
                inserted, merged = store.merge(result.events)
                total_inserted += inserted
                total_merged += merged

        store.save(journal_path)

        summary = ConsolidationSummary(
            files_processed=len(files),
            events_inserted=total_inserted,
            events_merged=total_merged,
            events_removed=0,
            errors=all_errors,
        )

        _logger.info(
            "Consolidation complete",
            extra={
                "files_processed": summary.files_processed,
                "events_inserted": summary.events_inserted,
                "events_merged": summary.events_merged,
                "error_count": len(summary.errors),
            },
        )

        return summary
