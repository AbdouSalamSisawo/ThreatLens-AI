"""
ThreatLens AI - Model Training
==============================

Reproducible training pipeline:

  1. Load the processed dataset (produced by prepare_dataset.py).
  2. Extract lexical features with the SHARED extractor (same module the
     API uses at inference time).
  3. Stratified 60/20/20 train/validation/test split (fixed seed).
  4. Compare candidate models on the VALIDATION set:
       - Logistic Regression (baseline + interpretable)
       - Random Forest
       - Hist Gradient Boosting
       - Dummy (majority-class) baseline for context
  5. Selection rule (documented, implemented below):
       highest validation PR-AUC wins; if Logistic Regression is within
       0.01 PR-AUC of the best model, Logistic Regression is selected
       because it supports exact per-instance feature contributions
       (coefficient x standardised value) without extra dependencies.
  6. Evaluate the SELECTED model ONCE on the held-out test set.
  7. Additional honesty checks:
       - Domain-grouped split experiment (does performance survive when
         URLs from the same registrable domain never cross splits?)
       - Out-of-source sanity checks: recall on 300 recently collected
         OpenPhish URLs; false-positive rate on the 1,000 most popular
         Majestic Million domains (documented construction).
  8. Persist: model pipeline, feature schema, metadata, metrics.

The held-out test set is used exactly once for the final evaluation.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.feature_extractor import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    extract_features,
)

RANDOM_SEED = 42
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
MODEL_VERSION = "1.0.0"

# Documented classification bands (model probability -> user-facing class).
# The binary decision threshold remains 0.5 (the model's actual boundary).
CLASSIFICATION_BANDS = {
    "high_risk": {"min_probability": 0.80, "description": "Strong phishing indicators"},
    "suspicious": {"min_probability": 0.50, "description": "Meaningful phishing indicators"},
    "likely_benign": {"min_probability": 0.00, "description": "No dominant phishing signals"},
}
UNCERTAIN_BAND = {"lower": 0.35, "upper": 0.65}


def build_feature_frame(urls: pd.Series) -> pd.DataFrame:
    rows = [extract_features(u) for u in urls]
    return pd.DataFrame(rows, columns=list(FEATURE_NAMES))


def metrics_for(y_true, proba, threshold: float = 0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    return {
        "accuracy": float((pred == y_true).mean()),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, proba)) if len(set(y_true)) > 1 else None,
        "pr_auc": float(average_precision_score(y_true, proba)) if len(set(y_true)) > 1 else None,
        "confusion_matrix": {
            "tn": int(confusion_matrix(y_true, pred, labels=[0, 1])[0][0]),
            "fp": int(confusion_matrix(y_true, pred, labels=[0, 1])[0][1]),
            "fn": int(confusion_matrix(y_true, pred, labels=[0, 1])[1][0]),
            "tp": int(confusion_matrix(y_true, pred, labels=[0, 1])[1][1]),
        },
    }


def candidate_models() -> dict:
    return {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000, C=1.0, random_state=RANDOM_SEED
                    ),
                ),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=2,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.1,
            random_state=RANDOM_SEED,
        ),
    }


def out_of_source_checks(model, data_dir: Path) -> dict:
    """Honest generalisation probes on data the model never trained on."""
    checks: dict = {}

    openphish_path = data_dir / "raw" / "openphish_feed.txt"
    if openphish_path.exists():
        urls = [
            line.strip()
            for line in openphish_path.read_text().splitlines()
            if line.strip().startswith("http")
        ][:300]
        if urls:
            X = build_feature_frame(pd.Series(urls))
            proba = model.predict_proba(X)[:, 1]
            pred = (proba >= 0.5).astype(int)
            checks["openphish_recent_300"] = {
                "description": (
                    "Recall on 300 URLs from the live OpenPhish free feed "
                    "retrieved 2026-10-29. Out-of-time and out-of-source "
                    "sample; indicative only, not a benchmark."
                ),
                "n": len(urls),
                "flagged_as_phishing": int(pred.sum()),
                "recall_proxy": round(float(pred.mean()), 4),
            }

    majestic_path = data_dir / "raw" / "majestic_million.csv"
    if majestic_path.exists():
        try:
            dom = pd.read_csv(majestic_million_path(majestic_path))
            top = dom.iloc[:1000][dom.columns[2]].astype(str).str.lower()
            urls = [f"https://{d}" for d in top if d and "." in d]
            X = build_feature_frame(pd.Series(urls))
            proba = model.predict_proba(X)[:, 1]
            pred = (proba >= 0.5).astype(int)
            checks["majestic_top_1000"] = {
                "description": (
                    "False-positive rate on HTTPS home-page URLs constructed "
                    "from the 1,000 most-visited domains (Majestic Million, "
                    "retrieved 2026-10-29). Constructed URLs, documented method."
                ),
                "n": len(urls),
                "flagged_as_phishing": int(pred.sum()),
                "false_positive_rate": round(float(pred.mean()), 4),
            }
        except Exception as exc:  # noqa: BLE001 - probe must not break training
            checks["majestic_top_1000"] = {"error": str(exc)}
    return checks


def majestic_million_path(path: Path) -> Path:
    return path


def domain_grouped_evaluation(df: pd.DataFrame) -> dict:
    """
    Second, stricter evaluation: GroupShuffleSplit by registrable domain so
    that no domain appears in both train and the grouped holdout. Reported
    alongside the primary random-split metrics to expose possible leakage
    inflation; it is NOT the selection criterion.
    """
    from sklearn.base import clone

    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_SEED)
    domains = df["url"].map(lambda u: extract_features(u)["hostname_entropy"] and u)
    # Reuse the registrable-domain logic from the extractor
    from app.services.feature_extractor import parse_url

    def reg_domain(u: str) -> str:
        try:
            return parse_url(u).registrable_domain
        except Exception:  # noqa: BLE001
            return u

    groups = df["url"].map(reg_domain)
    train_idx, hold_idx = next(gss.split(df, groups=groups))

    X = build_feature_frame(df["url"])
    y = df["label"].values

    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, random_state=RANDOM_SEED)),
        ]
    )
    pipe.fit(X.iloc[train_idx], y[train_idx])
    proba = pipe.predict_proba(X.iloc[hold_idx])[:, 1]
    m = metrics_for(y[hold_idx], proba)
    return {
        "description": (
            "Logistic Regression retrained with a domain-grouped split: no "
            "registrable domain appears in both train and holdout. A large "
            "drop versus the random split indicates domain memorisation."
        ),
        "n_train": int(len(train_idx)),
        "n_holdout": int(len(hold_idx)),
        "n_unique_domains_holdout": int(groups.iloc[hold_idx].nunique()),
        "metrics": m,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the ThreatLens model")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_DIR / "data" / "processed" / "phishing_clean.csv",
    )
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DIR / "data")
    args = parser.parse_args()

    warnings.filterwarnings("ignore", category=UserWarning)
    t_start = datetime.now(timezone.utc)

    df = pd.read_csv(args.dataset)
    assert {"url", "label"}.issubset(df.columns), "Dataset schema invalid"

    print(f"[1/6] Extracting features for {len(df)} URLs ...")
    X_all = build_feature_frame(df["url"])
    y_all = df["label"].values

    # -- Splits ---------------------------------------------------------------
    X_train, X_tmp, y_train, y_tmp = train_test_split(
        X_all, y_all, test_size=0.40, stratify=y_all, random_state=RANDOM_SEED
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=RANDOM_SEED
    )
    print(
        f"      split sizes: train={len(X_train)} val={len(X_val)} test={len(X_test)}"
    )

    # -- Candidate comparison on validation ------------------------------------
    print("[2/6] Comparing candidate models on the validation set ...")
    val_results = {}
    for name, model in candidate_models().items():
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_val)[:, 1]
        val_results[name] = metrics_for(y_val, proba)
        print(f"      {name:24s} val PR-AUC={val_results[name]['pr_auc']:.4f} "
              f"F1={val_results[name]['f1']:.4f}")

    # Majority-class baseline for context (train performance, not a candidate)
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train, y_train)
    dummy_acc = float((dummy.predict(X_val) == y_val).mean())

    # -- Documented selection rule ---------------------------------------------
    best_name = max(val_results, key=lambda n: val_results[n]["pr_auc"] or 0.0)
    best_pr = val_results[best_name]["pr_auc"]
    lr_pr = val_results["logistic_regression"]["pr_auc"]
    if best_name != "logistic_regression" and (best_pr - lr_pr) <= 0.01:
        selected_name = "logistic_regression"
        selection_reason = (
            f"Validation PR-AUC within 0.01 of the best candidate "
            f"({best_name}: {best_pr:.4f} vs {lr_pr:.4f}); Logistic Regression "
            f"selected per the documented simplicity/explainability tie-break "
            f"(exact per-instance coefficient contributions)."
        )
    else:
        selected_name = best_name
        selection_reason = (
            f"Highest validation PR-AUC ({best_pr:.4f}); margin over Logistic "
            f"Regression ({lr_pr:.4f}) exceeded the 0.01 tie-break band."
        )
    print(f"[3/6] Selected: {selected_name} - {selection_reason}")

    # -- Refit on train+validation, evaluate ONCE on test ----------------------
    final_model = candidate_models()[selected_name]
    X_trv = pd.concat([X_train, X_val])
    y_trv = np.concatenate([y_train, y_val])
    final_model.fit(X_trv, y_trv)
    test_proba = final_model.predict_proba(X_test)[:, 1]
    test_metrics = metrics_for(y_test, test_proba)
    print(
        f"[4/6] Held-out test: acc={test_metrics['accuracy']:.4f} "
        f"precision={test_metrics['precision']:.4f} recall={test_metrics['recall']:.4f} "
        f"F1={test_metrics['f1']:.4f} PR-AUC={test_metrics['pr_auc']:.4f}"
    )

    # -- Honesty probes ----------------------------------------------------------
    print("[5/6] Running domain-grouped and out-of-source checks ...")
    grouped = domain_grouped_evaluation(df)
    oos = out_of_source_checks(final_model, args.data_dir)

    # -- Persist artefacts ---------------------------------------------------------
    print("[6/6] Saving artefacts ...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACTS_DIR / "phishing_model.joblib"
    joblib.dump(final_model, model_path)

    feature_schema = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "n_features": len(FEATURE_NAMES),
        "note": "Order is part of the contract; bump schema_version to change.",
    }
    (ARTIFACTS_DIR / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2))

    trained_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "model_id": "threatlens-phishing-url-classifier",
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "selected_model": selected_name,
        "selection_reason": selection_reason,
        "sklearn_pipeline": True,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "classification_bands": CLASSIFICATION_BANDS,
        "uncertain_band": UNCERTAIN_BAND,
        "positive_class": 1,
        "positive_class_label": "phishing",
        "probability_meaning": (
            "Estimated model probability for the phishing class from "
            "predict_proba. NOT a calibrated probability and NOT the "
            "probability of criminal activity."
        ),
        "dataset": {
            "source": "pirocheto/phishing-url (TabNetone corpus, CC-BY-4.0)",
            "retrieved": "2026-10-29",
            "prepared_records": int(len(df)),
            "class_distribution": {
                "phishing": int((df['label'] == 1).sum()),
                "legitimate": int((df['label'] == 0).sum()),
            },
        },
        "training_config": {
            "random_seed": RANDOM_SEED,
            "split": "60/20/20 stratified train/validation/test",
            "decision_threshold": 0.5,
            "candidates": list(candidate_models().keys()),
            "class_imbalance_handling": "None required - dataset is approximately balanced",
        },
        "artifacts": {
            "model": str(model_path.name),
            "metrics": "metrics.json",
            "feature_schema": "feature_schema.json",
        },
    }
    (ARTIFACTS_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2))

    metrics = {
        "model_id": metadata["model_id"],
        "model_version": MODEL_VERSION,
        "selected_model": selected_name,
        "trained_at": trained_at,
        "dataset": metadata["dataset"],
        "split_sizes": {
            "train": int(len(X_train)),
            "validation": int(len(X_val)),
            "test": int(len(X_test)),
        },
        "validation_comparison": val_results,
        "majority_baseline_validation_accuracy": dummy_acc,
        "test_metrics": test_metrics,
        "domain_grouped_evaluation": grouped,
        "out_of_source_checks": oos,
        "evaluation_notes": [
            "Metrics come from a single evaluation on the held-out test set.",
            "The dataset is a public research corpus; it may not represent "
            "real-world traffic mix or current phishing campaigns.",
            "The random split shares structural patterns across splits; see "
            "domain_grouped_evaluation for a stricter view.",
            "Probabilities are uncalibrated; bands are decision aids, not "
            "measured risk levels.",
        ],
    }
    (ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    print("Artefacts written to", ARTIFACTS_DIR)
    print(f"Total wall time: {(datetime.now(timezone.utc) - t_start).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
