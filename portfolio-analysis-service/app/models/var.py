"""Pydantic models for the VaR calculation run and status API."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VarRunMode = Literal["missing", "full"]
VarRunStatus = Literal["queued", "running", "succeeded", "failed"]
RunFailureReason = Literal[
    "market_data_unavailable", "observed_history_unsupported", "interrupted", "internal_error"
]
RunWarningKind = Literal["outlier", "proxy_unresolved", "instrument_not_found", "excluded_price"]


class VarRunRequest(BaseModel):
    """Request body for POST /v1/accounts/{account_name}/risk/var/runs."""

    model_config = ConfigDict(extra="forbid")

    mode: VarRunMode = Field(default="missing", description="Which dates to (re)compute")
    start: dt.date | None = Field(default=None, description="First as-of date to consider")
    end: dt.date | None = Field(default=None, description="Last as-of date to consider")


class RunWarning(BaseModel):
    """A data-quality warning surfaced by a run (outlier, unresolved proxy, etc.)."""

    kind: RunWarningKind
    identifier: str
    date: dt.date | None = None
    value: float | None = Field(default=None, description="Return as a decimal, for outliers")
    message: str


class RunFailure(BaseModel):
    """RFC 7807-shaped description of why a VaR run failed."""

    type: str
    title: str
    detail: str
    reason: RunFailureReason
    run_id: str
    correlation_id: str


class VarRun(BaseModel):
    """A VaR calculation run: its request, lifecycle status, and outcome."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str
    account_name: str
    mode: VarRunMode
    requested_start: dt.date | None = None
    requested_end: dt.date | None = None
    resolved_start: dt.date | None = None
    resolved_end: dt.date | None = None
    status: VarRunStatus
    correlation_id: str = Field(description="Correlation ID of the creating POST request")
    requested_at: dt.datetime
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    dates_selected: int = 0
    dates_computed: int = 0
    dates_skipped: int = Field(
        default=0, description="Ladder dates in the run's range that did not need computing"
    )
    dates_missing: int = 0
    dates_stale: int = 0
    outcomes_pending_filled: int = 0
    warnings: list[RunWarning] = Field(default_factory=list)
    failure: RunFailure | None = None
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class VarRunList(BaseModel):
    """List of an account's VaR runs, newest first."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    runs: list[VarRun]
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class DateRange(BaseModel):
    """An inclusive from/to date range."""

    from_date: dt.date
    to_date: dt.date


class InstrumentTreatment(BaseModel):
    """An instrument's return-source treatment per look-back, as of the last successful run."""

    identifier: str
    sub_accounts: list[str]
    first_observed_date: dt.date | None = None
    last_observed_date: dt.date | None = None
    proxy: str | None = None
    proxy_mode: Literal["fill_gaps", "always"] = "fill_gaps"
    proxy_scale: float = 1.0
    treatment_by_lookback: dict[str, Literal["actual", "proxied", "rescaled"]] = Field(
        default_factory=dict,
        description="Look-back code (1y, 2y, 5y) to treatment at the latest computed date",
    )
    outlier_count: int = 0


class VarStatus(BaseModel):
    """Coverage and freshness of an account's VaR store relative to its position ladder."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    ladder_range: DateRange
    computed_range: DateRange | None = None
    missing_dates: int
    stale_dates_last_run: int
    pending_outcomes: int
    methodology_version: str | None = None
    last_run: VarRun | None = None
    instruments: list[InstrumentTreatment] = Field(default_factory=list)
    warnings: list[RunWarning] = Field(default_factory=list)
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
