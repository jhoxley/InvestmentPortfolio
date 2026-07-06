from __future__ import annotations

# Input columns (from create_ledger output schema)
LEDGER_COL_DATE: str = "date"
LEDGER_COL_SUB_ACCOUNT: str = "sub_account"
LEDGER_COL_ACTION: str = "action"
LEDGER_COL_TV: str = "Transaction Value"
LEDGER_COL_TQ: str = "Transaction Quantity"

# Action type strings
ACTION_BUY: str = "buy"
ACTION_SELL: str = "sell"
ACTION_LODGEMENT: str = "lodgement"
ACTION_DIVIDEND: str = "dividend"

EQUITY_ACTIONS: frozenset[str] = frozenset({"buy", "sell", "lodgement"})
CASH_SUB_ACCOUNT: str = "Cash"

# Output columns
OUT_COL_DATE: str = "date"
OUT_COL_SUB_ACCOUNT: str = "sub_account"
OUT_COL_BOOK_COST: str = "book_cost"
OUT_COL_QUANTITY: str = "quantity"
OUT_COL_TOTAL_INCOME: str = "total_income"
OUTPUT_COLUMNS: list[str] = [
    "date",
    "sub_account",
    "book_cost",
    "quantity",
    "total_income",
]

# Logging
LOG_CORRELATION_ID: str = "correlation_id"
COMPLETION_MSG: str = "Sub-account ledger written"
