# Model artefacts

This directory holds the trained model artefacts produced ONLY by the
project's own training pipeline:

    python training/prepare_dataset.py
    python training/train_model.py

Expected files (all generated, never committed):

- `phishing_model.joblib`  - the fitted scikit-learn pipeline
- `model_metadata.json`    - model id/version, dataset provenance, bands, config
- `metrics.json`           - genuine held-out evaluation report
- `feature_schema.json`    - feature schema version + ordered feature names

The API refuses to serve predictions if artefacts are missing, unloadable, or
built against a different feature schema. Downloaded serialised models are
treated as untrusted and never auto-loaded.
