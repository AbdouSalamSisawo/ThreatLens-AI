"""
ML pipeline tests: train->save->reload->infer with the SHARED feature schema.
Structural and integration assertions only - no invented per-URL predictions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.model_loader import ModelNotAvailableError, load_model  # noqa: E402
from app.services.explanation_service import compute_model_evidence  # noqa: E402
from app.services.feature_extractor import (  # noqa: E402
    FEATURE_NAMES,
    feature_vector,
)
from tests.conftest import BENIGN_FIXTURE_URLS, PHISHING_FIXTURE_URLS  # noqa: E402


def _frame(urls):
    return pd.DataFrame([dict(zip(FEATURE_NAMES, feature_vector(u))) for u in urls])


def test_model_reloads_from_artifact(trained_pipeline):
    artifacts, _pipe, _, _ = trained_pipeline
    loaded = joblib.load(artifacts / "phishing_model.joblib")
    assert hasattr(loaded, "predict_proba")


def test_feature_schema_shared_between_train_and_inference(trained_pipeline):
    artifacts, pipe, urls, _labels = trained_pipeline
    loaded = joblib.load(artifacts / "phishing_model.joblib")
    X = _frame(urls)
    assert X.shape[1] == len(FEATURE_NAMES)
    # Same features -> same probabilities from reloaded pipeline
    p1 = pipe.predict_proba(X)[:, 1]
    p2 = loaded.predict_proba(X)[:, 1]
    assert np.allclose(p1, p2)


def test_predictions_are_valid_probabilities(trained_pipeline):
    _, pipe, urls, _ = trained_pipeline
    proba = pipe.predict_proba(_frame(urls))[:, 1]
    assert ((proba >= 0) & (proba <= 1)).all()
    # The fixture is clearly-labelled and structurally separated: the model
    # must at minimum separate the two classes it was trained on.
    benign_mean = proba[: len(BENIGN_FIXTURE_URLS)].mean()
    phish_mean = proba[len(BENIGN_FIXTURE_URLS):].mean()
    assert phish_mean > benign_mean
    assert phish_mean > 0.7
    assert benign_mean < 0.4


def test_structural_sanity_ordering(trained_pipeline):
    """
    Structural check (not a claim about real URLs): a fixture URL with an IP
    host, credentials and login tokens must outscore a plain https fixture.
    """
    _, pipe, _, _ = trained_pipeline
    blatant = "http://user:pass@198.51.100.66/paypal/login/verify/account/webscr"
    plain = "https://kernel.org/pub/linux/kernel/"
    p_blatant = pipe.predict_proba(_frame([blatant]))[0][1]
    p_plain = pipe.predict_proba(_frame([plain]))[0][1]
    assert p_blatant > p_plain


def test_tree_path_evidence_is_exact(trained_pipeline):
    """The Random Forest decomposition must reproduce predict_proba exactly."""
    _, pipe, urls, _ = trained_pipeline
    X = _frame(urls)
    for i in range(0, len(urls), 5):
        feats = {name: float(X.iloc[i][name]) for name in FEATURE_NAMES}
        evidence = compute_model_evidence(pipe, feats)
        assert evidence["method"] == "tree_path"
        check = evidence["probability_check"]
        assert check is not None and check["exact"] is True


def test_missing_artifacts_raise_clear_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    class S:
        artifacts_dir = empty

    with pytest.raises(ModelNotAvailableError) as exc:
        load_model(S())  # type: ignore[arg-type]
    assert "validate_model.py" in str(exc.value)


def test_schema_mismatch_rejected(trained_pipeline):
    artifacts, *_ = trained_pipeline
    import json

    schema_path = artifacts / "feature_schema.json"
    original = json.loads(schema_path.read_text())
    tampered = dict(original)
    tampered["schema_version"] = "9.9.9"
    schema_path.write_text(json.dumps(tampered))

    class S:
        artifacts_dir = artifacts

    with pytest.raises(ModelNotAvailableError) as exc:
        load_model(S())  # type: ignore[arg-type]
    assert "schema mismatch" in str(exc.value).lower()

    schema_path.write_text(json.dumps(original))  # restore for other tests
