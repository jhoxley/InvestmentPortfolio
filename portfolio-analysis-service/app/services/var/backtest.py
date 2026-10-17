"""Pure historical-simulation VaR backtest statistics (013-var-series-backtest-api).

Implements docs/proposals/value-at-risk.md section 4.3 exactly: Kupiec
proportion-of-failures, Christoffersen independence and conditional coverage, the
Basel-style traffic-light zone, VaR stability and the rolling exception count. Every
function here is pure (no I/O) and uses only the Python standard library (`math.erfc`,
`math.exp`, `math.lgamma`), mirroring engine.py's pure-function convention from feature
012 so these are directly testable against hand-worked values.
"""

import math
from itertools import pairwise


def _log_term(count: int, prob: float) -> float:
    """Return count * ln(prob), using the `0 * ln(0) = 0` convention.

    Args:
        count: A non-negative observation count.
        prob: The probability associated with that count. Never evaluated (so never
            raises on prob == 0) when count is 0.

    Returns:
        0.0 if count is 0, otherwise count * math.log(prob).
    """
    if count == 0:
        return 0.0
    return count * math.log(prob)


def kupiec_pof(n: int, x: int, alpha: float) -> tuple[float | None, float | None]:
    """Kupiec proportion-of-failures likelihood ratio test and its p-value.

    Args:
        n: Observation count.
        x: Exception count.
        alpha: The confidence level's nominal exceedance rate (1 - confidence).

    Returns:
        (lr, p_value), or (None, None) if n is 0.
    """
    if n <= 0:
        return None, None
    pihat = x / n
    log_l0 = _log_term(n - x, 1 - alpha) + _log_term(x, alpha)
    log_l1 = _log_term(n - x, 1 - pihat) + _log_term(x, pihat)
    lr = max(-2 * log_l0 + 2 * log_l1, 0.0)
    p_value = math.erfc(math.sqrt(lr / 2))
    return lr, p_value


def christoffersen_independence(
    dated_indicators: list[tuple[int, bool]],
) -> tuple[float | None, float | None]:
    """Christoffersen independence likelihood ratio test and its p-value.

    Transitions are counted only between consecutive entries whose ordinals differ by
    exactly 1; a gap (an excluded date) breaks the chain rather than being skipped over
    (FR-014).

    Args:
        dated_indicators: (ordinal, exception_indicator) pairs, sorted by ordinal
            ascending. The ordinal is any strictly increasing integer sequence number
            (e.g. a business-day index) used only to detect adjacency.

    Returns:
        (lr, p_value), or (None, None) if there are no valid consecutive transitions.
    """
    n00 = n01 = n10 = n11 = 0
    for (prev_ord, prev_ind), (cur_ord, cur_ind) in pairwise(dated_indicators):
        if cur_ord - prev_ord != 1:
            continue
        if not prev_ind and not cur_ind:
            n00 += 1
        elif not prev_ind and cur_ind:
            n01 += 1
        elif prev_ind and not cur_ind:
            n10 += 1
        else:
            n11 += 1

    total = n00 + n01 + n10 + n11
    if total == 0:
        return None, None

    pi = (n01 + n11) / total
    pi01 = n01 / (n00 + n01) if (n00 + n01) else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) else 0.0

    log_l0 = _log_term(n00 + n10, 1 - pi) + _log_term(n01 + n11, pi)
    log_l1 = (
        _log_term(n00, 1 - pi01)
        + _log_term(n01, pi01)
        + _log_term(n10, 1 - pi11)
        + _log_term(n11, pi11)
    )
    lr = max(-2 * log_l0 + 2 * log_l1, 0.0)
    p_value = math.erfc(math.sqrt(lr / 2))
    return lr, p_value


def conditional_coverage(
    lr_pof: float | None, lr_ind: float | None
) -> tuple[float | None, float | None]:
    """Conditional-coverage likelihood ratio test and its p-value.

    Args:
        lr_pof: The Kupiec proportion-of-failures likelihood ratio, or None.
        lr_ind: The Christoffersen independence likelihood ratio, or None.

    Returns:
        (lr, p_value), or (None, None) if either input is None.
    """
    if lr_pof is None or lr_ind is None:
        return None, None
    lr = lr_pof + lr_ind
    p_value = math.exp(-lr / 2)
    return lr, p_value


def _log_binomial_pmf(n: int, i: int, p: float) -> float:
    """Log probability mass P(X = i) for X ~ Binomial(n, p), via log-gamma coefficients."""
    log_coefficient = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
    return log_coefficient + i * math.log(p) + (n - i) * math.log(1 - p)


def _binomial_cdf(x: int, n: int, p: float) -> float:
    """Cumulative probability P(X <= x) for X ~ Binomial(n, p).

    Each term is computed independently via log-gamma binomial coefficients (not a
    recurrence), so precision does not degrade as n grows (research.md section 8).
    """
    return sum(math.exp(_log_binomial_pmf(n, i, p)) for i in range(x + 1))


def traffic_light_zone(n: int, x: int, alpha: float) -> str | None:
    """Basel-style traffic-light zone from the cumulative binomial probability.

    Green while the cumulative probability of x or fewer exceptions is below 95%,
    yellow while below 99.99%, red otherwise (FR-015). Reproduces Basel's 0-4/5-9/10+
    thresholds exactly for n=250, alpha=0.01 (SC-003).

    Args:
        n: Observation count.
        x: Exception count.
        alpha: The confidence level's nominal exceedance rate (1 - confidence).

    Returns:
        "green", "yellow" or "red", or None if n is 0.
    """
    if n <= 0:
        return None
    cumulative = _binomial_cdf(x, n, alpha)
    if cumulative < 0.95:
        return "green"
    if cumulative < 0.9999:
        return "yellow"
    return "red"


def var_stability(values: list[tuple[float, bool]]) -> float | None:
    """Standard deviation of the day-on-day log change in VaR (FR-016).

    Args:
        values: (var_value, holdings_changed) pairs in date order, where
            holdings_changed is True if the underlying holdings changed between the
            previous included date and this one (excluding that transition's
            log-change from the calculation).

    Returns:
        The sample (ddof=1) standard deviation of the qualifying log-changes, or None
        if fewer than 2 qualify.
    """
    log_changes: list[float] = []
    for i in range(1, len(values)):
        prev_value, _ = values[i - 1]
        value, changed = values[i]
        if changed:
            continue
        log_changes.append(math.log(value / prev_value))

    if len(log_changes) < 2:
        return None
    mean = sum(log_changes) / len(log_changes)
    variance = sum((lc - mean) ** 2 for lc in log_changes) / (len(log_changes) - 1)
    return math.sqrt(variance)


def rolling_exception_counts(indicators: list[bool], window: int) -> list[int]:
    """A sliding-window exception count over the included observation sequence (FR-019).

    Args:
        indicators: Exception indicators in date order (one per included observation).
        window: The window size (250 for the standard rolling series).

    Returns:
        One count per date from the `window`-th observation onward (empty if fewer
        than `window` observations exist).
    """
    n = len(indicators)
    if n < window:
        return []

    counts: list[int] = []
    current = sum(1 for v in indicators[:window] if v)
    counts.append(current)
    for i in range(window, n):
        if indicators[i]:
            current += 1
        if indicators[i - window]:
            current -= 1
        counts.append(current)
    return counts
