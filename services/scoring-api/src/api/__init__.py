"""
API Router package — explicit exports, no self-imports.
"""

from src.api.score_router import router as score_router
from src.api.outcome_router import router as outcome_router
from src.api.consent_router import router as consent_router
from src.api.subject_router import router as subject_router

__all__ = [
    "score_router",
    "outcome_router",
    "consent_router",
    "subject_router",
]
