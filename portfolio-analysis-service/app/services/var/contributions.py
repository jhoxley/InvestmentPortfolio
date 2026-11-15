"""Pure standalone/incremental/component/marginal VaR decomposition functions (015).

Everything here operates on numpy arrays already produced by
`app.services.var.engine.build_scenario_matrix()` -- no I/O, mirroring the existing
engine module's pure-function discipline. `tail_weights`/`component_es` reuse the same
Acerbi-Tasche tail split `app.services.var.engine.var_es()` already computes, rather than
re-deriving it, so a group's Component ES values sum exactly to the portfolio's total ES
(research.md §6).
"""

from fractions import Fraction

import numpy as np

from app.services.var.engine import var_es


def standalone_var(group_pnl: np.ndarray, p_bp: int) -> float:
    """Compute a group's standalone VaR: the quantile of its own PnL column alone.

    Args:
        group_pnl: Length-n scenario PnL for this group alone (not the full portfolio).
        p_bp: Confidence level in basis points of probability.

    Returns:
        The group's standalone VaR, as a positive GBP loss.
    """
    return var_es(-group_pnl, p_bp).var


def incremental_var(total_losses: np.ndarray, group_pnl: np.ndarray, p_bp: int) -> float:
    """Compute a group's incremental VaR: total VaR minus VaR without this group.

    Args:
        total_losses: Length-n full-portfolio scenario losses (positive = loss).
        group_pnl: Length-n scenario PnL for the group being removed.
        p_bp: Confidence level in basis points of probability.

    Returns:
        VaR(portfolio) - VaR(portfolio with this group's exposure removed), as GBP.
    """
    reduced_losses = total_losses + group_pnl
    return var_es(total_losses, p_bp).var - var_es(reduced_losses, p_bp).var


def tail_weights(losses: np.ndarray, p_bp: int) -> np.ndarray:
    """Compute the per-scenario weights `var_es()` implicitly uses for Expected Shortfall.

    Reproduces the exact Acerbi-Tasche tail split (the top floor(m) scenarios weighted
    1/m, the next scenario weighted frac(m)/m, everything else 0) in **original scenario
    order**, so the same weights can be applied to any other column aligned to the same
    scenario days (i.e. one group's PnL) to get an exact partition of the aggregate ES.

    Args:
        losses: Length-n full-portfolio scenario losses (positive = loss) -- the same
            array passed to `var_es()` for the aggregate estimate.
        p_bp: Confidence level in basis points of probability.

    Returns:
        Length-n array of weights summing to 1, such that
        `float(np.dot(weights, losses)) == var_es(losses, p_bp).es`.
    """
    n = len(losses)
    order = np.argsort(losses)[::-1]
    m = Fraction(n * (10000 - p_bp), 10000)
    floor_m = int(m)
    frac = m - floor_m

    weights = np.zeros(n, dtype=float)
    if m <= 0:
        return weights

    per_scenario = 1.0 / float(m)
    for i in range(floor_m):
        weights[order[i]] = per_scenario
    if frac > 0:
        boundary = order[floor_m] if floor_m < n else order[-1]
        weights[boundary] += float(frac) * per_scenario
    return weights


def component_es(group_pnl: np.ndarray, weights: np.ndarray) -> float:
    """Compute a group's Component Expected Shortfall from the portfolio's tail weights.

    Args:
        group_pnl: Length-n scenario PnL for this group alone, aligned to the same
            scenario order as `weights`.
        weights: The portfolio's tail weights from `tail_weights()`.

    Returns:
        The group's Component ES, as a positive-or-negative GBP contribution (negative
        PnL in the tail means a positive risk contribution). Summing this over every
        group in a full partition of the portfolio's positions reproduces the
        portfolio's total ES exactly.
    """
    return -float(np.dot(weights, group_pnl))


def marginal_var(component_es_value: float, market_value: float) -> float:
    """Compute a group's marginal VaR: its Component ES per unit of market value.

    Args:
        component_es_value: The group's Component ES (from `component_es()`).
        market_value: The group's GBP market value.

    Returns:
        `component_es_value / market_value`, or `0.0` when `market_value` is not
        positive (never raises or produces NaN/inf) -- a zero-component group (e.g.
        Cash) always yields exactly `0.0` regardless of its market value.
    """
    if market_value <= 0:
        return 0.0
    return component_es_value / market_value
