"""
ThreatLens AI - model artefact validator.

One command that answers: "can this backend serve this model right now?"

    cd threatlens/backend
    python training/validate_model.py                  # validate ./artifacts
    python training/validate_model.py --artifacts-dir /path/to/artifacts

Run it after training, after dropping new artefacts into backend/artifacts/,
or before any deploy. Exit code 0 = all checks passed; 1 = at least one
check failed, with an actionable message.

The central check runs the SAME loader the API uses at startup
(app/ml/model_loader.py), so a pass here means the running API will serve
these artefacts, and a failure here means the API would refuse them - it
never falls back to a substitute model or mock predictions.

Warnings (model quality / documentation gaps) are reported but do not fail
the run; the loader's own contract is the only hard gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

REQUIRED_FILES = (
    "phishing_model.joblib",
    "model_metadata.json",
    "metrics.json",
    "feature_schema.json",
)

# Synthetic lexical fixtures only - the destination is never contacted; the
# validator exercises the exact feature-extraction path the API uses.
SMOKE_URLS = (
    "https://en.wikipedia.org/wiki/Phishing",
    "https://accounts.google.com/signin/v2/identifier",
    "http://198.51.100.7/secure-login-verify.example/paypal-account/update.php",
)

PASS, WARN, FAIL = "[PASS]", "[WARN]", "[FAIL]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ThreatLens model artefacts")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Artefact directory to validate (default: the backend/artifacts "
        "directory the API actually serves, taken from application settings).",
    )
    args = parser.parse_args()

    failures: list[str] = []

    def ok(message: str) -> None:
        print(f"{PASS} {message}")

    def warn(message: str) -> None:
        print(f"{WARN} {message}")

    def bad(message: str) -> None:
        failures.append(message)
        print(f"{FAIL} {message}")

    # -- 0. Resolve the artefact directory -----------------------------------
    if args.artifacts_dir is not None:
        artifacts = args.artifacts_dir
    else:
        from app.core.config import Settings

        artifacts = Settings().artifacts_dir
    print(f"Validating model artefacts in: {artifacts}\n")

    # -- 1. Presence ----------------------------------------------------------
    missing = [name for name in REQUIRED_FILES if not (artifacts / name).is_file()]
    if missing:
        bad("Missing artefact file(s): " + ", ".join(missing))
        print(
            "\n  Fix: copy the four artefact files produced by "
            "backend/training/train_model.py into this directory,\n"
            "  or retrain from scratch:\n"
            "      python training/prepare_dataset.py\n"
            "      python training/train_model.py\n"
            "  Full procedure: threatlens/MODEL_DROPIN.md\n"
        )
        return 1
    ok("All four artefact files are present")

    # -- 2. Load via the production loader (exact API startup path) -----------
    try:
        from app.core.config import Settings
        from app.ml.model_loader import load_model

        settings = Settings()
        if args.artifacts_dir is not None:
            settings.artifacts_dir = args.artifacts_dir
        loaded = load_model(settings)
    except Exception as exc:  # noqa: BLE001
        bad(f"Production loader refused the artefacts: {exc}")
        return 1
    ok("Production loader (app/ml/model_loader.py) accepted all artefacts")

    pipeline = loaded.pipeline

    # -- 3. Estimator interface ------------------------------------------------
    steps = getattr(pipeline, "steps", None)
    if steps:
        ok("Pipeline steps: " + " -> ".join(name for name, _ in steps))
    else:
        ok(f"Estimator type: {type(pipeline).__name__}")
    if not hasattr(pipeline, "predict_proba"):
        bad("Estimator has no predict_proba - the API requires probability output")
        return 1
    ok("predict_proba available (probability output required by the API)")

    # -- 4. Metadata / metrics completeness (quality warnings) -----------------
    metadata, metrics = loaded.metadata, loaded.metrics
    missing_meta = [
        key for key in ("model_id", "model_version", "selected_model") if key not in metadata
    ]
    if missing_meta:
        warn(f"model_metadata.json is missing key(s): {', '.join(missing_meta)} "
             "(model-info endpoint may show gaps)")
    else:
        ok(f"Model: {metadata['model_id']} v{metadata['model_version']} "
           f"({metadata['selected_model']})")
    test_metrics = metrics.get("test_metrics") or {}
    if test_metrics:
        headline = {
            key: test_metrics.get(key)
            for key in ("accuracy", "precision", "recall", "f1", "pr_auc")
        }
        ok("Held-out test metrics: "
           + ", ".join(f"{k}={v:.4f}" for k, v in headline.items() if v is not None))
    else:
        warn("metrics.json has no test_metrics block (dashboard transparency gaps)")
    if not metrics.get("domain_grouped_evaluation"):
        warn("metrics.json has no domain_grouped_evaluation "
             "(stricter generalisation check absent)")

    # -- 5. Smoke inference on the shared extractor path ------------------------
    import numpy as np
    import pandas as pd

    from app.services.feature_extractor import FEATURE_NAMES, extract_features

    try:
        print("\nSmoke inference (lexical features only - no URL is contacted):")
        for url in SMOKE_URLS:
            features = extract_features(url)
            X = pd.DataFrame(
                [[float(features[name]) for name in FEATURE_NAMES]],
                columns=list(FEATURE_NAMES),
            )
            proba = float(np.asarray(pipeline.predict_proba(X))[0][1])
            if not 0.0 <= proba <= 1.0:
                bad(f"predict_proba returned out-of-range value {proba} for {url}")
            print(f"  P(phishing)={proba:.4f}  {url}")
        ok("Smoke inference succeeded on the shared extractor path")
    except Exception as exc:  # noqa: BLE001
        bad(f"Smoke inference failed: {exc}")

    print()
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED - fix the [FAIL] items above and re-run.")
        return 1
    print("RESULT: all checks passed - this backend can serve these artefacts.")
    print("Restart the API (or redeploy) so a freshly copied artefact set is picked up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
