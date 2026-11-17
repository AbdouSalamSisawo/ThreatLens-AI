# Model Card — ThreatLens Phishing URL Classifier

> **Reference model.** The figures below describe the reference model (v1.0.0) produced during development. Model artefacts are no longer committed to the repository — when you supply your own model (see [MODEL_DROPIN.md](MODEL_DROPIN.md)), regenerate these figures from its `metrics.json`; the in-app *Model Performance* page always reads the live artefacts.

| | |
|---|---|
| **Model ID** | `threatlens-phishing-url-classifier` |
| **Version** | 1.0.0 |
| **Trained** | 2026-10-29 (UTC timestamp in `backend/artifacts/model_metadata.json`) |
| **Framework** | scikit-learn 1.5.2 (RandomForestClassifier) |
| **Artefacts** | `backend/artifacts/phishing_model.joblib`, `model_metadata.json`, `metrics.json`, `feature_schema.json` |

## 1. Purpose

Estimate the likelihood that a URL string matches phishing patterns seen in the training corpus, and support an explainable screening workflow. The model is one input to a human decision — never an automated block/allow mechanism.

## 2. Intended users

Campus awareness demos, security-education contexts, and the ThreatLens web prototype's users (students, staff, non-technical users). **Prohibited uses:** automated blocking/gatekeeping of network traffic; legal or compliance decisions; claiming a URL is confirmed malicious or confirmed safe; scanning URLs on behalf of third parties at scale.

## 3. Training data

- Public "TabNetone" corpus (`pirocheto/phishing-url`, CC-BY-4.0, arXiv:2010.12847), retrieved 2026-10-29.
- 11,430 raw records loaded → 11,203 retained after validation, label-conflict checks and de-duplication (227 duplicates removed; 0 conflicts; 0 invalid).
- Labels: 5,488 phishing (1) / 5,715 legitimate (0).
- Only raw `url` + `status` used; all 87 pre-computed dataset features discarded (the model uses ThreatLens' own 33-feature schema).

## 4. Feature engineering

33 lexical features extracted by the shared, versioned module (`app/services/feature_extractor.py`, schema v1.0.0), grouped as:

- **Lengths/counts:** URL, hostname, path, query lengths; dots, hyphens, underscores, digits, percent-encodings, query params, ampersands, '@', path depth, double-slash-in-path.
- **Ratios:** digit ratios (URL, hostname).
- **Structure flags:** IP-address hostname (IPv4/IPv6), non-standard port, HTTPS scheme (as submitted), user:password@ credentials, shortener domain, punycode labels, high-abuse TLD, executable extension in path, long hostname (≥30 chars), long hexadecimal hostname labels.
- **Content signals:** count of generic security/urgency tokens (documented list), brand token outside the registrable domain (impersonation heuristic), Shannon entropy of hostname.

All lists are documented in the module. Features are signals for the model — individually they never decide an outcome.

## 5. Training methodology

1. Stratified 60/20/20 train/validation/test split, fixed seed 42 (train 6,721 / val 2,241 / test 2,241).
2. Candidates trained on the train split: Logistic Regression (StandardScaler pipeline), Random Forest (300 trees, min_samples_leaf=2), Hist Gradient Boosting (300 iters, lr=0.1), majority-class baseline.
3. Compared on **validation** PR-AUC (primary), F1, accuracy.
4. **Selection rule:** highest validation PR-AUC; if Logistic Regression is within 0.01 PR-AUC of the best, prefer Logistic Regression for exact per-instance coefficient explanations. Result: Random Forest won by margin (0.9472 vs 0.9153), so Random Forest was selected.
5. Selected model refit on train+validation; **single** evaluation on the held-out test set.
6. Class imbalance: none required (≈balanced); documented.

## 6. Evaluation methodology & actual metrics

**Held-out test set (used once):**

| Metric | Value |
|---|---|
| Accuracy | 0.8626 |
| Precision | 0.8903 |
| Recall | 0.8206 |
| F1 | 0.8540 |
| ROC-AUC | 0.9395 |
| PR-AUC | 0.9423 |
| Confusion matrix | TN 1032 · FP 111 · FN 197 · TP 901 |

**Why both error types matter:** false negatives (197) leave users exposed — a false sense of safety; false positives (111) harm legitimate sites and erode trust in the tool. Both are published and neither is tuned away silently.

**Stricter honesty checks:**

| Check | Result | Interpretation |
|---|---|---|
| Domain-grouped split (no registrable domain crosses train/holdout) | acc 0.8248, recall 0.7529, PR-AUC 0.8984 | Drop vs random split shows some domain memorisation in the random-split numbers |
| OpenPhish feed, 300 fresh URLs (out-of-time, out-of-source) | 238 flagged → 0.7933 recall proxy | Fresh phishing is caught somewhat less often than the corpus test suggests |
| Majestic top-1,000 domains (constructed HTTPS home-page URLs) | 23 flagged → 0.023 FPR | Popular legitimate sites are rarely flagged |

## 7. Output semantics

- `predict_proba` → **estimated model probability** for the phishing class. **Uncalibrated** — not a measured risk of criminality.
- Classification bands (documented): `likely_benign` < 0.50 · `suspicious` 0.50–0.80 · `high_risk` ≥ 0.80 · uncertainty flag 0.35–0.65.
- Risk score = round(probability × 100), a UI representation of the model output — explicitly not the probability of actual malicious activity.

## 8. Explanation capability

Exact per-instance decision-path decomposition (treeinterpreter method) attributes each tree's probability change to the split feature, averaged over all 300 trees; verified by tests to reproduce `predict_proba` within 1e-6. Contributions are reported with direction (toward phishing / toward benign) and the exactness check is exposed to the UI. Rule-derived "observed characteristics" are always clearly separated from model-derived contributions.

## 9. Known limitations & failure modes

- Lexical-only: phishing that mimics benign URL structure can pass; benign long/odd URLs can be flagged.
- Dataset bias: benign class skews to popular domains; less-famous legitimate sites with unusual structures are over-flagged risk.
- Static snapshot: phishing kits evolve; retraining needed (no drift monitoring yet).
- Random-split metrics overstate real-world generalisation (see grouped-split check).
- Uncalibrated probabilities; thresholds chosen as documented aids, not optimised operating points.

## 10. Model versioning & integrity

- Feature schema version 1.0.0 is embedded in artefacts and in code; the API refuses to serve on mismatch (train/serve skew guard).
- Only artefacts produced by this repository's `training/train_model.py` are loaded; downloaded serialised models are treated as untrusted.
- Retraining: `python training/prepare_dataset.py && python training/train_model.py` regenerates artefacts atomically with fresh metadata and metrics.
