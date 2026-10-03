"""API router for VaR calculation runs and status (feature 012).

Routes are added incrementally as later tasks build out VarRunService and
VarStatusService (T024-T026, T031, T053); this module starts with just the router
instance so app/main.py has something stable to register during the Foundational
phase.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["Risk"])
