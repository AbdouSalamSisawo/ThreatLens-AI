# Model drop-in guide — ThreatLens AI

The application is production-complete **except for one input: the trained
model artefacts**. This guide is the single procedure for putting a model in —
and everything around it is already built and verified: authentication
(Supabase), per-user scan history with Row Level Security, the inference and
explanation pipeline, rate limiting, tests, and deployment configuration.

> **Current state:** the repository ships **without** model artefacts
> (`backend/artifacts/` contains only a README and is git-ignored otherwise).
> Until you drop a model in, the API runs but `POST /api/scan` returns an
> honest `503 model_unavailable`. Follow section 2 to supply your model, or
> section 4 to train one with the included pipeline.

---

## 1. What "the model" is

Exactly **four files** in `backend/artifacts/`:

| File | Role |
|---|---|
| `phishing_model.joblib` | The trained scikit-learn estimator (serialised with joblib) |
| `feature_schema.json` | Feature schema version + ordered feature-name list (33 lexical features) |
| `model_metadata.json` | Model ID, version, selection record, dataset provenance |
| `metrics.json` | Held-out test metrics, domain-grouped evaluation, out-of-source checks |

The model file alone is not enough — the loader reads all four, and the
feature schema is what guarantees the artefact matches the code.

## 2. The one-step drop-in

From `backend/`:

```bash
# 1. Copy your four artefact files into backend/artifacts/ (overwrite)
cp /path/to/your/artifacts/* artifacts/

# 2. Validate — one command, same checks the API runs at startup + smoke inference
python scripts/validate_model.py

# 3. Restart the API (artefacts are loaded once at startup)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`scripts/validate_model.py` exits `0` only when:

- all four files are present;
- **the production loader accepts them** (this is the exact
  `app/ml/model_loader.py` code path — schema version and feature-name list
  must match the deployed feature extractor, or the API would refuse to serve);
- the estimator exposes `predict_proba`;
- a smoke inference runs end-to-end on the shared feature-extractor path.

Any failure exits `1` with the specific reason and the fix. Quality warnings
(missing metrics blocks) are reported but do not block serving.

## 3. What the API does while the model is absent or broken

It **never fakes a prediction**. If any artefact is missing, corrupt, or
schema-incompatible, `POST /api/scan` returns

```
HTTP 503  {"error": {"code": "model_unavailable", "message": "..."}}
```

and `/api/model-info` reports the same state — the frontend shows an honest
"model unavailable" error panel. This behaviour is covered by automated tests
(`test_scan_returns_503_no_fallback`). There is no substitute model, no random
output, no mock.

## 4. Training your own model from scratch

Training is done in the research notebook, not in standalone scripts:

```bash
pip install -r ml/requirements.txt
jupyter lab ml/notebooks/threatlens_phishing_url_detection.ipynb   # Run All
```

The notebook downloads the data from its original sources (checksum-verified,
see `ml/data/README.md`), cleans it, compares and tunes candidate models with
domain-grouped cross-validation, evaluates the selected model once on a
domain-disjoint test set, and, in its deployment section, writes the four
artefacts into `backend/artifacts/` and runs `scripts/validate_model.py`
automatically. It can also be run on Google Colab (see `ml/README.md`).

The notebook imports the **same shared feature extractor** as the API
(`app/services/feature_extractor.py`), so train/serve skew is impossible by
construction; the schema-version check in the loader is the second guard.

## 5. Rollback

Keep a copy of the previous artefact set before overwriting:

```bash
cp -r backend/artifacts ~/artifacts-backup-$(date +%F)
```

Restoring is the reverse: copy the backup's four files back into
`backend/artifacts/`, run `python scripts/validate_model.py`, restart the API.

## 6. Security rules for artefacts

- Only load artefacts **produced by this project's training pipeline**
  (the research notebook in `ml/notebooks/`). `app/ml/model_loader.py` documents this
  policy: downloaded serialised models are treated as untrusted and never
  auto-loaded.
- A model file from an unknown source can execute arbitrary code when
  deserialised (pickle). Validate the origin before dropping it in.
- The four artefact files are the only ML inputs — no API keys, no external
  model service, no network calls in the inference path.
