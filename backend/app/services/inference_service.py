"""
Inference service.

Runs genuine predictions with the trained scikit-learn pipeline. There is
no fallback prediction path: if the model is unavailable or inference fails,
the API returns an explicit service error (HTTP 503) - never a guess.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from app.ml.model_loader import LoadedModel, ModelNotAvailableError
from app.services.feature_extractor import extract_features

logger = logging.getLogger("threatlens.inference")


class InferenceError(RuntimeError):
    """Raised when prediction fails for a loaded model."""


class InferenceService:
    def __init__(self, model: LoadedModel) -> None:
        self._model = model
        self._pipeline = model.pipeline
        md = model.metadata
        self._bands = md.get("classification_bands", {})
        self._uncertain = md.get("uncertain_band", {"lower": 0.35, "upper": 0.65})

    @property
    def model_version(self) -> str:
        return str(self._model.metadata.get("model_version", "unknown"))

    @property
    def model_id(self) -> str:
        return str(self._model.metadata.get("model_id", "unknown"))

    @property
    def selected_model(self) -> str:
        return str(self._model.metadata.get("selected_model", "unknown"))

    @property
    def feature_schema_version(self) -> str:
        return str(self._model.metadata.get("feature_schema_version", "unknown"))

    def predict(self, url: str) -> dict:
        """
        Run the trained model on one URL.

        Returns a dict with the estimated probability of the PHISHING class,
        the binary prediction at the 0.5 threshold, the user-facing
        classification band, the risk score (probability x 100, documented)
        and the uncertainty flag. All outputs derive from the model.
        """
        from app.services.feature_extractor import FEATURE_NAMES

        t0 = time.perf_counter()
        features = extract_features(url)
        import pandas as pd

        X = pd.DataFrame(
            [[float(features[name]) for name in FEATURE_NAMES]],
            columns=list(FEATURE_NAMES),
        )
        try:
            proba = self._pipeline.predict_proba(X)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inference failed")
            raise InferenceError("Model inference failed.") from exc

        p_phishing = float(np.asarray(proba)[0][1])
        # Ordered band mapping from model_metadata (high risk -> benign).
        classification = "likely_benign"
        for band_name in ("likely_benign", "suspicious", "high_risk"):
            band = self._bands.get(band_name, {})
            if p_phishing >= float(band.get("min_probability", 0.0)):
                classification = band_name
        lower = float(self._uncertain.get("lower", 0.35))
        upper = float(self._uncertain.get("upper", 0.65))

        return {
            "probability_phishing": p_phishing,
            "binary_prediction": "phishing" if p_phishing >= 0.5 else "benign",
            "classification": classification,
            "risk_score": int(round(p_phishing * 100)),
            "is_uncertain": bool(lower <= p_phishing <= upper),
            "features": features,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }


def get_inference_service(model: LoadedModel | None) -> InferenceService:
    if model is None:
        raise ModelNotAvailableError("Model not loaded")
    return InferenceService(model)
