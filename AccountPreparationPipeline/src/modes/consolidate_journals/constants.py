from __future__ import annotations

import re

JOURNAL_COLUMNS: list[str] = [
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    "value",
    "quantity",
]

DEDUP_KEY_COLUMNS: list[str] = ["date", "reference"]
DEDUP_FALLBACK_KEY_COLUMNS: list[str] = ["date", "action", "value"]

HL_HEADER_COL0: str = "Trade date"
HL_HEADER_COL1: str = "Settle date"

HL_CONTRIB_REFERENCES: frozenset[str] = frozenset({"Deposit", "BACS"})

RE_BUY: re.Pattern[str] = re.compile(r"^B\d+$")
RE_SELL: re.Pattern[str] = re.compile(r"^S\d+$")
RE_BACS: re.Pattern[str] = re.compile(r"^BACS", re.IGNORECASE)

RE_DESCRIPTION_SUFFIX: re.Pattern[str] = re.compile(r"\s+[\d.,]+\s*@.*$")

LOG_CJ_CORRELATION_ID: str = "correlation_id"
LOG_CJ_FILE: str = "file"

SUMMARY_HEADER: str = "=== Consolidation Summary ==="
SUMMARY_SUCCESS_LABEL: str = "SUCCESS"
SUMMARY_ERRORS_LABEL: str = "ERRORS"
SUMMARY_NONE: str = "None"
