"""Canonical config/holdings fingerprinting for incremental VaR recomputation.

A `missing` run (feature 012 User Story 5) needs to tell, for each ladder date, whether
a previously computed estimate is still valid. Two fingerprints answer that:

- `config_fingerprint`: changes whenever the methodology, VaR configuration, or any
  instrument's proxy configuration changes -- invalidating every date at once.
- `row_fingerprint`: changes whenever a specific date's holdings change (a re-priced
  ladder, a new/closed position) -- invalidating only that date.
"""

import hashlib
import json

from app.config import VarSettings
from app.services.var.exposures import Exposure, ProxyConfig


def config_fingerprint(var_settings: VarSettings, proxy_configs: dict[str, ProxyConfig]) -> str:
    """Fingerprint the methodology version, VaR configuration, and proxy configuration.

    Args:
        var_settings: The active VaR configuration.
        proxy_configs: Held identifier to its configured VaR proxy, if any.

    Returns:
        A sha256 hex digest, stable regardless of dict ordering.
    """
    payload = {
        "methodology_version": var_settings.methodology_version,
        "lookbacks": dict(sorted(var_settings.lookbacks.items())),
        "confidence_levels_bp": sorted(var_settings.confidence_levels_bp),
        "min_observed_share_per_scenario": var_settings.min_observed_share_per_scenario,
        "sparse_density_threshold": var_settings.sparse_density_threshold,
        "outlier_abs_return": var_settings.outlier_abs_return,
        "quality": {
            "ok_max_rescaled_pct": var_settings.quality.ok_max_rescaled_pct,
            "ok_max_proxied_pct": var_settings.quality.ok_max_proxied_pct,
            "insufficient_min_scenario_ratio": (
                var_settings.quality.insufficient_min_scenario_ratio
            ),
            "insufficient_max_rescaled_pct": var_settings.quality.insufficient_max_rescaled_pct,
        },
        "excluded_returns": sorted(
            (
                {"identifier": excluded.identifier, "date": str(excluded.date)}
                for excluded in var_settings.excluded_returns
            ),
            key=lambda e: (e["identifier"], e["date"]),
        ),
        "proxy_configs": {
            identifier: {"proxy": cfg.proxy, "mode": cfg.mode, "scale": cfg.scale}
            for identifier, cfg in sorted(proxy_configs.items())
        },
    }
    return _hash(payload)


def row_fingerprint(config_fp: str, exposure: Exposure) -> str:
    """Fingerprint one date's holdings under a given configuration.

    Market values are rounded to the penny before hashing, so floating-point noise in
    the 3rd decimal place and beyond never causes a spurious recompute.

    Args:
        config_fp: The current `config_fingerprint()` result.
        exposure: The date's positions, Cash value, and totals.

    Returns:
        A sha256 hex digest, stable regardless of position ordering.
    """
    holdings = sorted(
        (position.identifier, position.sub_account, round(position.market_value, 2))
        for position in exposure.positions
    )
    payload = {
        "config_fingerprint": config_fp,
        "cash_value": round(exposure.cash_value, 2),
        "holdings": holdings,
    }
    return _hash(payload)


def _hash(payload: object) -> str:
    """Return the sha256 hex digest of a JSON-canonicalised payload.

    Args:
        payload: Any JSON-serialisable structure.

    Returns:
        64-character lowercase hex digest.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
