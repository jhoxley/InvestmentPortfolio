"""Orchestrates the read-only VaR contributions endpoint (015-var-contributions).

Never triggers a calculation run and never calls market-data (FR-007): it reads the
existing estimates/outcomes store for the gating decision and, when an estimate exists
and is of sufficient quality, reconstructs the scenario matrix from the accumulated
scenario-returns snapshot (feature 012's `VarRunService` now persists) plus the ladder's
already-stored position ladder -- never a fresh market-data fetch.
"""

import math
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
import structlog

from app.config import VarSettings
from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.models.var_series import ContributionGroupEntry, VarContributionsResponse
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.contributions import (
    component_es,
    incremental_var,
    marginal_var,
    standalone_var,
    tail_weights,
)
from app.services.var.engine import _PROXY, _RESCALED, build_scenario_matrix, scenario_pnl
from app.services.var.exposures import (
    ContributionGroupDef,
    build_exposures,
    build_proxy_configs,
    group_positions,
)

logger = structlog.get_logger(__name__)

_ATTRIBUTE_LABEL = "risk/var/contributions"


def _is_nan(value: object) -> bool:
    """True if value is a float NaN (pandas' representation of a missing CSV cell)."""
    return isinstance(value, float) and math.isnan(value)


def _none_if_nan(value: object) -> float | None:
    """Convert a pandas NaN/None read back from CSV into None; pass other values through.

    Args:
        value: A cell value read from a pandas DataFrame.

    Returns:
        None if value is missing, otherwise value cast to float.
    """
    if value is None or _is_nan(value):
        return None
    return float(value)  # type: ignore[arg-type]


def _none_if_nan_str(value: object) -> str | None:
    """Convert a pandas NaN/None read back from CSV into None; pass strings through."""
    if value is None or _is_nan(value):
        return None
    return str(value)


