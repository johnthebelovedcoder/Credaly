"""
Data Ingestion Service — connects to external data sources, normalizes data,
and feeds it into the feature engineering pipeline.
Per PRD Section 5.1: FR-001 through FR-010.

Phase 0/1: Credit bureaus (CRC, FirstCentral, CreditRegistry).
Phase 2: Telco, mobile money, open banking.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.circuit_breaker import get_circuit_breaker
from src.models import DataPipelineRun, _hash_bvn

logger = logging.getLogger(__name__)


# ── Base Ingestion Adapter ────────────────────────────────────────────

class BaseIngestionAdapter(ABC):
    """Abstract base for all data source adapters."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    async def fetch_data(self, bvn: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch data for a given BVN. Returns None if data unavailable."""
        ...

    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw data to canonical schema. Must handle missing fields gracefully. PRD FR-008."""
        ...


# ── Bureau Adapters (Phase 0/1) ──────────────────────────────────────

class CRCBureauAdapter(BaseIngestionAdapter):
    """CRC Credit Bureau adapter. PRD FR-001."""

    @property
    def source_name(self) -> str:
        return "crc_bureau"

    async def fetch_data(self, bvn: str, **kwargs) -> Optional[Dict[str, Any]]:
        if not settings.crc_api_url or not settings.crc_api_key:
            logger.warning("CRC bureau not configured — skipping")
            return None

        breaker = get_circuit_breaker("crc_bureau")
        try:
            async with breaker:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{settings.crc_api_url}/credit_report",
                        params={"bvn": bvn},
                        headers={"Authorization": f"Bearer {settings.crc_api_key}"},
                    )
                    response.raise_for_status()
                    return response.json()
        except CircuitBreakerError:
            logger.error("CRC circuit breaker is OPEN — skipping request")
            return None
        except Exception as e:
            logger.error(f"CRC bureau fetch failed for BVN: {e}")
            return None

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CRC bureau data to canonical schema."""
        return {
            "bureau_name": "crc",
            "credit_score": raw_data.get("credit_score"),
            "total_accounts": raw_data.get("total_accounts", 0),
            "active_accounts": raw_data.get("active_accounts", 0),
            "delinquent_accounts": raw_data.get("delinquent_accounts", 0),
            "oldest_account_age_months": raw_data.get("oldest_account_age_months"),
            "total_outstanding_balance": raw_data.get("total_outstanding_balance", 0),
            "delinquency_flags": raw_data.get("delinquency_flags", []),
            "inquiries_last_6_months": raw_data.get("inquiries_last_6_months", 0),
        }


class FirstCentralBureauAdapter(BaseIngestionAdapter):
    """FirstCentral Credit Bureau adapter. PRD FR-001."""

    @property
    def source_name(self) -> str:
        return "firstcentral_bureau"

    async def fetch_data(self, bvn: str, **kwargs) -> Optional[Dict[str, Any]]:
        if not settings.firstcentral_api_url or not settings.firstcentral_api_key:
            logger.warning("FirstCentral bureau not configured — skipping")
            return None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.firstcentral_api_url}/credit_report",
                    params={"bvn": bvn},
                    headers={"Authorization": f"Bearer {settings.firstcentral_api_key}"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"FirstCentral bureau fetch failed: {e}")
            return None

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "bureau_name": "firstcentral",
            "credit_score": raw_data.get("score"),
            "total_accounts": raw_data.get("account_count", 0),
            "active_accounts": raw_data.get("active_count", 0),
            "delinquent_accounts": raw_data.get("delinquent_count", 0),
            "oldest_account_age_months": raw_data.get("oldest_account_age"),
            "total_outstanding_balance": raw_data.get("outstanding_balance", 0),
            "delinquency_flags": raw_data.get("flags", []),
            "inquiries_last_6_months": raw_data.get("recent_inquiries", 0),
        }


class CreditRegistryAdapter(BaseIngestionAdapter):
    """Credit Registry adapter. PRD FR-001."""

    @property
    def source_name(self) -> str:
        return "creditregistry_bureau"

    async def fetch_data(self, bvn: str, **kwargs) -> Optional[Dict[str, Any]]:
        if not settings.creditregistry_api_url or not settings.creditregistry_api_key:
            logger.warning("CreditRegistry bureau not configured — skipping")
            return None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.creditregistry_api_url}/credit_report",
                    params={"bvn": bvn},
                    headers={"Authorization": f"Bearer {settings.creditregistry_api_key}"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"CreditRegistry bureau fetch failed: {e}")
            return None

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "bureau_name": "creditregistry",
            "credit_score": raw_data.get("score"),
            "total_accounts": raw_data.get("total_accounts", 0),
            "active_accounts": raw_data.get("active_accounts", 0),
            "delinquent_accounts": raw_data.get("delinquent_accounts", 0),
            "oldest_account_age_months": raw_data.get("oldest_account_age_months"),
            "total_outstanding_balance": raw_data.get("outstanding_balance", 0),
            "delinquency_flags": raw_data.get("delinquency_flags", []),
            "inquiries_last_6_months": raw_data.get("inquiries_6m", 0),
        }


# ── Ingestion Service ─────────────────────────────────────────────────

