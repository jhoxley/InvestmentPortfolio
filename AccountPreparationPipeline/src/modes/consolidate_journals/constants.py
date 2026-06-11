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

HL_DEPOSIT_REFERENCES: frozenset[str] = frozenset({"Deposit", "BACS"})
HL_DEPOSIT_REFERENCE_ALIASES: frozenset[str] = frozenset({"CARD WEB", "FPC"})
HL_INCOME_REFERENCES: frozenset[str] = frozenset({"INTEREST", "RDP CR", "COMMISSION"})

RE_BUY: re.Pattern[str] = re.compile(r"^B\d+$")
RE_SELL: re.Pattern[str] = re.compile(r"^S\d+$")
RE_OFFSET: re.Pattern[str] = re.compile(r"^[BS]\d+-offset$")

OFFSET_SUFFIX: str = "-offset"
RE_BACS: re.Pattern[str] = re.compile(r"^BACS", re.IGNORECASE)

RE_DESCRIPTION_SUFFIX: re.Pattern[str] = re.compile(r"\s+[\d.,]+\s*@.*$")

CASH_SUB_ACCOUNT: str = "Cash"
CASH_ACTION_TYPES: frozenset[str] = frozenset({"deposit", "fee", "income"})
SUB_ACCOUNT_STRIP_SUFFIXES: tuple[str, ...] = (" Fee Sale -",)

NUMBER_FORMAT_VALUE: str = "#,##0.00"
NUMBER_FORMAT_QUANTITY: str = "#,##0.######"

LOG_CJ_CORRELATION_ID: str = "correlation_id"
LOG_CJ_FILE: str = "file"

SUMMARY_HEADER: str = "=== Consolidation Summary ==="
SUMMARY_SUCCESS_LABEL: str = "SUCCESS"
SUMMARY_ERRORS_LABEL: str = "ERRORS"
SUMMARY_NONE: str = "None"