class VarContributionsService:
    """Builds a VarContributionsResponse from the existing VaR store, never recomputing."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        var_repo: VarRepository,
        identifier_mapping_repo: IdentifierMappingRepository,
        settings: VarSettings,
    ) -> None:
        """Initialise with the collaborators a contributions request needs.

        Args:
            ladder_repo: Repository for position ladders (read-only here).
            accounts_service: Shared account existence/date-range lookup service.
            var_repo: The VaR calculation store (estimates + scenario-returns snapshot).
            identifier_mapping_repo: Resolves sub-account names to identifier/theme.
            settings: The application's VaR configuration.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._var_repo = var_repo
        self._mapping_repo = identifier_mapping_repo
        self._settings = settings

    def get_contributions(
        self,
        account_name: str,
        as_of: date,
        lookback_code: str,
        lookback_days: int,
        confidence_bp: int,
        group_by: Literal["position", "theme"],
    ) -> VarContributionsResponse:
        """Build the contributions response for one account/date/lookback/confidence.

        Args:
            account_name: The account identifier.
            as_of: The requested as-of date.
            lookback_code: The resolved look-back code (e.g. "2y").
            lookback_days: The resolved look-back's business-day window length.
            confidence_bp: The resolved confidence level, in basis points.
            group_by: "position" or "theme".

        Returns:
            Populated VarContributionsResponse (empty "not computed" shape if nothing has
            been computed for this account/date/lookback; empty "insufficient" shape if
            the stored quality is insufficient).

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

        links = {
            "self": f"/v1/accounts/{account_name}/risk/var/contributions",
            "status": f"/v1/accounts/{account_name}/risk/var/status",
            "runs": f"/v1/accounts/{account_name}/risk/var/runs",
        }
        base_kwargs = {
            "account_name": account_name,
            "lookback_code": lookback_code,
            "lookback_days": lookback_days,
            "confidence_bp": confidence_bp,
            "group_by": group_by,
            "_links": links,
        }

        logger.info(
            "var_contributions_request",
            account_name=account_name,
            date=str(as_of),
            lookback_code=lookback_code,
            confidence_bp=confidence_bp,
            group_by=group_by,
        )

        estimates = self._var_repo.read_estimates(account_name)
        as_of_ts = pd.Timestamp(as_of)
        matching = estimates[
            (estimates["date"] == as_of_ts) & (estimates["lookback_code"] == lookback_code)
        ]
        if matching.empty:
            return VarContributionsResponse(
                date=None,
                outcome_date=None,
                total_value_gbp=None,
                quality=None,
                quality_reason=None,
                groups=[],
                **base_kwargs,  # type: ignore[arg-type]
            )
        estimate_row = matching.iloc[0]

        outcomes = self._var_repo.read_outcomes(account_name)
        outcome_matching = outcomes[outcomes["date"] == as_of_ts]
        outcome_row = outcome_matching.iloc[0] if not outcome_matching.empty else None
        total_value_gbp = (
            _none_if_nan(outcome_row["total_value_gbp"]) if outcome_row is not None else None
        )
        outcome_date = (
            pd.Timestamp(outcome_row["outcome_date"]).date()
            if outcome_row is not None and not _is_nan(outcome_row["outcome_date"])
            else None
        )

        quality = str(estimate_row["quality"])
        quality_reason = _none_if_nan_str(estimate_row.get("quality_reason"))

        if quality == "insufficient":
            return VarContributionsResponse(
                date=as_of,
                outcome_date=outcome_date,
                total_value_gbp=total_value_gbp,
                quality="insufficient",
                quality_reason=quality_reason,
                groups=[],
                **base_kwargs,  # type: ignore[arg-type]
            )

        panel = self._var_repo.read_scenario_returns(account_name)
        if panel is None or as_of not in panel.grid:
            return VarContributionsResponse(
                date=None,
                outcome_date=None,
                total_value_gbp=None,
                quality=None,
                quality_reason=None,
                groups=[],
                **base_kwargs,  # type: ignore[arg-type]
            )

        ladder_df = self._ladder_repo.read_full_df(account_name)
        exposures_by_date = build_exposures(ladder_df, self._mapping_repo.lookup)
        exposure = exposures_by_date[as_of]

        proxy_configs = build_proxy_configs(self._mapping_repo.entries())
        as_of_row = panel.grid.index(as_of)
        matrix = build_scenario_matrix(
            exposure, panel, as_of_row, lookback_days, self._settings, proxy_configs
        )

        included_returns = matrix.effective_returns[matrix.included]
        n_positions = len(exposure.positions)
        total_pnl = (
            scenario_pnl(included_returns, matrix.values)
            if n_positions > 0
            else np.zeros(int(matrix.included.sum()))
        )
        total_losses = -total_pnl
        weights = tail_weights(total_losses, confidence_bp)
        included_provenance = matrix.provenance[matrix.included]

        group_defs = group_positions(exposure, group_by, self._mapping_repo.lookup)
        groups = [
            self._build_group_entry(
                group_def,
                matrix.values,
                included_returns,
                included_provenance,
                total_losses,
                weights,
                confidence_bp,
                total_value_gbp,
            )
            for group_def in group_defs
        ]

        return VarContributionsResponse(
            date=as_of,
            outcome_date=outcome_date,
            total_value_gbp=total_value_gbp,
            quality=quality,  # type: ignore[arg-type]
            quality_reason=quality_reason,
            groups=groups,
            **base_kwargs,  # type: ignore[arg-type]
        )

    def _build_group_entry(
        self,
        group_def: ContributionGroupDef,
        matrix_values: np.ndarray,
        included_returns: np.ndarray,
        included_provenance: np.ndarray,
        total_losses: np.ndarray,
        weights: np.ndarray,
        confidence_bp: int,
        total_value_gbp: float | None,
    ) -> ContributionGroupEntry:
        """Build one ContributionGroupEntry from a group definition and the shared matrix.

        Args:
            group_def: The group's identity and member column indices.
            matrix_values: The full matrix's per-position GBP market values.
            included_returns: The holiday-excluded effective-returns matrix.
            included_provenance: The holiday-excluded provenance codes matrix.
            total_losses: The full-portfolio scenario losses.
            weights: The portfolio's tail weights (from `tail_weights()`).
            confidence_bp: The requested confidence level, in basis points.
            total_value_gbp: The account's total market value on this date, or None.

        Returns:
            Populated ContributionGroupEntry.
        """
        n_scenarios = included_returns.shape[0]
        if group_def.is_cash:
            group_pnl = np.zeros(n_scenarios)
            actual_pct, proxied_pct, rescaled_pct = 100.0, 0.0, 0.0
        else:
            indices = list(group_def.indices)
            group_values = matrix_values[indices]
            group_returns = included_returns[:, indices]
            group_pnl = scenario_pnl(group_returns, group_values)

            group_provenance = included_provenance[:, indices]
            worst = group_provenance.max(axis=0) if group_provenance.size else np.array([])
            rescaled_value = float(group_values[worst == _RESCALED].sum()) if worst.size else 0.0
            proxied_value = float(group_values[worst == _PROXY].sum()) if worst.size else 0.0
            group_mv = group_def.market_value
            rescaled_pct = 100.0 * rescaled_value / group_mv if group_mv > 0 else 0.0
            proxied_pct = 100.0 * proxied_value / group_mv if group_mv > 0 else 0.0
            actual_pct = max(0.0, 100.0 - rescaled_pct - proxied_pct)

        standalone = standalone_var(group_pnl, confidence_bp)
        incremental = incremental_var(total_losses, group_pnl, confidence_bp)
        ces = component_es(group_pnl, weights)
        marginal = marginal_var(ces, group_def.market_value)
        weight_pct = (
            100.0 * group_def.market_value / total_value_gbp
            if total_value_gbp and total_value_gbp > 0
            else 0.0
        )

        return ContributionGroupEntry(
            key=group_def.key,
            identifier=group_def.identifier,
            market_value_gbp=group_def.market_value,
            weight_pct=weight_pct,
            standalone_var_gbp=standalone,
            incremental_var_gbp=incremental,
            component_es_gbp=ces,
            marginal_var_gbp_per_gbp=marginal,
            actual_mv_pct=actual_pct,
            proxied_mv_pct=proxied_pct,
            rescaled_mv_pct=rescaled_pct,
        )
