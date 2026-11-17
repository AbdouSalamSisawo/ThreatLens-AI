# Model artefacts

This directory holds the trained model artefacts exported by the research
notebook (`ml/notebooks/threatlens_phishing_url_detection.ipynb`, deployment
section). They are git-ignored, so only this README is committed.

Expected files:

- `phishing_model.joblib`  - the fitted scikit-learn pipeline
- `model_metadata.json`    - model id/version, dataset provenance, bands, config
- `metrics.json`           - genuine held-out evaluation report
- `feature_schema.json`    - feature schema version + ordered feature names

Validate a set before serving it:

    python scripts/validate_model.py

The API refuses to serve predictions if artefacts are missing, unloadable, or
built against a different feature schema. Downloaded serialised models are
treated as untrusted and never auto-loaded.
