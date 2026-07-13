"""Orchestrates validation, date resolution, join, and pnl computation.

For the account time series endpoint.
"""

from datetime import date

import pandas as pd
import structlog

from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.models.timeseries import TimeSeriesEntry, TimeSeriesResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services import timeseries_attributes
from app.services.accounts_service import AccountsService
from app.services.business_day_expansion import expand_business_days
from app.services.timeseries_date_resolver import TimeseriesDateResolver

logger = structlog.get_logger(__name__)

_CAPITAL_COLUMNS = ["capital", "income", "book_value"]


class TimeSeriesService:
    """Joins an account's capital ledger and position ladder into a time series."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        accounts_service: AccountsService,
        date_resolver: TimeseriesDateResolver,
    ) -> None:
        """Initialise with the two repositories and the shared account/date services.

        Args:
            ladder_repo: Repository for position ladders.
            capital_repo: Repository for capital ledgers.
            accounts_service: Shared account existence/date-range lookup service.
            date_resolver: Shared date defaulting/adjustment service.
        """
        self._ladder_repo = ladder_repo
        self._capital_repo = capital_repo
        self._accounts_service = accounts_service
        self._date_resolver = date_resolver

    def get_series(
        self,
        account_name: str,
        attributes: list[str],
        start: date | None,
        end: date | None,
        today: date,
    ) -> TimeSeriesResponse:
        """Build the requested time series for an account.

        Args:
            account_name: The account identifier.
            attributes: Requested attribute names.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            today: The current date.

        Returns:
            Populated TimeSeriesResponse.

        Raises:
            NoAttributesRequestedError: If attributes is empty.
            UnsupportedAttributeError: If any attribute name is unsupported.
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If a required source is missing or
                insufficient for the resolved date range.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        log = logger.bind(account_name=account_name, attributes=attributes)
        timeseries_attributes.validate_attributes(attributes)

        needs_capital = any(timeseries_attributes.requires_capital_ledger(a) for a in attributes)
        needs_ladder = any(timeseries_attributes.requires_position_ladder(a) for a in attributes)

        summary = self._accounts_service.get_summary(account_name)
        if summary.capital_ledger is None and summary.position_ladder is None:
            raise AccountNotFoundError(
                account_name=account_name,
                message=(
                    f"No capital ledger or position ladder has been ingested for "
                    f"account '{account_name}'."
                ),
            )

        capital_attribute = next(
            (a for a in attributes if timeseries_attributes.requires_capital_ledger(a)), None
        )
        ladder_attribute = next(
            (a for a in attributes if timeseries_attributes.requires_position_ladder(a)), None
        )

        if needs_capital and summary.capital_ledger is None:
            assert capital_attribute is not None
            raise MissingRequiredSourceError(
                account_name=account_name, attribute=capital_attribute, source="capital_ledger"
            )
        if needs_ladder and summary.position_ladder is None:
            assert ladder_attribute is not None
            raise MissingRequiredSourceError(
                account_name=account_name, attribute=ladder_attribute, source="position_ladder"
            )

        earliest_dates = []
        if needs_capital and summary.capital_ledger is not None:
            earliest_dates.append(summary.capital_ledger.from_date)
        if needs_ladder and summary.position_ladder is not None:
            earliest_dates.append(summary.position_ladder.from_date)

        resolved_start, resolved_end = self._date_resolver.resolve(
            raw_start=start,
            raw_end=end,
            today=today,
            required_source_earliest_dates=earliest_dates,
        )

        if (
            needs_capital
            and summary.capital_ledger is not None
            and resolved_start < summary.capital_ledger.from_date
        ):
            assert capital_attribute is not None
            raise MissingRequiredSourceError(
                account_name=account_name,
                attribute=capital_attribute,
                source="capital_ledger",
                message=(
                    f"capital_ledger for account '{account_name}' has no data before "
                    f"{summary.capital_ledger.from_date}, but the resolved start date "
                    f"is {resolved_start}."
                ),
            )
        if (
            needs_ladder
            and summary.position_ladder is not None
            and resolved_start < summary.position_ladder.from_date
        ):
            assert ladder_attribute is not None
            raise MissingRequiredSourceError(
                account_name=account_name,
                attribute=ladder_attribute,
                source="position_ladder",
                message=(
                    f"position_ladder for account '{account_name}' has no data before "
                    f"{summary.position_ladder.from_date}, but the resolved start date "
                    f"is {resolved_start}."
                ),
            )

        capital_expanded: pd.DataFrame | None = None
        if needs_capital:
            capital_df = self._capital_repo.read_df(account_name)
            capital_expanded = expand_business_days(
                capital_df, _CAPITAL_COLUMNS, resolved_start, resolved_end
            )

        market_value_expanded: pd.DataFrame | None = None
        if needs_ladder:
            ladder_df = self._ladder_repo.read_full_df(account_name)
            aggregated = ladder_df.groupby("date", as_index=False)["market_value"].sum()
            market_value_expanded = expand_business_days(
                aggregated, ["market_value"], resolved_start, resolved_end
            )

        if capital_expanded is not None and market_value_expanded is not None:
            merged = capital_expanded.merge(market_value_expanded, on="date", how="inner")
        elif capital_expanded is not None:
            merged = capital_expanded
        else:
            assert market_value_expanded is not None
            merged = market_value_expanded

        if "pnl" in attributes:
            merged["pnl"] = merged["income"] + merged["market_value"] - merged["book_value"]

        column_for_attribute = {
            "capital": "capital",
            "income": "income",
            "book_cost": "book_value",
            "market_value": "market_value",
            "pnl": "pnl",
        }

        entries = [
            TimeSeriesEntry(
                date=row["date"],
                **{attr: float(row[column_for_attribute[attr]]) for attr in attributes},
            )
            for _, row in merged.iterrows()
        ]

        log.info(
            "timeseries_request",
            from_date=str(resolved_start),
            to_date=str(resolved_end),
            row_count=len(entries),
        )

        return TimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            from_date=resolved_start,
            to_date=resolved_end,
            entries=entries,
            _links={
                "self": f"/v1/accounts/{account_name}/timeseries",
                "attributes": "/v1/timeseries/attributes",
                "accounts": "/v1/accounts",
            },
        )
