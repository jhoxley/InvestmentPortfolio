"""Exceptions raised by portfolio-browser's own data-access layer."""

from __future__ import annotations


class PortfolioAnalysisServiceError(Exception):
    """Raised when a call to portfolio-analysis-service fails.

    Covers non-2xx responses, timeouts, and connection errors alike — callers
    (Dash callbacks) only need to know the call failed, not the transport-level
    detail, to render the FR-014 error state.
    """
