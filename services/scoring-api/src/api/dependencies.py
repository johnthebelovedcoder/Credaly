"""
Dependency injection for FastAPI routers.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.services.consent.service import ConsentService
from src.services.scoring.service import ScoringService
from src.services.outcomes.service import OutcomeService
from src.services.ingestion.service import IngestionService
from src.services.features.service import FeatureService
from src.services.api_key.service import ApiKeyService
from src.services.webhook.service import WebhookService


def get_consent_service(db: AsyncSession = Depends(get_db)) -> ConsentService:
    return ConsentService(db)


def get_scoring_service(db: AsyncSession = Depends(get_db)) -> ScoringService:
    return ScoringService(db)


def get_outcome_service(db: AsyncSession = Depends(get_db)) -> OutcomeService:
    return OutcomeService(db)


def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    return IngestionService(db)


def get_feature_service(db: AsyncSession = Depends(get_db)) -> FeatureService:
    return FeatureService(db)


def get_api_key_service(db: AsyncSession = Depends(get_db)) -> ApiKeyService:
    return ApiKeyService(db)


def get_webhook_service(db: AsyncSession = Depends(get_db)) -> WebhookService:
    return WebhookService(db)
