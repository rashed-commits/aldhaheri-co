"""
Phase 3: Model Training
=======================
Reads ``data/features.csv``, trains an XGBoost binary classifier with
time-series cross-validation, evaluates it, and persists the artefacts
to ``model/saved/``.

Improvements over baseline
--------------------------
* Walk-forward window — only trains on the most recent N rows per ticker.
* Two-pass feature pruning — drops low-importance features before final CV.
* Saves ``feature_importance.json`` alongside the model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src.config import CFG
from src.utils import (
    check_required_columns,
    drop_na_rows,
    ensure_dir,
    get_logger,
    load_csv,
)

log = get_logger("train")

# Columns that are not features (excluded before fitting)
_NON_FEATURE_COLS = ["date", "ticker", "target", "open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def load_and_prepare(
    path: Path,
) -> Tuple[pd.DataFrame, pd.Series, List[str], pd.DataFrame]:
    """
    Load features CSV, validate it, and split into X / y.

    Returns
    -------
    X : pd.DataFrame
        Feature matrix (float64, NaN-free).
    y : pd.Series
        Binary target vector.
    feature_names : list[str]
        Ordered list of feature column names.
    raw : pd.DataFrame
        Full DataFrame (used for time-ordered CV splitting).
    """
    df = load_csv(path)
    check_required_columns(df, ["target"], context="features.csv")
    df = drop_na_rows(df, context="train")

    feature_names = [c for c in df.columns if c not in _NON_FEATURE_COLS]
    X = df[feature_names].astype(float)
    y = df["target"].astype(int)
    return X, y, feature_names, df


# ---------------------------------------------------------------------------
# Walk-forward window
# ---------------------------------------------------------------------------

def apply_walk_forward_window(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Keep only the most recent *window* rows per ticker."""
    parts = []
    for ticker, grp in df.groupby("ticker", sort=False):
        grp_sorted = grp.sort_values("date")
        parts.append(grp_sorted.tail(window))
    result = pd.concat(parts, ignore_index=True)
    log.info(
        "Walk-forward window: %d -> %d rows (window=%d per ticker).",
        len(df), len(result), window,
    )
    return result


# ---------------------------------------------------------------------------
# Feature importance pruning
# ---------------------------------------------------------------------------

