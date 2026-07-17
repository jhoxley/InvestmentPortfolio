"""Orchestrates validation, date resolution, and per-position expansion.

For the position time series endpoint.
"""

from datetime import date

import pandas as pd
import structlog

from app.exceptions import (
    AccountNotFoundError,
    MissingRequiredSourceError,
    PositionLadderNotIngestedError,
)
from app.models.position_timeseries import PositionTimeSeriesEntry, PositionTimeSeriesResponse
from app.repositories.ladder_repository import LadderRepository
from app.services import position_attributes
from app.services.accounts_service import AccountsService
from app.services.business_day_expansion import expand_business_days
from app.services.positions_service import PositionsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver

logger = structlog.get_logger(__name__)

_PNL_COLUMNS = ["book_cost", "total_income", "market_value"]


class PositionTimeSeriesService:
    """Builds a per-position time series from an account's position ladder."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        positions_service: PositionsService,
        date_resolver: TimeseriesDateResolver,
    ) -> None:
        """Initialise with the ladder repository and the shared account/date/position services.

        Args:
            ladder_repo: Repository for position ladders.
            accounts_service: Shared account existence/date-range lookup service.
            positions_service: Position enumeration and effective-set resolution service.
            date_resolver: Shared date defaulting/adjustment service.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._positions_service = positions_service
        self._date_resolver = date_resolver

    def get_series(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date | None,
        end: date | None,
        today: date,
    ) -> PositionTimeSeriesResponse:
        """Build the requested per-position time series for an account.

        Args:
            account_name: The account identifier.
            positions: Requested position names, possibly empty (defaults to all).
            attributes: Requested attribute names.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            today: The current date.

        Returns:
            Populated PositionTimeSeriesResponse.

        Raises:
            NoAttributesRequestedError: If attributes is empty.
            UnsupportedAttributeError: If any attribute name is unsupported.
            AccountNotFoundError: If the account has no ingested resource at all.
            PositionLadderNotIngestedError: If the account is known but has no
                ingested position ladder.
            MissingRequiredSourceError: If the resolved start precedes the ladder's
                own earliest recorded date.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        log = logger.bind(
            account_name=account_name, requested_positions=positions, attributes=attributes
        )
        position_attributes.validate_attributes(attributes)

        summary = self._accounts_service.get_summary(account_name)
        if summary.capital_ledger is None and summary.position_ladder is None:
            raise AccountNotFoundError(
                account_name=account_name,
                message=(
                    f"No capital ledger or position ladder has been ingested for "
                    f"account '{account_name}'."
                ),
            )
        if summary.position_ladder is None:
            raise PositionLadderNotIngestedError(account_name=account_name)

        ladder_df = self._ladder_repo.read_full_df(account_name)
        ladder_df = ladder_df.assign(date=pd.to_datetime(ladder_df["date"]).dt.date)
        effective_positions = self._positions_service.resolve_effective_positions(
            ladder_df, positions
        )

        resolved_start, resolved_end = self._date_resolver.resolve(
            raw_start=start,
            raw_end=end,
            today=today,
            required_source_earliest_dates=[summary.position_ladder.from_date],
        )

        if resolved_start < summary.position_ladder.from_date:
            raise MissingRequiredSourceError(
                account_name=account_name,
                attribute=", ".join(attributes),
                source="position_ladder",
                message=(
                    f"position_ladder for account '{account_name}' has no data before "
                    f"{summary.position_ladder.from_date}, but the resolved start date "
                    f"is {resolved_start}."
                ),
            )

        value_columns = sorted(
            {position_attributes.COLUMN_FOR_ATTRIBUTE[attr] for attr in attributes if attr != "pnl"}
            | ({*_PNL_COLUMNS} if "pnl" in attributes else set())
        )

        entries: list[PositionTimeSeriesEntry] = []
        for position in effective_positions:
            subset = ladder_df[ladder_df["sub_account"] == position]
            first_date = subset["date"].min()
            last_date = subset["date"].max()
            still_held = last_date == summary.position_ladder.to_date
            expand_start = max(resolved_start, first_date)
            expand_end = resolved_end if still_held else min(resolved_end, last_date)
            if expand_start > expand_end:
                continue

            expanded = expand_business_days(subset, value_columns, expand_start, expand_end)
            if "pnl" in attributes:
                expanded["pnl"] = (
                    expanded["total_income"] + expanded["market_value"] - expanded["book_cost"]
                )

            for _, row in expanded.iterrows():
                entries.append(
                    PositionTimeSeriesEntry(
                        date=row["date"],
                        position=position,
                        **{
                            attr: float(
                                row[position_attributes.COLUMN_FOR_ATTRIBUTE.get(attr, attr)]
                            )
                            for attr in attributes
                        },
                    )
                )

        entries.sort(key=lambda e: (e.date, e.position))
        response_positions = sorted({entry.position for entry in entries})

        log.info(
            "position_timeseries_request",
            effective_positions=effective_positions,
            from_date=str(resolved_start),
            to_date=str(resolved_end),
            row_count=len(entries),
        )

        return PositionTimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            positions=response_positions,
            from_date=resolved_start,
            to_date=resolved_end,
            entries=entries,
            _links={
                "self": f"/v1/accounts/{account_name}/position",
                "positions": f"/v1/accounts/{account_name}/positions",
                "attributes": "/v1/positions/attributes",
                "accounts": "/v1/accounts",
            },
        )
