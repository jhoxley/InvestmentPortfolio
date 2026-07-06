from __future__ import annotations

CASH_SUB_ACCOUNT: str = "Cash"
BUY_SELL_ACTIONS: frozenset[str] = frozenset({"buy", "sell"})
SELL_ACTION: str = "sell"

LOG_CL_CORRELATION_ID: str = "correlation_id"
COMPLETION_MSG: str = "Ledger written"

LEDGER_COL_TRANSACTION_ID: str = "Transaction ID"
LEDGER_COL_ACCOUNT_VALUE: str = "Account Value"
LEDGER_COL_ACCOUNT_QUANTITY: str = "Account Quantity"
LEDGER_COL_TRANSACTION_VALUE: str = "Transaction Value"
LEDGER_COL_TRANSACTION_QUANTITY: str = "Transaction Quantity"

TRANSACTION_ID_SORT_COLS: list[str] = ["date", "account", "sub_account", "reference"]

LEDGER_COLUMNS: list[str] = [
    LEDGER_COL_TRANSACTION_ID,
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    LEDGER_COL_ACCOUNT_VALUE,
    LEDGER_COL_ACCOUNT_QUANTITY,
    LEDGER_COL_TRANSACTION_VALUE,
    LEDGER_COL_TRANSACTION_QUANTITY,
]
