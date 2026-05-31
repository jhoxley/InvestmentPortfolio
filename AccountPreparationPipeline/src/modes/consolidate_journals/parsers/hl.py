from __future__ import annotations

import csv
import datetime
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.modes.consolidate_journals.constants import (
    HL_CONTRIB_REFERENCES,
    HL_HEADER_COL0,
    HL_HEADER_COL1,
    RE_BUY,
    RE_DESCRIPTION_SUFFIX,
    RE_SELL,
)
from src.modes.consolidate_journals.schema import (
    ActionType,
    JournalEvent,
    ParseError,
    ParseResult,
)

_logger = logging.getLogger("pipeline.modes.consolidate_journals.parsers.hl")

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")


def _parse_date(raw: str) -> datetime.date:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_decimal(raw: str) -> Decimal | None:
    cleaned = raw.strip().lstrip("£").replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse decimal: {raw!r}") from exc


def _strip_description_suffix(description: str) -> str:
    result = RE_DESCRIPTION_SUFFIX.sub("", description).strip()
    return result if result else description


def _map_action(reference: str) -> ActionType:
    ref = reference.strip()
    if RE_BUY.match(ref):
        return ActionType.BUY
    if RE_SELL.match(ref):
        return ActionType.SELL
    if ref in HL_CONTRIB_REFERENCES or ref.upper().startswith("BACS"):
        return ActionType.CONTRIB
    raise ValueError(f"Unknown action for reference: {ref!r}")


class HLFragmentParser:
    def parse(self, file_path: Path, account: str) -> ParseResult:
        events: list[JournalEvent] = []
        errors: list[ParseError] = []

        try:
            with file_path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.reader(fh)
                col_indices: dict[str, int] | None = None

                for row in reader:
                    if col_indices is None:
                        if (
                            len(row) >= 2
                            and row[0].strip() == HL_HEADER_COL0
                            and row[1].strip() == HL_HEADER_COL1
                        ):
                            col_indices = {cell.strip(): idx for idx, cell in enumerate(row)}
                        continue

                    if not any(cell.strip() for cell in row):
                        continue

                    line = reader.line_num
                    try:
                        event = _parse_row(row, col_indices, account, file_path, line)
                        events.append(event)
                    except _RowParseError as exc:
                        errors.append(exc.as_parse_error())
                    except Exception as exc:
                        errors.append(
                            ParseError(
                                file_path=file_path,
                                line_number=line,
                                message=str(exc),
                            )
                        )

                if col_indices is None:
                    errors.append(
                        ParseError(
                            file_path=file_path,
                            line_number=None,
                            message="No header row found matching 'Trade date / Settle date'",
                        )
                    )

        except OSError as exc:
            errors.append(
                ParseError(
                    file_path=file_path,
                    line_number=None,
                    message=f"Cannot open file: {exc}",
                )
            )

        _logger.debug(
            "HL parse complete",
            extra={
                "file": str(file_path),
                "events": len(events),
                "errors": len(errors),
            },
        )
        return ParseResult(events=events, errors=errors)


class _RowParseError(Exception):
    def __init__(self, file_path: Path, line_number: int, message: str) -> None:
        super().__init__(message)
        self._file_path = file_path
        self._line_number = line_number
        self._message = message

    def as_parse_error(self) -> ParseError:
        return ParseError(
            file_path=self._file_path,
            line_number=self._line_number,
            message=self._message,
        )


def _get_cell(row: list[str], col_indices: dict[str, int], *names: str) -> str:
    for name in names:
        idx = col_indices.get(name)
        if idx is not None and idx < len(row):
            return row[idx].strip()
    return ""


def _parse_row(
    row: list[str],
    col_indices: dict[str, int],
    account: str,
    file_path: Path,
    line: int,
) -> JournalEvent:
    settle_raw = _get_cell(row, col_indices, "Settle date")
    reference = _get_cell(row, col_indices, "Reference")
    description = _get_cell(row, col_indices, "Description")
    value_raw = _get_cell(row, col_indices, "Value (£)", "Value")
    qty_raw = _get_cell(row, col_indices, "Qty", "Quantity")

    try:
        date = _parse_date(settle_raw)
    except ValueError as exc:
        raise _RowParseError(file_path, line, f"Invalid date: {exc}") from exc

    try:
        action = _map_action(reference)
    except ValueError as exc:
        raise _RowParseError(file_path, line, str(exc)) from exc

    try:
        value_dec = _parse_decimal(value_raw)
    except ValueError as exc:
        raise _RowParseError(file_path, line, f"Invalid value: {exc}") from exc

    if value_dec is None:
        raise _RowParseError(file_path, line, "Value column is empty")

    try:
        quantity = _parse_decimal(qty_raw)
    except ValueError:
        quantity = None

    sub_account = _strip_description_suffix(description) if description else ""
    if not sub_account:
        sub_account = description or reference

    return JournalEvent(
        date=date,
        account=account,
        sub_account=sub_account,
        action=action,
        reference=reference,
        value=value_dec,
        quantity=quantity,
    )
