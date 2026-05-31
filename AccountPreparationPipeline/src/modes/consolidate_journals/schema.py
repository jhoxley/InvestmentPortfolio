from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path


class ActionType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    CONTRIB = "contrib"
    WITHDRAWAL = "withdrawal"


class ConsolidationMethod(StrEnum):
    HL = "HL"


@dataclass(frozen=True)
class JournalEvent:
    date: datetime.date
    account: str
    sub_account: str
    action: ActionType
    reference: str
    value: Decimal
    quantity: Decimal | None


@dataclass(frozen=True)
class ParseError:
    file_path: Path
    line_number: int | None
    message: str


@dataclass(frozen=True)
class ParseResult:
    events: list[JournalEvent]
    errors: list[ParseError]


@dataclass(frozen=True)
class ConsolidationSummary:
    files_processed: int
    events_inserted: int
    events_merged: int
    events_removed: int
    errors: list[ParseError]
