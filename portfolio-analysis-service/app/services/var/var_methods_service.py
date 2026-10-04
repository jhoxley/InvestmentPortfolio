"""Pure builder for the VaR methods-discovery response (013-var-series-backtest-api).

A plain function of VarSettings -- no repository, no I/O -- since the methods endpoint
(FR-022) describes configuration only and needs no account.
"""

from app.config import VarSettings
from app.models.var_series import MethodLookback, VarMethodsResponse

_MEASURES = [
    "scenario_count",
    "actual_mv_pct",
    "proxied_mv_pct",
    "rescaled_mv_pct",
    "quality",
    "var_gbp",
    "var_pct",
    "es_gbp",
    "es_pct",
    "hypothetical_pnl_gbp",
    "ladder_pnl_gbp",
    "exception_count",
    "exception_rate",
    "kupiec_lr",
    "christoffersen_independence_lr",
    "conditional_coverage_lr",
    "traffic_light_zone",
    "mean_var_gbp",
    "var_stability",
    "rolling_exception_count",
]


def build_methods_response(settings: VarSettings) -> VarMethodsResponse:
    """Build the methods-discovery response from the application's VaR configuration.

    Args:
        settings: The application's VaR configuration.

    Returns:
        Populated VarMethodsResponse.
    """
    lookbacks = [
        MethodLookback(
            code=code, business_days=days, is_headline=code == settings.headline_lookback
        )
        for code, days in settings.lookbacks.items()
    ]
    return VarMethodsResponse(
        method="historical-simulation",
        methodology_version=settings.methodology_version,
        lookbacks=lookbacks,
        confidence_levels_bp=list(settings.confidence_levels_bp),
        measures=list(_MEASURES),
        _links={"self": "/v1/risk/var/methods"},
    )