class IngestionService:
    """
    Orchestrates data ingestion from multiple sources.
    Per PRD FR-008, FR-009, FR-010: normalizes, deduplicates, graceful degradation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.adapters: Dict[str, BaseIngestionAdapter] = {
            "crc_bureau": CRCBureauAdapter(),
            "firstcentral_bureau": FirstCentralBureauAdapter(),
            "creditregistry_bureau": CreditRegistryAdapter(),
        }

        # Sandbox mode: when no real API keys are configured, use mock adapters
        if not settings.crc_api_url:
            self.adapters["crc_bureau"] = MockBureauAdapter("crc")
        if not settings.firstcentral_api_url:
            self.adapters["firstcentral_bureau"] = MockBureauAdapter("firstcentral")
        if not settings.creditregistry_api_url:
            self.adapters["creditregistry_bureau"] = MockBureauAdapter("creditregistry")

    def register_adapter(self, adapter: BaseIngestionAdapter) -> None:
        """Register a new data source adapter (Phase 2+: telco, mobile money)."""
        self.adapters[adapter.source_name] = adapter

    async def ingest_all(self, bvn: str) -> Dict[str, Dict[str, Any]]:
        """
        Fetch data from all available sources for a BVN.
        Graceful degradation: if a source fails, proceed with others. PRD FR-010.
        """
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)
        results = {}
        pipeline_runs = []

        for source_name, adapter in self.adapters.items():
            run = DataPipelineRun(
                source_name=source_name,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(run)
            await self.db.flush()

            try:
                raw_data = await adapter.fetch_data(bvn)
                if raw_data is None:
                    run.status = "degraded"
                    run.error_log = "Source returned no data"
                    run.completed_at = datetime.now(timezone.utc)
                    continue

                normalized = adapter.normalize(raw_data)
                results[source_name] = normalized
                run.status = "completed"
                run.records_ingested = 1
            except Exception as e:
                run.status = "failed"
                run.error_count = 1
                run.error_log = str(e)
                logger.error(f"Ingestion failed for {source_name}: {e}")
            finally:
                run.completed_at = datetime.now(timezone.utc)

        return results

    async def ingest_for_scoring(
        self,
        bvn: str,
        tier_config: List[str],
    ) -> tuple[Dict[str, Dict[str, Any]], float]:
        """
        Ingest data needed for scoring, respecting tier_config.
        Returns (normalized_data, data_coverage_pct).
        """
        all_data = await self.ingest_all(bvn)

        # Filter by tier
        tier_sources = {
            "formal": ["crc_bureau", "firstcentral_bureau", "creditregistry_bureau"],
            "alternative": [],  # Phase 2: telco, mobile money
            "psychographic": [],  # Phase 3
        }

        allowed_sources = set()
        for tier in tier_config:
            allowed_sources.update(tier_sources.get(tier, []))

        filtered_data = {
            k: v for k, v in all_data.items() if k in allowed_sources
        }

        # Calculate coverage
        total_possible = len(allowed_sources)
        available = len(filtered_data)
        coverage_pct = (available / total_possible * 100) if total_possible > 0 else 0.0

        return filtered_data, coverage_pct


# ── Sandbox/Mock Bureau Adapter ────────────────────────────────────────

import random
import hashlib as _hashlib


class MockBureauAdapter(BaseIngestionAdapter):
    """
    Generates realistic synthetic bureau data for sandbox/development testing.
    Used when no real API keys are configured (PRD US-008).
    """

    # Realistic Nigerian credit score distributions
    SCORE_RANGES = {
        "crc": (350, 800, 580, 120),        # mean=580, std=120
        "firstcentral": (400, 850, 610, 110),
        "creditregistry": (300, 750, 550, 100),
    }

    def __init__(self, bureau_name: str):
        self._bureau_name = bureau_name

    @property
    def source_name(self) -> str:
        return f"mock_{self._bureau_name}"

    async def fetch_data(self, bvn: str, **kwargs) -> dict:
        """Generate deterministic (seeded by BVN) but realistic bureau data."""
        seed = int(_hashlib.md5(bvn.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        score_min, score_max, score_mean, score_std = self.SCORE_RANGES[self._bureau_name]
        credit_score = int(max(score_min, min(score_max, rng.gauss(score_mean, score_std))))

        # Correlate other fields with score
        account_count = max(0, int(credit_score / 100 + rng.randint(-2, 3)))
        delinquent = 0 if credit_score > 600 else rng.randint(0, max(1, account_count // 2))
        active = max(0, account_count - delinquent)

        return {
            "credit_score": credit_score,
            "total_accounts": account_count,
            "active_accounts": active,
            "delinquent_accounts": delinquent,
            "oldest_account_age_months": max(1, int(rng.gauss(36, 24))),
            "total_outstanding_balance": max(0, int(rng.gauss(500000, 300000))),
            "delinquency_flags": ["30_DAYS_LATE"] if delinquent > 0 and rng.random() > 0.5 else [],
            "inquiries_last_6_months": max(0, int(rng.gauss(2, 2))),
        }

    def normalize(self, raw_data: dict) -> dict:
        """Normalize mock bureau data to canonical schema."""
        return {
            "bureau_name": f"mock_{self._bureau_name}",
            "credit_score": raw_data.get("credit_score"),
            "total_accounts": raw_data.get("total_accounts", 0),
            "active_accounts": raw_data.get("active_accounts", 0),
            "delinquent_accounts": raw_data.get("delinquent_accounts", 0),
            "oldest_account_age_months": raw_data.get("oldest_account_age_months"),
            "total_outstanding_balance": raw_data.get("total_outstanding_balance", 0),
            "delinquency_flags": raw_data.get("delinquency_flags", []),
            "inquiries_last_6_months": raw_data.get("inquiries_last_6_months", 0),
        }
