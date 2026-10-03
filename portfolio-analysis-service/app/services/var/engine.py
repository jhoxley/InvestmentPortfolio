"""Pure historical-simulation VaR/ES calculation functions.

Everything here is a pure function over numpy arrays -- no I/O, no market-data calls.
This is deliberate (research.md section 6): it is what makes the engine trivially
testable against hand-computed reference values, and the scenario x position PnL shape
is the seam a later Incremental VaR feature needs.
"""

from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from typing import Literal, NamedTuple

import numpy as np
import structlog

from app.config import VarSettings
from app.services.var.exposures import Exposure, ProxyConfig
from app.services.var.return_panel import ReturnPanel

logger = structlog.get_logger(__name__)

Quality = Literal["ok", "degraded", "insufficient"]


def rank_k(n: int, p_bp: int) -> int:
    """Return the 1-based rank of the VaR order statistic among n descending losses.

    k = n - ceil(n * p / 10000) + 1, computed with exact integer arithmetic so floating
    point error can never shift the selected rank (FR-006).

    Args:
        n: Number of scenario observations (n >= 1).
        p_bp: Confidence level in basis points of probability (e.g. 9500 for 95%).

    Returns:
        The 1-based rank k, always satisfying 1 <= k <= n.
    """
    ceil_np = (n * p_bp + 9999) // 10000
    k = n - ceil_np + 1
    return min(max(k, 1), n)


class VarEsResult(NamedTuple):
    """VaR and Expected Shortfall at one confidence level, as positive loss amounts."""

    var: float
    es: float


def var_es(losses: np.ndarray, p_bp: int) -> VarEsResult:
    """Compute historical-simulation VaR and Expected Shortfall from a loss vector.

    VaR is the k-th largest loss (rank_k). ES is the Acerbi-Tasche empirical tail mean
    over m = n * (1 - p) observations, using exact `fractions.Fraction` arithmetic for
    the integer/fractional split so the result matches a hand calculation exactly.

    Args:
        losses: 1-D array of scenario losses (positive = a loss), length n >= 1.
        p_bp: Confidence level in basis points of probability.

    Returns:
        VarEsResult(var, es), both positive GBP (or return-unit) amounts.
    """
    n = len(losses)
    sorted_desc = np.sort(losses)[::-1]
    k = rank_k(n, p_bp)
    var = float(sorted_desc[k - 1])

    m = Fraction(n * (10000 - p_bp), 10000)
    floor_m = int(m)
    frac = m - floor_m
    tail_sum = float(np.sum(sorted_desc[:floor_m])) if floor_m > 0 else 0.0
    if frac > 0:
        next_loss = float(sorted_desc[floor_m]) if floor_m < n else float(sorted_desc[-1])
        tail_sum += float(frac) * next_loss
    es = tail_sum / float(m) if m > 0 else var

    return VarEsResult(var=var, es=es)


