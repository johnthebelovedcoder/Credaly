"""
MLflow Integration — model tracking, versioning, and A/B deployment.
Per PRD FR-028, FR-029: model versioning, A/B testing, performance tracking.

This module wraps MLflow to:
  1. Log training runs with parameters, metrics, and artifacts
  2. Register and version models in the MLflow Model Registry
  3. Support A/B deployment with configurable traffic splitting
  4. Track model performance metrics (Gini, KS, PSI) over time
"""

import logging
import os
from typing import Any, Dict, List, Optional

import mlflow
import mlflow.sklearn
import pandas as pd

from src.core.config import settings

logger = logging.getLogger(__name__)


class MLflowTracker:
    """
    MLflow integration for ML model lifecycle management.
    PRD FR-028, FR-029.
    """

    def __init__(self, experiment_name: str = "credaly_scoring"):
        self.experiment_name = experiment_name
        self.tracking_uri = settings.model_registry_uri

        # Set tracking URI
        if self.tracking_uri.startswith("./"):
            # Local file store (development)
            self.tracking_uri = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                self.tracking_uri.lstrip("./"),
            )

        mlflow.set_tracking_uri(self.tracking_uri)

        # Set or create experiment
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
        else:
            self.experiment_id = experiment.experiment_id

        mlflow.set_experiment(self.experiment_name)

        logger.info(
            f"MLflow tracker initialized — experiment: {self.experiment_name}, "
            f"tracking URI: {self.tracking_uri}"
        )

    def start_run(self, run_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """
        Start a new MLflow run for training or evaluation.
        Usage:
            with tracker.start_run(run_name="training_v1.2") as run:
                tracker.log_params({...})
                tracker.log_metrics({...})
        """
        return mlflow.start_run(run_name=run_name, tags=tags or {})

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log training parameters (hyperparameters, feature list, etc.)."""
        try:
            mlflow.log_params(params)
        except Exception as e:
            logger.warning(f"Failed to log params: {e}")

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Log training/evaluation metrics."""
        try:
            mlflow.log_metrics(metrics, step=step)
        except Exception as e:
            logger.warning(f"Failed to log metrics: {e}")

    def log_model(
        self,
        model,
        artifact_path: str = "model",
        signature=None,
        model_name: Optional[str] = None,
    ) -> str:
        """
        Log a model artifact and register it in the Model Registry.
        Returns the model URI.
        """
        try:
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path=artifact_path,
                signature=signature,
            )

            run_id = mlflow.active_run().info.run_id
            model_uri = f"runs:/{run_id}/{artifact_path}"

            if model_name:
                # Register in Model Registry
                mlflow.register_model(
                    model_uri=model_uri,
                    name=model_name,
                )
                logger.info(f"Model registered: {model_name} (run: {run_id})")

            return model_uri
        except Exception as e:
            logger.error(f"Failed to log model: {e}")
            return ""

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None) -> None:
        """Log a file artifact (e.g., feature importance plot, confusion matrix)."""
        try:
            mlflow.log_artifact(local_path, artifact_path)
        except Exception as e:
            logger.warning(f"Failed to log artifact: {e}")

    def get_run(self, run_id: str) -> Optional[Any]:
        """Get a specific run by ID."""
        try:
            return mlflow.get_run(run_id)
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            return None

    def get_latest_run(self, model_name: str) -> Optional[Any]:
        """Get the latest production version of a registered model."""
        try:
            client = mlflow.tracking.MlflowClient()
            latest_versions = client.get_latest_versions(model_name, stages=["Production"])
            if latest_versions:
                version = latest_versions[0]
                return client.get_run(version.run_id)
            return None
        except Exception as e:
            logger.error(f"Failed to get latest run for {model_name}: {e}")
            return None

    def transition_model_stage(
        self,
        model_name: str,
        version: str,
        stage: str,
    ) -> None:
        """
        Transition a model version to a new stage.
        Stages: None, Staging, Production, Archived
        """
        try:
            client = mlflow.tracking.MlflowClient()
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
            )
            logger.info(f"Model {model_name} v{version} → {stage}")
        except Exception as e:
            logger.error(f"Failed to transition model stage: {e}")

    def get_model_versions(self, model_name: str) -> List[Dict[str, Any]]:
        """Get all versions of a registered model."""
        try:
            client = mlflow.tracking.MlflowClient()
            versions = client.search_model_versions(f"name='{model_name}'")
            return [
                {
                    "version": v.version,
                    "stage": v.current_stage,
                    "run_id": v.run_id,
                    "creation_timestamp": v.creation_timestamp,
                }
                for v in versions
            ]
        except Exception as e:
            logger.error(f"Failed to get model versions for {model_name}: {e}")
            return []

    def load_model_from_registry(self, model_name: str, stage: str = "Production"):
        """
        Load a model from the registry by stage.
        Returns the loaded model object.
        """
        try:
            model_uri = f"models:/{model_name}/{stage}"
            return mlflow.sklearn.load_model(model_uri)
        except Exception as e:
            logger.error(f"Failed to load model {model_name} from {stage}: {e}")
            return None

    def log_dataset_info(
        self,
        name: str,
        source: str,
        num_rows: int,
        num_features: int,
        date_range: tuple,
    ) -> None:
        """Log dataset metadata for reproducibility."""
        try:
            mlflow.log_params({
                "dataset_name": name,
                "dataset_source": source,
                "dataset_num_rows": num_rows,
                "dataset_num_features": num_features,
                "dataset_date_start": date_range[0],
                "dataset_date_end": date_range[1],
            })
        except Exception as e:
            logger.warning(f"Failed to log dataset info: {e}")

    def log_training_run(
        self,
        model,
        params: Dict[str, Any],
        metrics: Dict[str, float],
        X_train: pd.DataFrame = None,
        model_name: str = "base_credit_model",
    ) -> str:
        """
        End-to-end training run logging.
        Starts a run, logs params, metrics, model, and registers it.
        """
        try:
            with self.start_run(run_name=f"{model_name}_training"):
                # Log parameters
                self.log_params(params)

                # Log metrics
                self.log_metrics(metrics)

                # Log model with signature if training data available
                signature = None
                if X_train is not None:
                    from mlflow.models.signature import infer_signature
                    # Dummy prediction for signature inference
                    sample_input = X_train.head(1)
                    sample_output = model.predict(sample_input)
                    signature = infer_signature(sample_input, sample_output)

                model_uri = self.log_model(
                    model,
                    artifact_path="model",
                    signature=signature,
                    model_name=model_name,
                )

                logger.info(
                    f"Training run logged — model: {model_name}, "
                    f"metrics: {metrics}"
                )

                return model_uri
        except Exception as e:
            logger.error(f"Failed to log training run: {e}")
            return ""


# ── Singleton instance ────────────────────────────────────────────────

_tracker: Optional[MLflowTracker] = None


def get_mlflow_tracker() -> MLflowTracker:
    """Get or create the MLflow tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = MLflowTracker()
    return _tracker


def log_model_performance(
    model_name: str,
    gini: float,
    ks_statistic: float,
    auc_roc: float,
    precision: float,
    recall: float,
    f1_score: float,
    psi_per_feature: Optional[Dict[str, float]] = None,
) -> None:
    """
    Log model performance metrics for monitoring.
    Called after model evaluation on validation/test data.
    """
    tracker = get_mlflow_tracker()
    try:
        with tracker.start_run(run_name=f"{model_name}_evaluation"):
            tracker.log_metrics({
                "gini_coefficient": gini,
                "ks_statistic": ks_statistic,
                "auc_roc": auc_roc,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
            })

            if psi_per_feature:
                for feature_name, psi_value in psi_per_feature.items():
                    tracker.log_metrics({f"psi_{feature_name}": psi_value})

            logger.info(
                f"Model performance logged — {model_name}: "
                f"Gini={gini:.3f}, KS={ks_statistic:.3f}"
            )
    except Exception as e:
        logger.error(f"Failed to log model performance: {e}")
