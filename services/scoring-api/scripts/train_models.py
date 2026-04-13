"""
Train ML models on synthetic Nigerian credit data and save as pickles.

Generates realistic synthetic data with known feature-target relationships,
then trains:
  1. base_credit_model.pkl — GradientBoostingRegressor (300-850 scale)
  2. alternative_booster.pkl — GradientBoostingRegressor (behavioral boost)
  3. psychometric_engine.pkl — GradientBoostingRegressor (psychographic score)

Usage:
    cd services/scoring-api
    python scripts/train_models.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

np.random.seed(42)

N_SAMPLES = 50_000
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────
# 1. Synthetic Data Generation — realistic Nigerian credit profiles
# ──────────────────────────────────────────────────────────────────────

def generate_synthetic_data(n: int) -> pd.DataFrame:
    """
    Generate synthetic borrower data with realistic feature-target relationships.

    The ground-truth credit score is constructed from a known formula so we
    can verify model quality. Real-world noise is added to simulate actual data.
    """

    # ── Formal features ──────────────────────────────────────────────
    # Bureau scores: bimodal distribution (many thin-file, some established)
    thin_file_mask = np.random.random(n) < 0.35
    bureau_scores = np.where(
        thin_file_mask,
        np.random.normal(450, 60, n),   # Thin-file borrowers
        np.random.normal(620, 90, n),   # Established borrowers
    )
    bureau_scores = np.clip(bureau_scores, 300, 850)

    bureau_delinquency_flag = np.where(bureau_scores > 650, 0.0,
                                       np.where(np.random.random(n) < 0.4, 1.0, 0.0))

    # Debt-to-income: lower is better, correlated with bureau score
    dti_mean = np.where(bureau_scores > 600, 0.25, 0.45)
    debt_to_income_ratio = np.clip(
        np.random.normal(dti_mean, 0.15),
        0.0, 1.5
    )

    total_credit_accounts = np.clip(
        np.random.poisson(np.where(bureau_scores > 600, 4, 1)),
        0, 20
    ).astype(float)

    credit_utilization_ratio = np.clip(
        np.random.normal(
            np.where(bureau_scores > 650, 0.3, 0.6),
            0.2
        ),
        0.0, 1.0
    )

    oldest_account_age_months = np.clip(
        np.random.exponential(np.where(bureau_scores > 600, 48, 12)),
        1, 360
    )

    recent_inquiries_6m = np.clip(
        np.random.poisson(np.where(bureau_scores > 600, 1, 3)),
        0, 15
    ).astype(float)

    # ── Alternative features ─────────────────────────────────────────
    telco_consistency_index = np.clip(np.random.beta(2, 2, n), 0, 1)
    mobile_money_inflow_trend = np.clip(np.random.normal(0.4, 0.3, n), 0, 1)
    utility_payment_streak = np.clip(np.random.exponential(6), 0, 48)
    bnpl_repayment_rate = np.clip(np.random.beta(5, 2, n), 0, 1)
    savings_balance_trend = np.clip(np.random.normal(0.3, 0.3, n), 0, 1)

    # ── Psychographic features ───────────────────────────────────────
    address_stability_score = np.clip(np.random.beta(3, 2, n), 0, 1)
    employment_tenure_months = np.clip(np.random.exponential(24), 0, 240)
    app_usage_regularity = np.clip(np.random.beta(2, 3, n), 0, 1)

    # ── Ground-truth credit score (300-850) ──────────────────────────
    # Formula: weighted combination of all signals + noise
    formal_component = (
        0.30 * np.clip((bureau_scores - 300) / 550, 0, 1) * 100 +
        0.20 * (1 - bureau_delinquency_flag) * 100 +
        0.15 * np.clip(1 - debt_to_income_ratio, 0, 1) * 100 +
        0.10 * np.clip(total_credit_accounts / 10, 0, 1) * 100 +
        0.10 * np.clip(1 - credit_utilization_ratio, 0, 1) * 100 +
        0.10 * np.clip(oldest_account_age_months / 120, 0, 1) * 100 +
        0.05 * np.clip(1 - recent_inquiries_6m / 10, 0, 1) * 100
    )

    alt_component = (
        0.30 * telco_consistency_index * 100 +
        0.25 * mobile_money_inflow_trend * 100 +
        0.20 * np.clip(utility_payment_streak / 24, 0, 1) * 100 +
        0.15 * bnpl_repayment_rate * 100 +
        0.10 * savings_balance_trend * 100
    )

    psych_component = (
        0.40 * address_stability_score * 100 +
        0.35 * np.clip(employment_tenure_months / 60, 0, 1) * 100 +
        0.25 * app_usage_regularity * 100
    )

    # Composite: 70% formal + 20% alt + 10% psych + noise
    raw_score = (
        0.70 * formal_component +
        0.20 * alt_component +
        0.10 * psych_component +
        np.random.normal(0, 8, n)  # Real-world noise
    )

    # Scale to 300-850
    credit_score = np.clip(300 + (raw_score / 100) * 550, 300, 850).astype(int)

    # ── Default outcome (for model training feedback loop) ───────────
    # Probability of default inversely related to credit score
    pd_default = np.clip(
        np.exp(-0.008 * (credit_score - 300)) + np.random.normal(0, 0.02, n),
        0.01, 0.95
    )
    outcome = np.where(
        np.random.random(n) < pd_default,
        0,  # Defaulted
        1   # Repaid
    )

    return pd.DataFrame({
        # Formal
        "avg_bureau_score": bureau_scores,
        "bureau_delinquency_flag": bureau_delinquency_flag,
        "debt_to_income_ratio": debt_to_income_ratio,
        "total_credit_accounts": total_credit_accounts,
        "credit_utilization_ratio": credit_utilization_ratio,
        "oldest_account_age_months": oldest_account_age_months,
        "recent_inquiries_6m": recent_inquiries_6m,
        # Alternative
        "telco_consistency_index": telco_consistency_index,
        "mobile_money_inflow_trend": mobile_money_inflow_trend,
        "utility_payment_streak": utility_payment_streak,
        "bnpl_repayment_rate": bnpl_repayment_rate,
        "savings_balance_trend": savings_balance_trend,
        # Psychographic
        "address_stability_score": address_stability_score,
        "employment_tenure_months": employment_tenure_months,
        "app_usage_regularity": app_usage_regularity,
        # Target
        "credit_score": credit_score,
        "outcome": outcome,
    })


# ──────────────────────────────────────────────────────────────────────
# 2. Train Models
# ──────────────────────────────────────────────────────────────────────

def train_base_credit_model(df: pd.DataFrame) -> GradientBoostingRegressor:
    """
    Base Credit Model — trained on structured financial data.
    Predicts credit score (300-850) from bureau + formal features.
    """
    feature_cols = [
        "avg_bureau_score",
        "bureau_delinquency_flag",
        "debt_to_income_ratio",
        "total_credit_accounts",
        "credit_utilization_ratio",
        "oldest_account_age_months",
        "recent_inquiries_6m",
    ]

    X = df[feature_cols].values
    y = df["credit_score"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"Base Credit Model — Metrics")
    print(f"{'='*60}")
    print(f"  MAE:  {mae:.1f} points")
    print(f"  RMSE: {rmse:.1f} points")
    print(f"  R²:   {r2:.4f}")
    print(f"  Features: {feature_cols}")
    print(f"  Samples:  {len(X_train):,}")

    # Feature importance
    importances = dict(zip(feature_cols, model.feature_importances_))
    print(f"\n  Feature importance:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        print(f"    {feat:40s} {imp:.4f}")

    # Save model
    path = os.path.join(MODEL_DIR, "base_credit_model.pkl")
    joblib.dump(model, path)
    print(f"\n  Saved: {path}")

    # Save metadata
    metadata = {
        "model_type": "sklearn_gbr",
        "feature_names": feature_cols,
        "n_training_samples": len(X_train),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2_score": round(r2, 4),
        "version": "v1.0.0-synthetic",
    }
    meta_path = os.path.join(MODEL_DIR, "base_credit_model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return model


def train_alternative_booster(df: pd.DataFrame) -> GradientBoostingRegressor:
    """
    Alternative Data Booster — predicts behavioral score contribution
    from telco, mobile money, utility, BNPL, and savings data.
    """
    feature_cols = [
        "telco_consistency_index",
        "mobile_money_inflow_trend",
        "utility_payment_streak",
        "bnpl_repayment_rate",
        "savings_balance_trend",
    ]

    # Target: how much the alt data should boost the base score
    # This is the difference between the full composite and the formal-only score
    X = df[feature_cols].values

    # Create a target that correlates with alt features
    alt_target = (
        0.30 * df["telco_consistency_index"] * 100 +
        0.25 * df["mobile_money_inflow_trend"] * 100 +
        0.20 * np.clip(df["utility_payment_streak"] / 24, 0, 1) * 100 +
        0.15 * df["bnpl_repayment_rate"] * 100 +
        0.10 * df["savings_balance_trend"] * 100
    ).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, alt_target, test_size=0.2, random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_leaf=30,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"Alternative Booster — Metrics")
    print(f"{'='*60}")
    print(f"  MAE:  {mae:.2f}")
    print(f"  R²:   {r2:.4f}")
    print(f"  Features: {feature_cols}")
    print(f"  Samples:  {len(X_train):,}")

    path = os.path.join(MODEL_DIR, "alternative_booster.pkl")
    joblib.dump(model, path)
    print(f"\n  Saved: {path}")

    return model


def train_psychometric_engine(df: pd.DataFrame) -> GradientBoostingRegressor:
    """
    Psychometric Engine — predicts psychographic score contribution
    from address stability, employment tenure, and app usage.
    """
    feature_cols = [
        "address_stability_score",
        "employment_tenure_months",
        "app_usage_regularity",
    ]

    X = df[feature_cols].values

    psych_target = (
        0.40 * df["address_stability_score"] * 100 +
        0.35 * np.clip(df["employment_tenure_months"] / 60, 0, 1) * 100 +
        0.25 * df["app_usage_regularity"] * 100
    ).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, psych_target, test_size=0.2, random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_leaf=30,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"Psychometric Engine — Metrics")
    print(f"{'='*60}")
    print(f"  MAE:  {mae:.2f}")
    print(f"  R²:   {r2:.4f}")
    print(f"  Features: {feature_cols}")
    print(f"  Samples:  {len(X_train):,}")

    path = os.path.join(MODEL_DIR, "psychometric_engine.pkl")
    joblib.dump(model, path)
    print(f"\n  Saved: {path}")

    return model


# ──────────────────────────────────────────────────────────────────────
# 3. Main
# ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Generating {N_SAMPLES:,} synthetic borrower profiles...")
    df = generate_synthetic_data(N_SAMPLES)

    print(f"\nCredit score distribution:")
    print(f"  Mean:   {df['credit_score'].mean():.0f}")
    print(f"  Median: {df['credit_score'].median():.0f}")
    print(f"  Min:    {df['credit_score'].min()}")
    print(f"  Max:    {df['credit_score'].max()}")
    print(f"  Std:    {df['credit_score'].std():.0f}")
    print(f"  Default rate: {(1 - df['outcome'].mean()):.1%}")

    print(f"\n{'='*60}")
    print(f"Training ML models")
    print(f"{'='*60}")

    train_base_credit_model(df)
    train_alternative_booster(df)
    train_psychometric_engine(df)

    # Write model version
    version_path = os.path.join(MODEL_DIR, "model_version.txt")
    with open(version_path, "w") as f:
        f.write("v1.0.0-synthetic\n")

    print(f"\n{'='*60}")
    print(f"All models trained and saved to {MODEL_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
