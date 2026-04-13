"""
Scoring Service — orchestrates the ML scoring pipeline.
Per PRD Section 5.4: FR-024 through FR-030.

Three parallel models:
  1. Base Credit Model — gradient-boosted tree (XGBoost/LightGBM) on structured financial data
  2. Alternative Data Booster — trained on behavioral signals
  3. Psychometric Engine — trained on survey and proxy signals

Composite Scoring Engine combines outputs via weighted ensemble,
adjusted by data_coverage_pct.

Output: credit score (300-850), confidence interval, reliability band.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import CreditScore, _hash_bvn
from src.services.features.service import FeatureService
from src.services.cache.service import CacheService

logger = logging.getLogger(__name__)

# Default explanation factors
POSITIVE_FACTORS_DEFAULT = [
    "No delinquency flags detected in bureau data",
    "Credit accounts show consistent repayment history",
    "Low credit utilization relative to available limits",
]

NEGATIVE_FACTORS_DEFAULT = [
    "Limited alternative data available — score based primarily on formal credit history",
    "No recent credit score improvement trend detected",
    "Thin credit file — few accounts contributing to score",
]


class ScoringService:
    """
    Orchestrates ML model inference and composite score generation.
    PRD FR-024 — FR-030.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feature_service = FeatureService(db)
        self.cache_service = CacheService()
        self._base_model = None
        self._alt_model = None
        self._psych_model = None
        self._model_version = "v1.0.0"
        self._load_models()

    def _load_models(self) -> None:
        """
        Load ML models from the model registry/artifacts path.
        In production, models are loaded from SageMaker or MLflow registry.
        For Phase 0/1, placeholder models return baseline scores.
        """
        model_path = settings.model_artifacts_path

        # Try to load Base Credit Model
        base_model_path = os.path.join(model_path, "base_credit_model.pkl")
        if os.path.exists(base_model_path):
            try:
                self._base_model = joblib.load(base_model_path)
                logger.info("Base Credit Model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load Base Credit Model: {e}")

        # Try to load Alternative Booster
        alt_model_path = os.path.join(model_path, "alternative_booster.pkl")
        if os.path.exists(alt_model_path):
            try:
                self._alt_model = joblib.load(alt_model_path)
                logger.info("Alternative Booster loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load Alternative Booster: {e}")

        # Try to load Psychometric Engine
        psych_model_path = os.path.join(model_path, "psychometric_engine.pkl")
        if os.path.exists(psych_model_path):
            try:
                self._psych_model = joblib.load(psych_model_path)
                logger.info("Psychometric Engine loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load Psychometric Engine: {e}")

        # Load model version from metadata file
        version_path = os.path.join(model_path, "model_version.txt")
        if os.path.exists(version_path):
            with open(version_path) as f:
                self._model_version = f.read().strip()

        if not self._base_model:
            logger.warning("No ML models loaded — using placeholder scoring for development")

    def _predict_base_model(self, features: Dict[str, float]) -> Optional[float]:
        """Run Base Credit Model inference. PRD FR-025.
        Returns a credit score in the 300-850 range (GradientBoostingRegressor).
        """
        if self._base_model is None:
            # Fallback: derive score from available formal features
            bureau = features.get("avg_bureau_score")
            if bureau and bureau > 0:
                return bureau
            return 550.0  # Population mean

        try:
            input_features = np.array([[features.get(f, 0.0) for f in [
                "avg_bureau_score",
                "bureau_delinquency_flag",
                "debt_to_income_ratio",
                "total_credit_accounts",
                "credit_utilization_ratio",
                "oldest_account_age_months",
                "recent_inquiries_6m",
            ]]])
            score = float(self._base_model.predict(input_features)[0])
            return max(settings.score_min, min(settings.score_max, score))
        except Exception as e:
            logger.error(f"Base model inference failed: {e}")
            bureau = features.get("avg_bureau_score")
            return bureau if bureau else 550.0

    def _predict_alternative_booster(self, features: Dict[str, float]) -> Optional[float]:
        """Run Alternative Data Booster inference. PRD FR-024(2).
        Returns a behavioral score contribution (0-100 range) that boosts the base score.
        """
        if self._alt_model is None:
            # Fallback: compute simple weighted sum of alt features
            alt_signal = sum(
                features.get(f, 0.0)
                for f in ["telco_consistency_index", "mobile_money_inflow_trend", "utility_payment_streak"]
            )
            if alt_signal > 0:
                return min(100, alt_signal * 15)
            return None  # No alternative data — no boost

        try:
            input_features = np.array([[features.get(f, 0.0) for f in [
                "telco_consistency_index",
                "mobile_money_inflow_trend",
                "utility_payment_streak",
                "bnpl_repayment_rate",
                "savings_balance_trend",
            ]]])
            return float(self._alt_model.predict(input_features)[0])
        except Exception as e:
            logger.error(f"Alternative booster inference failed: {e}")
            return None

    def _predict_psychometric(self, features: Dict[str, float]) -> Optional[float]:
        """Run Psychometric Engine inference. PRD FR-024(3).
        Returns a psychographic score contribution (0-100 range).
        """
        if self._psych_model is None:
            # Fallback
            psych_signal = sum(
                features.get(f, 0.0)
                for f in ["address_stability_score", "employment_tenure_months", "app_usage_regularity"]
            )
            if psych_signal > 0:
                return min(100, psych_signal * 10)
            return None

        try:
            input_features = np.array([[features.get(f, 0.0) for f in [
                "address_stability_score",
                "employment_tenure_months",
                "app_usage_regularity",
            ]]])
            return float(self._psych_model.predict(input_features)[0])
        except Exception as e:
            logger.error(f"Psychometric engine inference failed: {e}")
            return None

    def _compute_composite_score(
        self,
        base_score: Optional[float],
        alt_score: Optional[float],
        psych_score: Optional[float],
        data_coverage_pct: float,
    ) -> Tuple[int, int, int, str]:
        """
        Combine model outputs into a composite score (300-850).
        PRD FR-026: weighted ensemble, dynamically adjusted by data_coverage_pct.

        Logic:
          - base_score is already on 300-850 scale (from regression model)
          - alt_score is 0-100 (behavioral boost contribution)
          - psych_score is 0-100 (psychographic boost contribution)
          - Composite = base + alt_boost * alt_weight + psych_boost * psych_weight

        Returns: (score, confidence_lower, confidence_upper, confidence_band)
        """
        if base_score is None and alt_score is None and psych_score is None:
            # Nothing available — return mid-range with low confidence
            return 550, 450, 650, "LOW"

        # Start with base score if available, else use population mean
        if base_score is not None:
            score = base_score
        else:
            score = 550.0  # Population mean fallback

        # Add alternative data boost (scaled to credit score impact)
        alt_boost = 0.0
        if alt_score is not None and data_coverage_pct >= 20:
            # Alt data can shift score by up to ±40 points
            alt_normalized = (alt_score - 50) / 50  # -1 to +1
            alt_boost = alt_normalized * 40
            score += alt_boost

        # Add psychographic boost (scaled to credit score impact)
        psych_boost = 0.0
        if psych_score is not None and data_coverage_pct >= 30:
            # Psych data can shift score by up to ±20 points
            psych_normalized = (psych_score - 50) / 50  # -1 to +1
            psych_boost = psych_normalized * 20
            score += psych_boost

        # Clamp to valid range
        score = int(max(settings.score_min, min(settings.score_max, round(score))))

        # Confidence interval — wider when less data or heavy reliance on boosters
        # Base uncertainty shrinks as coverage increases
        base_uncertainty = max(15, 80 - data_coverage_pct)
        # Extra uncertainty if relying heavily on alt/psych boosters
        booster_uncertainty = 0
        if alt_score is not None and base_score is None:
            booster_uncertainty += 20  # No formal data, relying on alt
        if psych_score is not None and base_score is None and alt_score is None:
            booster_uncertainty += 15  # Only psych data

        margin = base_uncertainty + booster_uncertainty
        confidence_lower = max(settings.score_min, score - margin)
        confidence_upper = min(settings.score_max, score + margin)

        # Confidence band classification
        if data_coverage_pct >= 70 and margin <= 25:
            band = "HIGH"
        elif data_coverage_pct >= 40 and margin <= 45:
            band = "MEDIUM"
        else:
            band = "LOW"

        return score, confidence_lower, confidence_upper, band

    def _generate_explanations(
        self,
        features: Dict[str, float],
        score: int,
    ) -> Tuple[List[str], List[str]]:
        """
        Generate human-readable positive and negative factors.
        PRD FR-003, FR-018: plain English, under 50 words each.
        """
        positive = []
        negative = []

        # Positive factors
        if features.get("bureau_delinquency_flag", 1.0) == 0.0:
            positive.append("No delinquency flags detected in bureau data")
        if features.get("oldest_account_age_months", 0) > 24:
            positive.append(f"Long credit history of {int(features['oldest_account_age_months'])} months demonstrates stability")
        if features.get("telco_consistency_index", 0) > 0.5:
            positive.append("Consistent mobile money and telco usage patterns observed")
        if features.get("utility_payment_streak", 0) > 0:
            positive.append(f"Utility payments show {int(features['utility_payment_streak'])} consecutive on-time payments")
        if features.get("mobile_money_inflow_trend", 0) > 0.5:
            positive.append("Mobile money inflows show a positive trend over recent months")

        # Fill with defaults if needed
        while len(positive) < 3:
            for factor in POSITIVE_FACTORS_DEFAULT:
                if factor not in positive:
                    positive.append(factor)
                    break

        # Negative factors
        if features.get("bureau_delinquency_flag", 0) > 0:
            negative.append("Delinquency flags detected on one or more credit accounts")
        if features.get("recent_inquiries_6m", 0) > 5:
            negative.append("Multiple recent credit inquiries may indicate credit-seeking behavior")
        alt_data_available = any(
            features.get(f, 0) > 0
            for f in ["telco_consistency_index", "mobile_money_inflow_trend", "utility_payment_streak"]
        )
        if not alt_data_available:
            negative.append("Limited alternative data available — score based primarily on formal credit history")
        if features.get("total_credit_accounts", 0) < 2:
            negative.append("Thin credit file — few accounts contributing to score")

        while len(negative) < 3:
            for factor in NEGATIVE_FACTORS_DEFAULT:
                if factor not in negative:
                    negative.append(factor)
                    break

        return positive[:3], negative[:3]

    async def compute_score(
        self,
        bvn: str,
        tier_config: List[str],
        trace_id: str,
        consent_token_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full scoring pipeline: ingest → feature engineer → score → explain.
        PRD FR-024 — FR-027.
        Checks Redis cache first — returns cached result if < 24h old.
        If features don't exist in DB, triggers on-the-fly ingestion.
        """
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)
        tier_key = ",".join(sorted(tier_config))

        # Check cache first (PRD Section 6.1: cached score p95 < 500ms)
        cached = await self.cache_service.get_cached_score(bvn_hash, tier_key)
        if cached:
            logger.info(f"Returning cached score for {bvn_hash}")
            return cached

        # Step 1: Get features — trigger ingestion if missing
        features = await self.feature_service.get_latest_features(bvn, tier_config)

        if not features:
            # No features exist — trigger on-the-fly ingestion and feature computation
            logger.info(f"No features found for {bvn_hash} — triggering ingestion")
            from src.services.ingestion.service import IngestionService
            ingestion_service = IngestionService(self.db)

            raw_data, coverage_pct = await ingestion_service.ingest_for_scoring(bvn, tier_config)
            feature_service = FeatureService(self.db)
            computed_features = feature_service.compute_features_from_ingested_data(bvn_hash, raw_data)
            await feature_service.store_features(computed_features)
            await self.db.flush()

            # Re-fetch the stored features
            features = await self.feature_service.get_latest_features(bvn, tier_config)

        data_coverage_pct = self.feature_service.compute_data_coverage_pct(features, tier_config)

        # Step 2: Run all three models
        base_score = self._predict_base_model(features)
        alt_score = self._predict_alternative_booster(features)
        psych_score = self._predict_psychometric(features)

        # Step 3: Composite score
        score, conf_lower, conf_upper, band = self._compute_composite_score(
            base_score, alt_score, psych_score, data_coverage_pct
        )

        # Step 4: Generate explanations
        positive, negative = self._generate_explanations(features, score)

        # Step 5: Persist score
        credit_score = CreditScore(
            id=f"sco_{hashlib.md5(f'{bvn_hash}{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:10]}",
            borrower_bvn_hash=bvn_hash,
            score=score,
            confidence_lower=conf_lower,
            confidence_upper=conf_upper,
            confidence_band=band,
            data_coverage_pct=data_coverage_pct,
            model_version=self._model_version,
            consent_token_ref=consent_token_ref,
            trace_id=trace_id,
            positive_factors=json.dumps(positive),
            negative_factors=json.dumps(negative),
        )
        self.db.add(credit_score)
        await self.db.flush()

        result = {
            "score": score,
            "confidence_interval": {
                "lower": conf_lower,
                "upper": conf_upper,
                "level": f"{settings.confidence_level:.0%}",
            },
            "confidence_band": band,
            "data_coverage_pct": round(data_coverage_pct, 1),
            "positive_factors": positive,
            "negative_factors": negative,
            "consent_token_ref": consent_token_ref,
            "model_version": self._model_version,
            "computed_at": datetime.now(timezone.utc),
            "trace_id": trace_id,
        }

        # Cache the result (PRD Section 6.1: 24h TTL)
        await self.cache_service.set_cached_score(bvn_hash, tier_key, result)

        # Check for material score change and dispatch webhooks (US-006)
        await self._dispatch_webhooks_if_material_change(
            bvn_hash=bvn_hash,
            new_score=score,
            new_band=band,
        )

        return result

    async def _dispatch_webhooks_if_material_change(
        self,
        bvn_hash: str,
        new_score: int,
        new_band: str,
    ) -> None:
        """Fire webhook if score changed >40 points or band changed. US-006."""
        try:
            # Get the previous score
            stmt = (
                select(CreditScore)
                .where(CreditScore.borrower_bvn_hash == bvn_hash)
                .order_by(CreditScore.computed_at.desc())
                .limit(2)  # Current + previous
            )
            result = await self.db.execute(stmt)
            scores = result.scalars().all()

            if len(scores) >= 2:
                prev = scores[1]  # Second most recent (first is the one we just created)
                from src.services.webhooks.service import WebhookDispatcher
                dispatcher = WebhookDispatcher(self.db)
                try:
                    await dispatcher.check_score_change_and_dispatch(
                        bvn_hash=bvn_hash,
                        new_score=new_score,
                        old_score=prev.score,
                        old_band=prev.confidence_band,
                        new_band=new_band,
                    )
                finally:
                    await dispatcher.close()
        except Exception as e:
            # Never fail scoring because of webhook issues
            logging.getLogger(__name__).warning(f"Webhook dispatch failed: {e}")

    async def get_score_history(
        self,
        bvn: str,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """Retrieve score history for a borrower. PRD US-004."""
        bvn_hash = _hash_bvn(bvn, settings.bvn_encryption_key)

        stmt = (
            select(CreditScore)
            .where(CreditScore.borrower_bvn_hash == bvn_hash)
            .order_by(CreditScore.computed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        scores = result.scalars().all()

        return [
            {
                "score": s.score,
                "confidence_band": s.confidence_band,
                "data_coverage_pct": s.data_coverage_pct,
                "model_version": s.model_version,
                "computed_at": s.computed_at,
            }
            for s in scores
        ]


