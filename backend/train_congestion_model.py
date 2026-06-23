"""
train_congestion_model.py
--------------------------
Trains the ML congestion weight predictor and saves:
  - congestion_model.pkl
  - congestion_feature_columns.pkl

Run:  python train_congestion_model.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold, cross_validate
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURE_COLS = [
    'road_type',
    'dist_from_hazard_km',
    'hour',
    'day_of_week',
    'is_peak',
    'zone_cluster',
    'requires_closure',
    'duration_norm',
    'cause_accident',
    'cause_breakdown',
    'cause_waterlog',
    'cause_protest',
    'veh_truck',
    'veh_car',
    'veh_two_wheeler',
    'veh_lcv',
]

TARGET_COL = 'congestion_weight'


def train():
    data_path = os.path.join(BACKEND_DIR, 'congestion_training_data.csv')
    print(f"Loading training data from {data_path} ...")
    df = pd.read_csv(data_path)
    print(f"  {len(df)} observations, {len(FEATURE_COLS)} features, target: {TARGET_COL}")

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    # ── 5-Fold Cross-Validation ────────────────────────────────────────────
    print("\nRunning 5-Fold CV on GradientBoostingRegressor ...")
    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        min_samples_leaf=10,
        random_state=42,
    )

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_mae, cv_r2 = [], []

    for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        fold_model = GradientBoostingRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            min_samples_leaf=10,
            random_state=42,
        )
        fold_model.fit(X_tr, y_tr)
        preds = fold_model.predict(X_val)

        mae = mean_absolute_error(y_val, preds)
        r2  = r2_score(y_val, preds)
        cv_mae.append(mae)
        cv_r2.append(r2)
        print(f"  Fold {fold+1}: MAE={mae:.4f}  R²={r2:.4f}")

    print(f"\n  Mean CV MAE : {np.mean(cv_mae):.4f} ± {np.std(cv_mae):.4f}")
    print(f"  Mean CV R²  : {np.mean(cv_r2):.4f} ± {np.std(cv_r2):.4f}")

    # ── Train final model on full data ────────────────────────────────────
    print("\nTraining final model on full dataset ...")
    model.fit(X, y)

    train_preds = model.predict(X)
    print(f"  Full-data MAE : {mean_absolute_error(y, train_preds):.4f}")
    print(f"  Full-data R²  : {r2_score(y, train_preds):.4f}")

    # ── Feature importance ────────────────────────────────────────────────
    print("\nFeature importances (built-in):")
    importance = model.feature_importances_
    for name, imp in sorted(zip(FEATURE_COLS, importance), key=lambda x: -x[1]):
        print(f"  {name:<30} {imp:.4f}")

    # ── Save model + feature columns ──────────────────────────────────────
    model_path   = os.path.join(BACKEND_DIR, 'congestion_model.pkl')
    columns_path = os.path.join(BACKEND_DIR, 'congestion_feature_columns.pkl')

    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    with open(columns_path, 'wb') as f:
        pickle.dump(FEATURE_COLS, f)

    print(f"\nSaved model      → {model_path}")
    print(f"Saved feature cols → {columns_path}")

    return model, np.mean(cv_r2), np.mean(cv_mae)


if __name__ == '__main__':
    train()