def scenario_pnl(returns: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Apply a scenario x position returns matrix to a holdings vector.

    Args:
        returns: n x m array of simple returns (scenario rows, position columns).
        values: Length-m array of GBP market values.

    Returns:
        Length-n array of scenario PnL (returns @ values).
    """
    return np.asarray(returns @ values)


@dataclass(frozen=True)
class ConfidenceLevelResult:
    """VaR/ES at one confidence level, or None/None when the estimate is insufficient."""

    confidence_bp: int
    var_gbp: float | None
    es_gbp: float | None


@dataclass(frozen=True)
class EstimateResult:
    """The full result of estimate(): one (as-of date, look-back) VaR/ES calculation.

    Attributes:
        scenario_count: n, the number of scenario days retained after exclusion.
        excluded_scenarios: lookback_days window rows dropped by the observed-share rule
            (and by being outside the available grid).
        scenario_pnls: The retained scenario days' PnL (GBP), in window order.
        actual_mv_pct: Share of risky market value never needing proxy or rescale.
        proxied_mv_pct: Share of risky market value using a proxy (and not also rescaled)
            on any retained day.
        rescaled_mv_pct: Share of risky market value rescaled on any retained day.
        quality: "ok" / "degraded" / "insufficient" per the configured thresholds.
        quality_reason: Empty unless degraded or insufficient.
        levels: One ConfidenceLevelResult per requested confidence level.
    """

    scenario_count: int
    excluded_scenarios: int
    scenario_pnls: np.ndarray
    actual_mv_pct: float
    proxied_mv_pct: float
    rescaled_mv_pct: float
    quality: Quality
    quality_reason: str
    levels: list[ConfidenceLevelResult] = field(default_factory=list)


def _window_slice(panel: ReturnPanel, as_of_row: int, lookback_days: int) -> tuple[int, int]:
    """Return the [start, end) row slice for a look-back window ending at as_of_row.

    Args:
        panel: The return panel whose grid the window is sliced from.
        as_of_row: Index into panel.grid of the as-of date (inclusive).
        lookback_days: The look-back window length in business days.

    Returns:
        (start, end) such that panel.grid[start:end] is the window, clipped to the
        available grid when the window would start before row 0.
    """
    end = as_of_row + 1
    start = max(end - lookback_days, 0)
    return start, end


_ACTUAL, _PROXY, _RESCALED = 0, 1, 2


def _position_returns_and_provenance(
    identifier: str,
    panel: ReturnPanel,
    start: int,
    end: int,
    window_grid: tuple[date, ...],
    proxy_configs: dict[str, ProxyConfig],
    settings: VarSettings,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build one position's window returns, source-observed mask, and provenance codes.

    Args:
        identifier: The position's market-data identifier.
        panel: The shared return grid.
        start: Window start row (inclusive) in panel.grid.
        end: Window end row (exclusive) in panel.grid.
        window_grid: panel.grid[start:end], passed in to avoid re-slicing per position.
        proxy_configs: Held identifier to its configured ProxyConfig, if any.
        settings: VaR configuration (sparse_density_threshold).

    Returns:
        (returns, source_observed, provenance): each a length-`window_len` array.
        provenance is `_ACTUAL` or `_PROXY` here; a cell that is still NaN after this
        (own return missing, and proxy missing or absent) is marked `_RESCALED` by the
        caller's rescale pass once it fills it.
    """
    window_len = end - start
    own_col = panel.identifiers.index(identifier) if identifier in panel.identifiers else None
    own_returns = (
        panel.returns[start:end, own_col] if own_col is not None else np.full(window_len, np.nan)
    )
    own_observed = (
        panel.observed[start:end, own_col]
        if own_col is not None
        else np.zeros(window_len, dtype=bool)
    )

    config = proxy_configs.get(identifier)
    if config is None:
        provenance = np.full(window_len, _ACTUAL, dtype=int)
        return own_returns, own_observed, provenance

    proxy_col = panel.identifiers.index(config.proxy) if config.proxy in panel.identifiers else None
    proxy_returns = (
        panel.returns[start:end, proxy_col] * config.scale
        if proxy_col is not None
        else np.full(window_len, np.nan)
    )
    proxy_observed = (
        panel.observed[start:end, proxy_col]
        if proxy_col is not None
        else np.zeros(window_len, dtype=bool)
    )

    first_observed = panel.first_observed.get(identifier)
    if first_observed is None:
        sparse = True
    else:
        eligible = np.array([d >= first_observed for d in window_grid])
        eligible_count = int(eligible.sum())
        if eligible_count == 0:
            sparse = True
        else:
            density = float((own_observed & eligible).sum()) / eligible_count
            sparse = density < settings.sparse_density_threshold

    if config.mode == "always" or sparse:
        return proxy_returns, proxy_observed, np.full(window_len, _PROXY, dtype=int)

    own_missing = np.isnan(own_returns)
    returns = np.where(own_missing, proxy_returns, own_returns)
    source_observed = np.where(own_missing, proxy_observed, own_observed)
    provenance = np.where(own_missing, _PROXY, _ACTUAL)
    return returns, source_observed, provenance


def estimate(
    exposure: Exposure,
    panel: ReturnPanel,
    as_of_row: int,
    lookback_days: int,
    confidences_bp: tuple[int, ...],
    settings: VarSettings,
    proxy_configs: dict[str, ProxyConfig] | None = None,
) -> EstimateResult:
    """Compute one historical-simulation VaR/ES estimate for one date and look-back.

    Args:
        exposure: The positions held (and their GBP market values) at the as-of date.
        panel: The shared return grid; `as_of_row` indexes into `panel.grid`.
        as_of_row: Row index of the as-of date within `panel.grid`.
        lookback_days: The look-back window length in business days.
        confidences_bp: Confidence levels to compute, in basis points of probability.
        settings: VaR configuration (exclusion/sparsity/outlier/quality thresholds).
        proxy_configs: Held identifier to its configured VaR proxy, if any (FR-009/010).

    Returns:
        The populated EstimateResult.
    """
    proxy_configs = proxy_configs or {}
    start, end = _window_slice(panel, as_of_row, lookback_days)
    window_len = end - start
    window_grid = panel.grid[start:end]
    excluded_scenarios = lookback_days - window_len

    values = np.array([p.market_value for p in exposure.positions], dtype=float)
    n_positions = len(exposure.positions)
    returns = np.full((window_len, n_positions), np.nan, dtype=float)
    source_observed = np.zeros((window_len, n_positions), dtype=bool)
    provenance = np.full((window_len, n_positions), _ACTUAL, dtype=int)
    for i, position in enumerate(exposure.positions):
        pos_returns, pos_observed, pos_provenance = _position_returns_and_provenance(
            position.identifier, panel, start, end, window_grid, proxy_configs, settings
        )
        returns[:, i] = pos_returns
        source_observed[:, i] = pos_observed
        provenance[:, i] = pos_provenance

    if exposure.risky_value > 0:
        observed_share = (source_observed.astype(float) @ values) / exposure.risky_value
        included = observed_share >= settings.min_observed_share_per_scenario
    else:
        included = np.ones(window_len, dtype=bool)

    effective_returns = returns.copy()
    for row in range(window_len):
        if not included[row]:
            continue
        row_returns = effective_returns[row]
        missing = np.isnan(row_returns)
        if not missing.any():
            continue
        provenance[row, missing] = _RESCALED
        present = ~missing
        if present.any():
            present_values = values[present]
            total = present_values.sum()
            weighted_mean = (
                float(np.dot(row_returns[present], present_values) / total) if total > 0 else 0.0
            )
            effective_returns[row, missing] = weighted_mean
        else:
            effective_returns[row, missing] = 0.0

    included_returns = effective_returns[included]
    pnls = (
        scenario_pnl(included_returns, values) if n_positions > 0 else np.zeros(int(included.sum()))
    )
    excluded_scenarios += window_len - int(included.sum())
    scenario_count = int(included.sum())

    if n_positions > 0 and included.any():
        worst = provenance[included].max(axis=0)
    else:
        worst = np.full(n_positions, _ACTUAL, dtype=int)
    rescaled_value = float(values[worst == _RESCALED].sum()) if n_positions > 0 else 0.0
    proxied_value = float(values[worst == _PROXY].sum()) if n_positions > 0 else 0.0
    rescaled_mv_pct = (
        100.0 * rescaled_value / exposure.risky_value if exposure.risky_value > 0 else 0.0
    )
    proxied_mv_pct = (
        100.0 * proxied_value / exposure.risky_value if exposure.risky_value > 0 else 0.0
    )
    actual_mv_pct = (
        100.0 if exposure.risky_value <= 0 else max(0.0, 100.0 - rescaled_mv_pct - proxied_mv_pct)
    )

    quality: Quality
    reason = ""
    q = settings.quality
    if scenario_count < q.insufficient_min_scenario_ratio * lookback_days:
        quality = "insufficient"
        reason = (
            f"scenario_count {scenario_count} < "
            f"{q.insufficient_min_scenario_ratio * lookback_days:.0f} "
            f"({q.insufficient_min_scenario_ratio:.0%} of {lookback_days})"
        )
    elif rescaled_mv_pct > q.insufficient_max_rescaled_pct:
        quality = "insufficient"
        reason = f"rescaled {rescaled_mv_pct:.1f}% > {q.insufficient_max_rescaled_pct:.0f}%"
    elif rescaled_mv_pct > q.ok_max_rescaled_pct or proxied_mv_pct > q.ok_max_proxied_pct:
        quality = "degraded"
    else:
        quality = "ok"

    levels: list[ConfidenceLevelResult] = []
    if quality == "insufficient" or scenario_count == 0:
        for p_bp in confidences_bp:
            levels.append(ConfidenceLevelResult(confidence_bp=p_bp, var_gbp=None, es_gbp=None))
    else:
        losses = -pnls
        for p_bp in confidences_bp:
            result = var_es(losses, p_bp)
            levels.append(
                ConfidenceLevelResult(confidence_bp=p_bp, var_gbp=result.var, es_gbp=result.es)
            )

    return EstimateResult(
        scenario_count=scenario_count,
        excluded_scenarios=excluded_scenarios,
        scenario_pnls=pnls,
        actual_mv_pct=actual_mv_pct,
        proxied_mv_pct=proxied_mv_pct,
        rescaled_mv_pct=rescaled_mv_pct,
        quality=quality,
        quality_reason=reason,
        levels=levels,
    )