def prune_features(
    X: pd.DataFrame,
    y: pd.Series,
    feature_names: List[str],
    threshold: float,
) -> Tuple[List[str], Dict[str, float]]:
    """
    Two-pass feature selection.

    Pass 1: Quick train on all features to extract importance scores.
    Returns the surviving feature names and full importance dict.
    """
    log.info("Pass 1: quick train on %d features for importance scores ...", len(feature_names))
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = XGBClassifier(
        n_estimators=100,  # fewer trees for quick pass
        max_depth=CFG.max_depth,
        learning_rate=CFG.learning_rate,
        subsample=CFG.subsample,
        colsample_bytree=CFG.colsample_bytree,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=CFG.random_state,
    )
    model.fit(X_scaled, y)

    importances = dict(zip(feature_names, model.feature_importances_))

    # Sort and log
    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    for name, imp in sorted_imp:
        log.info("  %-25s  importance=%.4f%s", name, imp, "" if imp >= threshold else "  [PRUNED]")

    surviving = [name for name, imp in sorted_imp if imp >= threshold]
    pruned_count = len(feature_names) - len(surviving)
    log.info(
        "Pruned %d features below threshold %.4f; %d features survive.",
        pruned_count, threshold, len(surviving),
    )

    if not surviving:
        log.warning("All features pruned! Keeping top 5 by importance.")
        surviving = [name for name, _ in sorted_imp[:5]]

    return surviving, importances


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = CFG.cv_folds,
) -> Dict[str, Any]:
    """
    Run time-series cross-validation and return aggregated metrics.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    scaler = StandardScaler()

    fold_metrics: Dict[str, List[float]] = {
        "accuracy": [], "roc_auc": [], "f1": []
    }

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), start=1):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

        X_tr_sc = scaler.fit_transform(X_tr)
        X_val_sc = scaler.transform(X_val)

        # Compute class weight to handle imbalanced targets
        neg_count = int((y_tr == 0).sum())
        pos_count = int((y_tr == 1).sum())
        scale_pos = neg_count / pos_count if pos_count > 0 else 1.0

        model = XGBClassifier(
            n_estimators=CFG.n_estimators,
            max_depth=CFG.max_depth,
            learning_rate=CFG.learning_rate,
            subsample=CFG.subsample,
            colsample_bytree=CFG.colsample_bytree,
            scale_pos_weight=scale_pos,
            early_stopping_rounds=30,
            eval_metric="logloss",
            random_state=CFG.random_state,
        )
        model.fit(X_tr_sc, y_tr, eval_set=[(X_val_sc, y_val)], verbose=False)
        y_pred = model.predict(X_val_sc)
        y_prob = model.predict_proba(X_val_sc)[:, 1]

        fold_metrics["accuracy"].append(accuracy_score(y_val, y_pred))
        fold_metrics["roc_auc"].append(roc_auc_score(y_val, y_prob))
        fold_metrics["f1"].append(f1_score(y_val, y_pred, zero_division=0))

        log.info(
            "Fold %d/%d — acc=%.4f  roc_auc=%.4f  f1=%.4f",
            fold, n_splits,
            fold_metrics["accuracy"][-1],
            fold_metrics["roc_auc"][-1],
            fold_metrics["f1"][-1],
        )

    return fold_metrics


# ---------------------------------------------------------------------------
# Final model fit
# ---------------------------------------------------------------------------

def train_final_model(
    X: pd.DataFrame, y: pd.Series
) -> Tuple[XGBClassifier, StandardScaler]:
    """Fit the final XGBoost model on the full dataset."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    neg_count = int((y == 0).sum())
    pos_count = int((y == 1).sum())
    scale_pos = neg_count / pos_count if pos_count > 0 else 1.0

    model = XGBClassifier(
        n_estimators=CFG.n_estimators,
        max_depth=CFG.max_depth,
        learning_rate=CFG.learning_rate,
        subsample=CFG.subsample,
        colsample_bytree=CFG.colsample_bytree,
        scale_pos_weight=scale_pos,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=CFG.random_state,
    )
    model.fit(X_scaled, y)
    log.info("Final model trained on %d samples, %d features.", len(X), X.shape[1])
    return model, scaler


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_artefacts(
    model: XGBClassifier,
    scaler: StandardScaler,
    feature_names: List[str],
    metrics: Dict[str, Any],
    importances: Dict[str, float],
    out_dir: Path,
) -> None:
    """
    Persist model, scaler, feature list, metrics, and feature importances.

    Files written
    -------------
    ``model.joblib``            — fitted XGBClassifier
    ``scaler.joblib``           — fitted StandardScaler
    ``feature_names.json``      — ordered feature list (pruned)
    ``metrics.json``            — CV metric summary
    ``feature_importance.json`` — all feature importance scores
    """
    ensure_dir(out_dir)

    joblib.dump(model, out_dir / "model.joblib")
    log.info("Saved model -> %s", out_dir / "model.joblib")

    joblib.dump(scaler, out_dir / "scaler.joblib")
    log.info("Saved scaler -> %s", out_dir / "scaler.joblib")

    with open(out_dir / "feature_names.json", "w") as fh:
        json.dump(feature_names, fh, indent=2)
    log.info("Saved feature names -> %s", out_dir / "feature_names.json")

    summary = {
        k: {
            "mean": float(np.mean(v)),
            "std": float(np.std(v)),
            "values": [float(x) for x in v],
        }
        for k, v in metrics.items()
    }
    with open(out_dir / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    log.info("Saved CV metrics -> %s", out_dir / "metrics.json")

    sorted_imp = {k: float(v) for k, v in sorted(importances.items(), key=lambda x: x[1], reverse=True)}
    with open(out_dir / "feature_importance.json", "w") as fh:
        json.dump(sorted_imp, fh, indent=2)
    log.info("Saved feature importance -> %s", out_dir / "feature_importance.json")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Entry point called by ``main.py --phase 3``."""
    features_path = CFG.data_dir / "features.csv"
    df = load_csv(features_path)
    check_required_columns(df, ["target"], context="features.csv")

    # --- walk-forward window ---
    df = apply_walk_forward_window(df, CFG.walk_forward_window)
    df = drop_na_rows(df, context="train")

    feature_names = [c for c in df.columns if c not in _NON_FEATURE_COLS]
    X = df[feature_names].astype(float)
    y = df["target"].astype(int)

    log.info(
        "Dataset: %d samples, %d features, %.1f%% positive class.",
        len(X), len(feature_names), 100.0 * y.mean(),
    )

    # --- feature importance pruning (two-pass) ---
    surviving, importances = prune_features(
        X, y, feature_names, CFG.min_feature_importance,
    )
    X = X[surviving]
    feature_names = surviving

    log.info(
        "After pruning: %d samples, %d features.", len(X), len(feature_names),
    )

    # --- cross-validation (pass 2 with pruned features) ---
    log.info("Pass 2: %d-fold time-series cross-validation ...", CFG.cv_folds)
    cv_metrics = cross_validate(X, y)
    for metric, values in cv_metrics.items():
        log.info(
            "CV %s — mean=%.4f  std=%.4f",
            metric, np.mean(values), np.std(values),
        )

    # --- final model ---
    model, scaler = train_final_model(X, y)

    # --- evaluate on full set (sanity check) ---
    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    log.info("\n%s", classification_report(y, y_pred, zero_division=0))

    # --- persist artefacts ---
    save_artefacts(model, scaler, feature_names, cv_metrics, importances, CFG.model_dir)
    log.info("Phase 3 complete.")
