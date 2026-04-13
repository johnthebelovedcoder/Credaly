"""
Evidently AI Integration — model drift detection and data quality monitoring.
Per PRD FR-029: PSI monitoring, data drift reports, model performance dashboards.

This module:
  1. Computes Population Stability Index (PSI) per feature
  2. Detects data drift between reference and current datasets
  3. Generates drift reports for admin dashboard consumption
  4. Triggers alerts when thresholds are exceeded
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Evidently AI integration for drift detection.
    PRD FR-029: PSI monitoring, alerting at 0.2, retraining at 0.25.
    """

    def __init__(self):
        self._evidently_available = self._check_evidently()

    def _check_evidently(self) -> bool:
        """Check if Evidently is installed."""
        try:
            import evidently
            return True
        except ImportError:
            logger.warning("Evidently AI not installed — drift detection disabled")
            return False

    def compute_psi(
        self,
        reference: pd.Series,
        current: pd.Series,
        n_bins: int = 10,
    ) -> float:
        """
        Compute Population Stability Index (PSI) for a single feature.

        PSI < 0.1: No significant change
        0.1 <= PSI < 0.2: Moderate change — monitor
        0.2 <= PSI < 0.25: Significant change — investigate
        PSI >= 0.25: Major change — retrain model

        Args:
            reference: Reference distribution (training data)
            current: Current distribution (production data)
            n_bins: Number of bins for discretization

        Returns:
            PSI value (float)
        """
        if not self._evidently_available:
            # Fallback: manual PSI computation
            return self._compute_psi_manual(reference, current, n_bins)

        try:
            from evidently.metrics import ColumnDistributionMetric
            from evidently.report import Report

            # Create a simple report to get distribution metrics
            reference_df = pd.DataFrame({"feature": reference})
            current_df = pd.DataFrame({"feature": current})

            report = Report(metrics=[
                ColumnDistributionMetric(column_name="feature"),
            ])
            report.run(reference_data=reference_df, current_data=current_df)

            # Extract PSI from the report
            # Note: Evidently's internal PSI computation
            json_result = report.as_dict()
            return self._extract_psi_from_report(json_result, reference, current, n_bins)

        except Exception as e:
            logger.warning(f"Evidently PSI computation failed: {e}")
            return self._compute_psi_manual(reference, current, n_bins)

    def _compute_psi_manual(
        self,
        reference: pd.Series,
        current: pd.Series,
        n_bins: int = 10,
    ) -> float:
        """
        Manual PSI computation without Evidently dependency.
        Formula: PSI = sum((actual% - expected%) * ln(actual% / expected%))
        """
        # Create bins
        bin_edges = pd.cut(reference, bins=n_bins, retbins=True)[1]

        # Compute percentages for each bin
        ref_counts = pd.cut(reference, bins=bin_edges).value_counts(normalize=True)
        curr_counts = pd.cut(current, bins=bin_edges).value_counts(normalize=True)

        # Align indices
        all_bins = ref_counts.index.union(curr_counts.index)
        ref_counts = ref_counts.reindex(all_bins, fill_value=0.001)  # Avoid division by zero
        curr_counts = curr_counts.reindex(all_bins, fill_value=0.001)

        # Compute PSI
        psi = ((curr_counts - ref_counts) * (curr_counts / ref_counts).apply(lambda x: __import__('math').log(x) if x > 0 else 0)).sum()

        return float(psi)

    def compute_psi_for_all_features(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Compute PSI for all features in the dataset.

        Returns:
            Dict mapping feature name to PSI value
        """
        if feature_names is None:
            feature_names = list(reference_data.columns)

        psi_results = {}
        for feature in feature_names:
            if feature in reference_data.columns and feature in current_data.columns:
                psi = self.compute_psi(
                    reference_data[feature],
                    current_data[feature],
                )
                psi_results[feature] = psi

                # Log alerts
                if psi >= 0.25:
                    logger.critical(
                        f"PSI ALERT: {feature} has PSI={psi:.4f} (>= 0.25) — "
                        f"model retraining recommended"
                    )
                elif psi >= 0.2:
                    logger.warning(
                        f"PSI WARNING: {feature} has PSI={psi:.4f} (>= 0.2) — "
                        f"investigating recommended"
                    )

        return psi_results

    def generate_drift_report(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive data drift report.

        Returns:
            Report dictionary with drift status per feature and summary.
        """
        if not self._evidently_available:
            return self._generate_drift_report_manual(reference_data, current_data)

        try:
            from evidently.metric_preset import DataDriftPreset
            from evidently.report import Report

            report = Report(metrics=[
                DataDriftPreset(),
            ])
            report.run(
                reference_data=reference_data,
                current_data=current_data,
            )

            return report.as_dict()

        except Exception as e:
            logger.error(f"Evidently drift report generation failed: {e}")
            return self._generate_drift_report_manual(reference_data, current_data)

    def _generate_drift_report_manual(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Manual drift report without Evidently."""
        psi_results = self.compute_psi_for_all_features(reference_data, current_data)

        drifted_features = {
            feature: psi
            for feature, psi in psi_results.items()
            if psi >= 0.2
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_features": len(reference_data.columns),
            "num_drifted_features": len(drifted_features),
            "drift_detected": len(drifted_features) > 0,
            "psi_per_feature": psi_results,
            "drifted_features": drifted_features,
            "recommendation": (
                "retrain_model"
                if any(psi >= 0.25 for psi in psi_results.values())
                else "monitor"
                if len(drifted_features) > 0
                else "no_action"
            ),
        }

    def check_drift_alerts(
        self,
        psi_per_feature: Dict[str, float],
        warning_threshold: float = 0.2,
        critical_threshold: float = 0.25,
    ) -> List[Dict[str, Any]]:
        """
        Check PSI values against alert thresholds.

        Returns:
            List of alert dictionaries
        """
        alerts = []

        for feature, psi in psi_per_feature.items():
            if psi >= critical_threshold:
                alerts.append({
                    "feature_name": feature,
                    "psi_value": psi,
                    "threshold": critical_threshold,
                    "severity": "critical",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "action": "Retrain model",
                })
            elif psi >= warning_threshold:
                alerts.append({
                    "feature_name": feature,
                    "psi_value": psi,
                    "threshold": warning_threshold,
                    "severity": "warning",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "action": "Investigate drift",
                })

        return alerts


# ── Singleton instance ────────────────────────────────────────────────

_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    """Get or create the drift detector singleton."""
    global _detector
    if _detector is None:
        _detector = DriftDetector()
    return _detector


def compute_feature_drift(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Convenience function: compute drift for a feature set.
    Used by admin API model metrics endpoint.
    """
    detector = get_drift_detector()
    return detector.generate_drift_report(reference_data, current_data)
