"""Historical-simulation Value at Risk (VaR) calculation engine and orchestration.

Sub-modules:
    exposures: Builds per-date position exposures from a position ladder.
    fingerprint: Canonical config/holdings fingerprinting for incremental recomputation.
    return_panel: Business-day return grids from observed-only price history.
    engine: Pure functions computing scenario PnL, VaR, Expected Shortfall and quality.
    run_scheduler: Single-worker background execution of calculation runs.
    var_run_service: Orchestrates a full calculation run end to end.
    var_status_service: Reports coverage and freshness without reading the ladder.
"""
