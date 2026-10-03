"""Orchestrates a VaR calculation run end to end: validate, fetch, compute, persist.

A run is created synchronously (validation, admission control, the initial "queued"
record) and then executed on the configured RunScheduler, so the triggering HTTP request
returns immediately (FR-017, SC-002) while the calculation -- which can take minutes the
first time a long price history must be fetched -- proceeds in the background.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pandas as pd
import structlog

from app.config import VarSettings
from app.exceptions import (
    AccountNotFoundError,
    InstrumentNotFoundError,
    InvalidVarRunRequestError,
    MarketDataServiceError,
    MissingRequiredSourceError,
    ObservedHistoryUnsupportedError,
    VarRunInProgressError,
)
from app.models.market_data import ObservedPriceHistory
from app.models.var import (
    RunFailure,
    RunFailureReason,
    RunWarning,
    RunWarningKind,
    VarRun,
    VarRunMode,
    VarRunRequest,
)
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import (
    ESTIMATE_COLUMNS,
    OUTCOME_COLUMNS,
    VarMeta,
    VarRepository,
)
from app.services.accounts_service import AccountsService
from app.services.daily_portfolio_return import compute_daily_portfolio_return
from app.services.var.engine import estimate, hypothetical_pnl
from app.services.var.exposures import build_exposures, build_proxy_configs
from app.services.var.fingerprint import config_fingerprint, row_fingerprint
from app.services.var.return_panel import build_return_panel
from app.services.var.run_scheduler import RunScheduler

if TYPE_CHECKING:
    from app.clients.market_data_client import ObservedPriceClient

logger = structlog.get_logger(__name__)

_ATTRIBUTE_LABEL = "risk/var"
_ACTIVE_STATUSES = {"queued", "running"}

_create_run_lock = threading.Lock()


@dataclass(frozen=True)
class DateSelection:
    """The outcome of `select_dates()`: which dates to (re)compute, and why.

    Attributes:
        dates: The dates selected for computation, in input order.
        dates_missing: In-range dates with no stored fingerprint at all.
        dates_stale: In-range dates whose stored fingerprint no longer matches.
        outcomes_pending_filled: In-range dates that were current and not stale, but
            whose stored outcome was pending and has now become resolvable (the ladder
            has caught up to their outcome date).
        dates_skipped: In-range dates not selected (current, with no resolvable pending
            outcome).
    """

    dates: list[date]
    dates_missing: int = 0
    dates_stale: int = 0
    outcomes_pending_filled: int = 0
    dates_skipped: int = field(default=0)


def select_dates(
    mode: VarRunMode,
    in_range_dates: list[date],
    stored_fingerprints: dict[date, str],
    stored_pending: set[date],
    current_fingerprints: dict[date, str],
    ladder_to: date,
) -> DateSelection:
    """Choose which in-range dates a run must (re)compute.

    Args:
        mode: "full" selects every in-range date; "missing" selects only what has
            changed or become resolvable.
        in_range_dates: Ladder dates already filtered to the run's requested range.
        stored_fingerprints: Date to the fingerprint of its currently stored estimate,
            for dates that have ever been computed.
        stored_pending: Dates whose stored outcome is still "pending".
        current_fingerprints: Date to the fingerprint freshly computed from today's
            configuration and holdings, for every date in `in_range_dates`.
        ladder_to: The ladder's last recorded date -- a pending outcome becomes
            resolvable once its outcome date (the next business day) is on or before
            this date.

    Returns:
        The DateSelection.
    """
    if mode == "full":
        return DateSelection(dates=list(in_range_dates))

    selected: list[date] = []
    missing = stale = pending_filled = 0
    for d in in_range_dates:
        if d not in stored_fingerprints:
            selected.append(d)
            missing += 1
            continue
        if stored_fingerprints[d] != current_fingerprints.get(d):
            selected.append(d)
            stale += 1
            continue
        if d in stored_pending:
            outcome_date = pd.bdate_range(start=d, periods=2)[-1].date()
            if outcome_date <= ladder_to:
                selected.append(d)
                pending_filled += 1

    return DateSelection(
        dates=selected,
        dates_missing=missing,
        dates_stale=stale,
        outcomes_pending_filled=pending_filled,
        dates_skipped=len(in_range_dates) - len(selected),
    )


class VarRunService:
    """Creates and executes historical-simulation VaR calculation runs."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        identifier_mapping_repo: IdentifierMappingRepository,
        observed_price_client: "ObservedPriceClient",
        var_repo: VarRepository,
        scheduler: RunScheduler,
        settings: VarSettings,
    ) -> None:
        """Initialise with every collaborator a run needs.

        Args:
            ladder_repo: Repository for position ladders.
            accounts_service: Shared account existence/date-range lookup service.
            identifier_mapping_repo: Resolves sub-account names to identifiers.
            observed_price_client: Fetches observed-only (fill=none) price history.
            var_repo: The VaR calculation store.
            scheduler: Executes a run's job in the background.
            settings: VaR configuration (look-backs, confidence levels, thresholds).
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._mapping_repo = identifier_mapping_repo
        self._observed_price_client = observed_price_client
        self._var_repo = var_repo
        self._scheduler = scheduler
        self._settings = settings

    def create_run(
        self, account_name: str, request: VarRunRequest, today: date, correlation_id: str
    ) -> VarRun:
        """Validate, admit, and queue a VaR calculation run.

        Args:
            account_name: The account identifier.
            request: The validated run request body.
            today: The current date (unused for "full"/"missing" selection in this
                version; reserved for future date-resolution needs).
            correlation_id: Correlation ID of the triggering HTTP request.

        Returns:
            The newly created VarRun, with status "queued".

        Raises:
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder.
            InvalidVarRunRequestError: If start is later than end.
            VarRunInProgressError: If the account already has a queued or running run.
        """
        del today  # reserved: "missing" mode's date selection (feature 012 US5) uses it
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
        if request.start is not None and request.end is not None and request.start > request.end:
            raise InvalidVarRunRequestError(
                message=f"start ({request.start}) must not be later than end ({request.end}).",
                fields=["start", "end"],
            )

        run_id = uuid.uuid4().hex
        with _create_run_lock:
            active = [
                r for r in self._var_repo.list_runs(account_name) if r.status in _ACTIVE_STATUSES
            ]
            if active:
                raise VarRunInProgressError(
                    account_name=account_name, active_run_id=active[0].run_id
                )

            run = VarRun(
                run_id=run_id,
                account_name=account_name,
                mode=request.mode,
                requested_start=request.start,
                requested_end=request.end,
                status="queued",
                correlation_id=correlation_id,
                requested_at=datetime.now(UTC),
                _links={
                    "self": f"/v1/accounts/{account_name}/risk/var/runs/{run_id}",
                    "account_runs": f"/v1/accounts/{account_name}/risk/var/runs",
                    "status": f"/v1/accounts/{account_name}/risk/var/status",
                },
            )
            self._var_repo.write_run(account_name, run)

        self._scheduler.submit(lambda: self.execute(account_name, run_id))
        return run

    def execute(self, account_name: str, run_id: str) -> None:
        """Run the full calculation for one queued run, updating its record as it goes.

        Args:
            account_name: The account identifier.
            run_id: The run to execute.
        """
        run = self._var_repo.read_run(account_name, run_id)
        if run is None:
            logger.error("var_run_execute_missing_record", account_name=account_name, run_id=run_id)
            return

        log = logger.bind(
            account_name=account_name, run_id=run_id, correlation_id=run.correlation_id
        )
        run = run.model_copy(update={"status": "running", "started_at": datetime.now(UTC)})
        self._var_repo.write_run(account_name, run)
        log.info("var_run_started", mode=run.mode)

        try:
            run = self._execute_body(account_name, run, log)
        except (
            MarketDataServiceError,
            ObservedHistoryUnsupportedError,
            InstrumentNotFoundError,
        ) as exc:
            reason: RunFailureReason = (
                "observed_history_unsupported"
                if isinstance(exc, ObservedHistoryUnsupportedError)
                else "market_data_unavailable"
            )
            run = self._fail(run, reason, str(exc))
            log.error("var_run_failed", reason=reason, detail=str(exc))
        except Exception as exc:
            run = self._fail(run, "internal_error", str(exc))
            log.exception("var_run_failed", reason="internal_error")
        self._var_repo.write_run(account_name, run)

    def _fail(self, run: VarRun, reason: RunFailureReason, detail: str) -> VarRun:
        """Build the failed-run update for `run`.

        Args:
            run: The in-progress run record.
            reason: Machine-readable failure reason.
            detail: Human-readable failure detail.

        Returns:
            `run` updated to status "failed" with a populated RunFailure.
        """
        return run.model_copy(
            update={
                "status": "failed",
                "finished_at": datetime.now(UTC),
                "failure": RunFailure(
                    type=f"https://portfolio-analysis/errors/var-run-{reason.replace('_', '-')}",
                    title="VaR Run Failed",
                    detail=detail,
                    reason=reason,
                    run_id=run.run_id,
                    correlation_id=run.correlation_id,
                ),
            }
        )

    def _execute_body(self, account_name: str, run: VarRun, log: "structlog.BoundLogger") -> VarRun:
        """Perform the calculation and persist its results; returns the succeeded run.

        Args:
            account_name: The account identifier.
            run: The "running" run record.
            log: A bound logger carrying account_name/run_id/correlation_id.

        Returns:
            `run` updated to status "succeeded" with its counts filled in.
        """
        meta = self._ladder_repo.read_meta(account_name)
        resolved_start = max(run.requested_start or meta.from_date, meta.from_date)
        resolved_end = min(run.requested_end or meta.to_date, meta.to_date)
        in_range_dates: list[date] = (
            [d.date() for d in pd.bdate_range(start=resolved_start, end=resolved_end)]
            if resolved_start <= resolved_end
            else []
        )

        ladder_df = self._ladder_repo.read_full_df(account_name)
        exposures = build_exposures(ladder_df, self._mapping_repo.lookup)

        all_proxy_configs = build_proxy_configs(self._mapping_repo.entries())
        config_fp = config_fingerprint(self._settings, all_proxy_configs)
        current_fingerprints = {d: row_fingerprint(config_fp, exposures[d]) for d in in_range_dates}

        stored_outcomes = self._var_repo.read_outcomes(account_name)
        stored_fingerprints: dict[date, str] = {}
        stored_pending: set[date] = set()
        for stored in stored_outcomes.itertuples():
            stored_date = stored.date.date()
            stored_fingerprints[stored_date] = stored.row_fingerprint
            if stored.outcome_status == "pending":
                stored_pending.add(stored_date)

        selection = select_dates(
            run.mode,
            in_range_dates,
            stored_fingerprints,
            stored_pending,
            current_fingerprints,
            meta.to_date,
        )
        dates = selection.dates

        base_update = {
            "resolved_start": resolved_start if in_range_dates else None,
            "resolved_end": resolved_end if in_range_dates else None,
            "dates_selected": len(dates),
            "dates_missing": selection.dates_missing,
            "dates_stale": selection.dates_stale,
            "outcomes_pending_filled": selection.outcomes_pending_filled,
            "dates_skipped": selection.dates_skipped,
        }
        if not dates:
            log.info("var_run_stage", stage="no_dates_selected")
            return run.model_copy(
                update={
                    **base_update,
                    "status": "succeeded",
                    "finished_at": datetime.now(UTC),
                    "dates_computed": 0,
                }
            )

        sub_accounts_by_identifier: dict[str, set[str]] = {}
        for d in dates:
            for position in exposures[d].positions:
                sub_accounts_by_identifier.setdefault(position.identifier, set()).add(
                    position.sub_account
                )
        needed_identifiers = sorted(sub_accounts_by_identifier)

        proxy_configs = {
            ident: cfg for ident, cfg in all_proxy_configs.items() if ident in needed_identifiers
        }
        proxy_identifiers = {cfg.proxy for cfg in proxy_configs.values()}
        fetch_identifiers = sorted(set(needed_identifiers) | proxy_identifiers)

        lookbacks = self._settings.lookbacks
        confidences = tuple(self._settings.confidence_levels_bp)
        max_lookback = max(lookbacks.values()) if lookbacks else 0

        fetch_start = pd.bdate_range(end=min(dates), periods=max_lookback + 6)[0].date()
        last_outcome_date = pd.bdate_range(start=max(dates), periods=2)[-1].date()
        fetch_end = min(last_outcome_date, meta.to_date)

        log.info(
            "var_run_stage",
            stage="fetch_prices",
            identifier_count=len(fetch_identifiers),
            fetch_start=str(fetch_start),
            fetch_end=str(fetch_end),
        )
        histories: dict[str, ObservedPriceHistory] = {}
        warnings: list[RunWarning] = []
        for identifier in fetch_identifiers:
            try:
                histories[identifier] = self._observed_price_client.get_observed_price_history(
                    identifier, fetch_start, fetch_end, "GBP"
                )
            except InstrumentNotFoundError:
                kind: RunWarningKind = (
                    "instrument_not_found"
                    if identifier in needed_identifiers
                    else "proxy_unresolved"
                )
                message = f"market-data-web-service has no price history for '{identifier}'."
                warnings.append(RunWarning(kind=kind, identifier=identifier, message=message))
                log.warning("var_" + kind, identifier=identifier)
                # Omitted from histories/the panel; the engine treats an identifier
                # missing from panel.identifiers as fully absent (rescale, or "no
                # proxy" if this was someone's configured proxy).

        panel = build_return_panel(histories, grid_start=fetch_start, grid_end=fetch_end)
        row_by_date = {d: i for i, d in enumerate(panel.grid)}

        estimate_rows: list[dict[str, object]] = []
        computed_at = datetime.now(UTC)
        for d in dates:
            exposure = exposures[d]
            as_of_row = row_by_date[d]
            for code, lookback_days in lookbacks.items():
                result = estimate(
                    exposure,
                    panel,
                    as_of_row,
                    lookback_days,
                    confidences,
                    self._settings,
                    proxy_configs=proxy_configs,
                )
                level_by_bp = {level.confidence_bp: level for level in result.levels}
                row: dict[str, object] = {
                    "date": d,
                    "method": "historical-simulation",
                    "lookback_code": code,
                    "lookback_days": lookback_days,
                    "scenario_count": result.scenario_count,
                    "excluded_scenarios": result.excluded_scenarios,
                    "actual_mv_pct": result.actual_mv_pct,
                    "proxied_mv_pct": result.proxied_mv_pct,
                    "rescaled_mv_pct": result.rescaled_mv_pct,
                    "quality": result.quality,
                    "quality_reason": result.quality_reason,
                    "row_fingerprint": current_fingerprints[d],
                    "methodology_version": self._settings.methodology_version,
                    "run_id": run.run_id,
                    "computed_at": computed_at,
                }
                for p_bp in (9500, 9750, 9900):
                    level = level_by_bp.get(p_bp)
                    row[f"var_{p_bp}_gbp"] = level.var_gbp if level else None
                    row[f"es_{p_bp}_gbp"] = level.es_gbp if level else None
                estimate_rows.append(row)

        instrument_rows = [
            {
                "identifier": identifier,
                "sub_accounts": ";".join(sorted(sub_accounts_by_identifier[identifier])),
                "first_observed_date": (
                    histories[identifier].first_observed_date if identifier in histories else None
                ),
                "last_observed_date": (
                    histories[identifier].last_observed_date if identifier in histories else None
                ),
                "proxy": proxy_configs[identifier].proxy if identifier in proxy_configs else None,
                "proxy_mode": (
                    proxy_configs[identifier].mode if identifier in proxy_configs else "fill_gaps"
                ),
                "proxy_scale": (
                    proxy_configs[identifier].scale if identifier in proxy_configs else 1.0
                ),
                "outlier_count": 0,
            }
            for identifier in needed_identifiers
        ]

        estimates_df = (
            pd.DataFrame(estimate_rows) if estimate_rows else pd.DataFrame(columns=ESTIMATE_COLUMNS)
        )

        ladder_returns = compute_daily_portfolio_return(ladder_df, meta.from_date, meta.to_date)
        ladder_return_by_date = dict(
            zip(ladder_returns["date"], ladder_returns["daily_return"], strict=True)
        )
        outcome_rows: list[dict[str, object]] = []
        for d in dates:
            exposure = exposures[d]
            outcome_date = pd.bdate_range(start=d, periods=2)[-1].date()
            pending = outcome_date > meta.to_date
            hyp_pnl = (
                None if pending else hypothetical_pnl(exposure, panel, row_by_date[outcome_date])
            )
            ladder_pnl = (
                None
                if pending
                else ladder_return_by_date.get(outcome_date, 0.0) * exposure.total_value
            )
            outcome_rows.append(
                {
                    "date": d,
                    "outcome_date": outcome_date,
                    "outcome_status": "pending" if pending else "realised",
                    "total_value_gbp": exposure.total_value,
                    "risky_value_gbp": exposure.risky_value,
                    "hypothetical_pnl_gbp": hyp_pnl,
                    "ladder_pnl_gbp": ladder_pnl,
                    "row_fingerprint": current_fingerprints[d],
                    "run_id": run.run_id,
                    "computed_at": computed_at,
                }
            )
        outcomes_df = (
            pd.DataFrame(outcome_rows) if outcome_rows else pd.DataFrame(columns=OUTCOME_COLUMNS)
        )
        instruments_df = pd.DataFrame(instrument_rows)

        log.info("var_run_stage", stage="persist", date_count=len(dates))
        self._var_repo.commit(
            account_name,
            estimates=estimates_df,
            outcomes=outcomes_df,
            instruments=instruments_df,
            meta=VarMeta(
                account_name=account_name,
                methodology_version=self._settings.methodology_version,
                config_fingerprint=config_fp,
                last_successful_run_id=run.run_id,
                updated_at=computed_at,
            ),
        )

        return run.model_copy(
            update={
                **base_update,
                "status": "succeeded",
                "finished_at": datetime.now(UTC),
                "dates_computed": len(dates),
                "warnings": warnings,
            }
        )


def recover_interrupted(var_repo: VarRepository) -> int:
    """Mark every queued/running VaR run as failed/interrupted, across all accounts.

    Called once at application start-up (FR-024): the in-memory run queue does not
    survive a restart, so any run still recorded as queued or running at that point was
    orphaned by the previous process stopping (a crash, or `uvicorn --reload`).

    Args:
        var_repo: The VaR calculation store to scan and update.

    Returns:
        The number of run records recovered.
    """
    recovered = 0
    for account_name in var_repo.list_accounts_with_runs():
        for run in var_repo.list_runs(account_name):
            if run.status not in _ACTIVE_STATUSES:
                continue
            updated = run.model_copy(
                update={
                    "status": "failed",
                    "finished_at": datetime.now(UTC),
                    "failure": RunFailure(
                        type="https://portfolio-analysis/errors/var-run-interrupted",
                        title="VaR Run Failed",
                        detail=(
                            f"Run '{run.run_id}' was still '{run.status}' when the service "
                            "started; the previous process must have stopped before it "
                            "finished."
                        ),
                        reason="interrupted",
                        run_id=run.run_id,
                        correlation_id=run.correlation_id,
                    ),
                }
            )
            var_repo.write_run(account_name, updated)
            logger.warning(
                "var_run_interrupted",
                account_name=account_name,
                run_id=run.run_id,
                previous_status=run.status,
            )
            recovered += 1
    return recovered
