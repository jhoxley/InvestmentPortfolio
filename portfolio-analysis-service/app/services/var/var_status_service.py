"""Reports VaR coverage and freshness for an account, without reading its position ladder.

Deliberately reads only cheap, small sources (the ladder's meta.json, and the VaR
store's own CSVs/JSON) so a status request stays fast (SC-007) even for an account
whose ladder.xlsx takes seconds to parse.
"""

import datetime as dt
from typing import Literal

import pandas as pd
import structlog

from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.models.var import DateRange, InstrumentTreatment, VarStatus
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService

logger = structlog.get_logger(__name__)

_ATTRIBUTE_LABEL = "risk/var"
_TREATMENT_PREFIX = "treatment_"


class VarStatusService:
    """Builds a VarStatus from an account's ladder metadata and VaR store."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        var_repo: VarRepository,
    ) -> None:
        """Initialise with the collaborators needed to answer a status request.

        Args:
            ladder_repo: Repository for position ladders (only `read_meta` is used).
            accounts_service: Shared account existence/date-range lookup service.
            var_repo: The VaR calculation store.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._var_repo = var_repo

    def get_status(self, account_name: str) -> VarStatus:
        """Build the VaR status for one account.

        Args:
            account_name: The account identifier.

        Returns:
            The populated VarStatus.

        Raises:
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder.
        """
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
            raise MissingRequiredSourceError(
                account_name=account_name, attribute=_ATTRIBUTE_LABEL, source="position_ladder"
            )

        ladder_meta = self._ladder_repo.read_meta(account_name)
        ladder_range = DateRange(from_date=ladder_meta.from_date, to_date=ladder_meta.to_date)
        ladder_business_days = {
            d.date() for d in pd.bdate_range(start=ladder_meta.from_date, end=ladder_meta.to_date)
        }

        outcomes = self._var_repo.read_outcomes(account_name)
        computed_range: DateRange | None = None
        missing_dates = len(ladder_business_days)
        pending_outcomes = 0
        if not outcomes.empty:
            computed_dates = {ts.date() for ts in outcomes["date"]}
            computed_range = DateRange(from_date=min(computed_dates), to_date=max(computed_dates))
            missing_dates = len(ladder_business_days - computed_dates)
            pending_outcomes = int((outcomes["outcome_status"] == "pending").sum())

        runs = self._var_repo.list_runs(account_name)
        succeeded_runs = [r for r in runs if r.status == "succeeded"]
        last_run = succeeded_runs[0] if succeeded_runs else (runs[0] if runs else None)
        stale_dates_last_run = last_run.dates_stale if last_run else 0
        warnings = last_run.warnings if last_run else []

        var_meta = self._var_repo.read_meta(account_name)
        methodology_version = var_meta.methodology_version if var_meta else None

        instruments_df = self._var_repo.read_instruments(account_name)
        instruments = [_to_instrument_treatment(row) for row in instruments_df.to_dict("records")]

        logger.info(
            "var_status_request",
            account_name=account_name,
            missing_dates=missing_dates,
            pending_outcomes=pending_outcomes,
            instrument_count=len(instruments),
        )

        return VarStatus(
            account_name=account_name,
            ladder_range=ladder_range,
            computed_range=computed_range,
            missing_dates=missing_dates,
            stale_dates_last_run=stale_dates_last_run,
            pending_outcomes=pending_outcomes,
            methodology_version=methodology_version,
            last_run=last_run,
            instruments=instruments,
            warnings=warnings,
            _links={
                "self": f"/v1/accounts/{account_name}/risk/var/status",
                "runs": f"/v1/accounts/{account_name}/risk/var/runs",
                "account": f"/v1/accounts/{account_name}",
            },
        )


def _to_instrument_treatment(row: dict[str, object]) -> InstrumentTreatment:
    """Convert one instruments.csv row (as a dict) into an InstrumentTreatment.

    Args:
        row: One row of `VarRepository.read_instruments()`, as a dict.

    Returns:
        The populated InstrumentTreatment, with any `treatment_<code>` columns folded
        into `treatment_by_lookback`.
    """
    sub_accounts_raw = row.get("sub_accounts")
    sub_accounts = (
        str(sub_accounts_raw).split(";")
        if sub_accounts_raw and not pd.isna(sub_accounts_raw)
        else []
    )
    treatment_by_lookback: dict[str, Literal["actual", "proxied", "rescaled"]] = {
        key[len(_TREATMENT_PREFIX) :]: value
        for key, value in row.items()
        if key.startswith(_TREATMENT_PREFIX)
        and value is not None
        and not pd.isna(value)
        and value in ("actual", "proxied", "rescaled")
    }
    proxy_raw = row.get("proxy")
    proxy_mode_raw = row.get("proxy_mode")
    outlier_count_raw = row.get("outlier_count", 0)
    proxy_scale_raw = row.get("proxy_scale", 1.0)
    return InstrumentTreatment(
        identifier=str(row["identifier"]),
        sub_accounts=sub_accounts,
        first_observed_date=_none_if_nat(row.get("first_observed_date")),
        last_observed_date=_none_if_nat(row.get("last_observed_date")),
        proxy=None if proxy_raw is None or pd.isna(proxy_raw) else str(proxy_raw),
        proxy_mode=("always" if proxy_mode_raw == "always" else "fill_gaps"),
        proxy_scale=float(proxy_scale_raw) if proxy_scale_raw is not None else 1.0,  # type: ignore[arg-type]
        treatment_by_lookback=treatment_by_lookback,
        outlier_count=int(outlier_count_raw) if outlier_count_raw is not None else 0,  # type: ignore[call-overload]
    )


def _none_if_nat(value: object) -> dt.date | None:
    """Return None for a NaT/NaN value, else a date (from a Timestamp).

    Args:
        value: A pandas Timestamp, NaT, or None.

    Returns:
        A `datetime.date`, or None.
    """
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    if isinstance(value, float) and pd.isna(value):
        return None
    return None
