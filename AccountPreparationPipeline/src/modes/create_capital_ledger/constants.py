from __future__ import annotations

CAPITAL_ACTION_DEPOSIT: str = "deposit"
CAPITAL_ACTION_INCOME: str = "income"
CAPITAL_ACTION_BUY: str = "buy"
CAPITAL_ACTION_SELL: str = "sell"
CAPITAL_ACTION_LODGEMENT: str = "lodgement"

CAPITAL_LEDGER_ACTIONS: frozenset[str] = frozenset({"deposit", "income", "buy", "sell", "lodgement"})

CAPITAL_COL_DATE: str = "date"
CAPITAL_COL_CAPITAL: str = "capital"
CAPITAL_COL_INCOME: str = "income"
CAPITAL_COL_BOOK_VALUE: str = "book_value"

CAPITAL_LEDGER_OUTPUT_COLUMNS: list[str] = ["date", "capital", "income", "book_value"]

LOG_CCL_CORRELATION_ID: str = "correlation_id"
COMPLETION_MSG: str = "Capital ledger written"
