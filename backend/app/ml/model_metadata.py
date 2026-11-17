"""Model metadata helpers (single accessor used by routes and dashboard)."""

from __future__ import annotations

from app.ml.model_loader import LoadedModel


def public_model_info(model: LoadedModel) -> dict:
    """Genuine, non-fabricated model metadata for API consumers."""
    md = model.metadata
    metrics = model.metrics
    test = metrics.get("test_metrics", {})
    return {
        "model_id": md.get("model_id"),
        "model_version": md.get("model_version"),
        "trained_at": md.get("trained_at"),
        "selected_model": md.get("selected_model"),
        "selection_reason": md.get("selection_reason"),
        "feature_schema_version": md.get("feature_schema_version"),
        "n_features": len(model.feature_schema.get("feature_names", [])),
        "probability_meaning": md.get("probability_meaning"),
        "classification_bands": md.get("classification_bands"),
        "uncertain_band": md.get("uncertain_band"),
        "dataset": md.get("dataset"),
        "training_config": md.get("training_config"),
        "test_metrics": test,
        "evaluation_available": bool(test),
        "evaluation_notes": metrics.get("evaluation_notes", []),
    }
