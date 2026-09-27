"""Shared helpers for risk feature tests: write stored ladders with controlled daily returns."""

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository


def write_ladder(repo: LadderRepository, account_name: str, rows: list[dict[str, Any]]) -> None:
    """Write a stored position ladder from explicit rows.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        rows: Dicts with keys date, sub_account, weighted_position_return.
    """
    df = pd.DataFrame(
        [
            {
                "date": r["date"],
                "sub_account": r["sub_account"],
                "book_cost": 0.0,
                "quantity": 1.0,
                "total_income": 0.0,
                "price": 1.0,
                "market_value": 0.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": r["weighted_position_return"],
            }
            for r in rows
        ]
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="cafebabe",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def write_daily_returns(
    repo: LadderRepository, account_name: str, start: date, returns: list[float]
) -> None:
    """Write a single-sub-account ladder with one return per consecutive business day.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        start: First business day (must itself be a business day).
        returns: Daily portfolio returns, one per consecutive business day from start.
    """
    days = pd.bdate_range(start=start, periods=len(returns))
    write_ladder(
        repo,
        account_name,
        [
            {"date": d.date(), "sub_account": "A", "weighted_position_return": r}
            for d, r in zip(days, returns, strict=True)
        ],
    )


def write_capital_only(repo: CapitalRepository, account_name: str) -> None:
    """Write a minimal stored capital ledger (no position ladder) for an account.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        [{"date": date(2024, 1, 2), "capital": 100.0, "income": 0.0, "book_value": 100.0}]
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=date(2024, 1, 2),
        to_date=date(2024, 1, 2),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)
