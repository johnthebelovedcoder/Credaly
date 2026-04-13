"""
Model Training Pipeline — trains the Base Credit Model on synthetic data
to produce a working model artifact for Phase 0.
Per PRD FR-025: XGBoost gradient-boosted tree architecture.

Usage:
    python -m scripts.train_baseline_model
"""

import logging
import os
import pickle
from pathlib import Path

import numpy as np
import joblib

logger = logging.getLogger(__name__)

# Feature names that the model expects
FEATURE_NAMES = [
    "avg_bureau_score",
    "bureau_delinquency_flag",
    "debt_to_income_ratio",
    "total_credit_accounts",
    "credit_utilization_ratio",
    "oldest_account_age_months",
    "recent_inquiries_6m",
]


def generate_synthetic_training_data(n_samples: int = 10000, seed: int = 42) -> tuple:
    """
    Generate synthetic training data that mimics realistic Nigerian credit patterns.

    The data follows these relationships:
    - Higher bureau score → lower default probability
    - Delinquency flags → much higher default probability
    - More accounts + longer history → lower default probability
    - High debt-to-income → higher default probability
    """
    rng = np.random.RandomState(seed)

    # Generate features
    avg_bureau_score = rng.normal(600, 100, n_samples).clip(300, 850)
    bureau_delinquency = (rng.random(n_samples) > 0.7).astype(float)
    debt_to_income = rng.exponential(0.3, n_samples).clip(0, 1)
    total_accounts = rng.poisson(3, n_samples).clip(0, 15).astype(float)
    credit_utilization = rng.beta(2, 5, n_samples).clip(0, 1)
    oldest_age = rng.exponential(36, n_samples).clip(0, 120)
    recent_inquiries = rng.poisson(2, n_samples).clip(0, 10).astype(float)

    X = np.column_stack([
        avg_bureau_score,
        bureau_delinquency,
        debt_to_income,
        total_accounts,
        credit_utilization,
        oldest_age,
        recent_inquiries,
    ])

    # Generate labels: 1 = repaid (good), 0 = default (bad)
    # Base probability from bureau score
    default_prob = 1.0 - (avg_bureau_score - 300) / 550  # 0-1 range

    # Modifiers
    default_prob += bureau_delinquency * 0.3
    default_prob += debt_to_income * 0.2
    default_prob -= (total_accounts / 15) * 0.1
    default_prob += credit_utilization * 0.1
    default_prob -= (oldest_age / 120) * 0.1
    default_prob += (recent_inquiries / 10) * 0.05

    # Add noise
    default_prob += rng.normal(0, 0.05, n_samples)
    default_prob = default_prob.clip(0, 1)

    y = (rng.random(n_samples) > default_prob).astype(int)

    logger.info(f"Generated {n_samples} synthetic samples")
    logger.info(f"  Good (1): {y.sum()} ({y.mean()*100:.1f}%)")
    logger.info(f"  Bad  (0): {(1-y).sum()} ({(1-y.mean())*100:.1f}%)")

    return X, y


def train_base_model(output_dir: str = "./models") -> None:
    """
    Train the Base Credit Model and save artifacts.

    Tries XGBoost first, falls back to scikit-learn GradientBoosting if
    XGBoost is not installed (common in dev environments).
    """
    logger.info("Generating synthetic training data...")
    X, y = generate_synthetic_training_data(n_samples=10000)

    logger.info("Training Base Credit Model...")

    model = None
    model_type = None

    # Try XGBoost first
    try:
        import xgboost as xgb
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss",
        )
        model_type = "xgboost"
        logger.info("Using XGBoost")
    except ImportError:
        pass

    # Fall back to scikit-learn
    if model is None:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
            )
            model_type = "sklearn_gb"
            logger.info("Using scikit-learn GradientBoosting (XGBoost not available)")
        except ImportError:
            logger.error("Neither XGBoost nor scikit-learn available!")
            return

    # Train
    model.fit(X, y)

    # Evaluate
    train_accuracy = model.score(X, y)

    # Gini coefficient approximation
    if hasattr(model, "predict_proba"):
        probas = model.predict_proba(X)[:, 1]
        # Sort by predicted probability
        sorted_indices = np.argsort(probas)
        sorted_labels = y[sorted_indices]
        # Gini from Lorenz curve
        n = len(sorted_labels)
        cumsum = np.cumsum(sorted_labels)
        gini = (2 * cumsum.sum() / cumsum[-1] - n - 1) / n if cumsum[-1] > 0 else 0
    else:
        gini = None

    logger.info(f"Model trained: {model_type}")
    logger.info(f"  Train accuracy: {train_accuracy:.4f}")
    if gini is not None:
        logger.info(f"  Gini coefficient: {gini:.4f}")

    # ── MLflow Integration — log training run ─────────────────────────
    try:
        from src.services.mlflow_integration import get_mlflow_tracker

        tracker = get_mlflow_tracker()
        tracker.log_training_run(
            model=model,
            params={
                "model_type": model_type,
                "n_estimators": 100,
                "max_depth": 4,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "n_samples": len(y),
                "good_rate": float(y.mean()),
            },
            metrics={
                "train_accuracy": float(train_accuracy),
                "gini_coefficient": float(gini) if gini is not None else 0.0,
            },
            X_train=None,  # Would pass DataFrame if available
            model_name="base_credit_model",
        )
        logger.info("Training run logged to MLflow")
    except Exception as e:
        logger.warning(f"MLflow logging failed: {e} — model artifacts still saved")

    # Save model
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "base_credit_model.pkl")
    joblib.dump(model, model_path)
    logger.info(f"Model saved to {model_path}")

    # Save feature metadata
    metadata = {
        "model_type": model_type,
        "feature_names": FEATURE_NAMES,
        "n_training_samples": len(y),
        "train_accuracy": float(train_accuracy),
        "gini_coefficient": float(gini) if gini is not None else None,
        "good_rate": float(y.mean()),
        "version": "v1.0.0-synthetic",
    }
    metadata_path = os.path.join(output_dir, "base_credit_model_metadata.json")
    import json
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved to {metadata_path}")

    # Save model version
    version_path = os.path.join(output_dir, "model_version.txt")
    with open(version_path, "w") as f:
        f.write(metadata["version"])
    logger.info(f"Version saved to {version_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    train_base_model()
