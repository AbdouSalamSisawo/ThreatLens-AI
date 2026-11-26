"""
Trusted model artefact loading.

Only artefacts produced by this project's own training pipeline
(the Phishing-url-detection-ML research notebook) are loaded. Downloaded serialised models
are treated as untrusted and never auto-loaded. If the artefact is missing
or incompatible the service reports an explicit error state - it NEVER
falls back to a substitute model, random output, or mock predictions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib

from app.core.config import Settings

logger = logging.getLogger("threatlens.model")


@dataclass
class LoadedModel:
    pipeline: object
    metadata: dict
    metrics: dict
    feature_schema: dict


class ModelNotAvailableError(RuntimeError):
    """Raised when the model artefact is missing, corrupt, or incompatible."""


def load_model(settings: Settings) -> LoadedModel:
    artifacts: Path = settings.artifacts_dir
    model_path = artifacts / "phishing_model.joblib"
    meta_path = artifacts / "model_metadata.json"
    metrics_path = artifacts / "metrics.json"
    schema_path = artifacts / "feature_schema.json"

    missing = [p.name for p in (model_path, meta_path, metrics_path, schema_path) if not p.exists()]
    if missing:
        raise ModelNotAvailableError(
            "Model artefacts are missing: "
            + ", ".join(missing)
            + ". Place the trained artefacts in backend/artifacts/ and run "
            "'python scripts/validate_model.py' (see docs/MODEL_DROPIN.md)."
        )

    try:
        pipeline = joblib.load(model_path)
        metadata = json.loads(meta_path.read_text())
        metrics = json.loads(metrics_path.read_text())
        schema = json.loads(schema_path.read_text())
    except Exception as exc:  # noqa: BLE001
        raise ModelNotAvailableError(
            f"Model artefacts exist but could not be loaded: {exc}"
        ) from exc

    # Guard against serving a model trained with a different feature schema.
    from app.services.feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION

    if schema.get("schema_version") != FEATURE_SCHEMA_VERSION:
        raise ModelNotAvailableError(
            f"Feature schema mismatch: model was trained with schema "
            f"{schema.get('schema_version')}, but the code provides "
            f"{FEATURE_SCHEMA_VERSION}. Retrain the model."
        )
    if list(schema.get("feature_names", [])) != list(FEATURE_NAMES):
        raise ModelNotAvailableError(
            "Feature name list differs between the artefact and the code. Retrain the model."
        )

    logger.info(
        "Model loaded: %s v%s (%s)",
        metadata.get("model_id"),
        metadata.get("model_version"),
        metadata.get("selected_model"),
    )
    return LoadedModel(
        pipeline=pipeline, metadata=metadata, metrics=metrics, feature_schema=schema
    )
