# Model Card — ThreatLens Phishing URL Classifier

| | |
|---|---|
| **Model ID** | `threatlens-phishing-url-classifier` |
| **Version** | 2.0.0 (UTC training timestamp in `backend/artifacts/model_metadata.json`) |
| **Model** | Extra Trees (`ExtraTreesClassifier`: 200 trees, `max_features="log2"`, `min_samples_leaf=2`, unlimited depth) |
| **Framework** | scikit-learn 1.6.1 (pinned in `backend/` and `ml/` requirements) |
| **Feature schema** | 1.1.0 — 33 lexical features |
| **Produced by** | [`ml/notebooks/threatlens_phishing_url_detection.ipynb`](../ml/notebooks/threatlens_phishing_url_detection.ipynb) |
| **Artefacts** | `backend/artifacts/phishing_model.joblib`, `model_metadata.json`, `metrics.json`, `feature_schema.json` |

All figures below come from the notebook. Its tables are in `ml/reports/tables/` and its figures in `ml/reports/figures/`.

## 1. Purpose

Estimate how closely a URL string matches the phishing patterns in the training corpus, as one input to an explainable screening workflow. It is an aid to a human decision, never an automated block/allow mechanism.

## 2. Intended users and prohibited uses

Campus awareness demos, security education, and users of the ThreatLens web application (students, staff, non-technical users).

**Prohibited:** automated blocking or gatekeeping of network traffic; legal or compliance decisions; declaring a URL confirmed malicious or confirmed safe; scanning URLs on behalf of third parties at scale.

## 3. Training data

- Hannousse & Yahiouche phishing-URL corpus ([arXiv:2010.12847](https://arxiv.org/abs/2010.12847), *Engineering Applications of Artificial Intelligence* 104, 2021), redistributed as `pirocheto/phishing-url` on Hugging Face, CC-BY-4.0. The snapshot was retrieved on 2026-10-29 and is checksum-verified (`ml/data/README.md`).
- 11,430 records loaded; 11,203 kept after removing 227 canonical duplicates. No records had invalid labels, unparsable URLs or label conflicts.
- 5,488 phishing / 5,715 legitimate, from 2,599 and 3,903 registrable domains respectively.
- Only the raw `url` and `status` fields are used. The dataset's 87 pre-computed features are discarded, because the API can only compute features from the URL.

## 4. Features

33 lexical features from the shared module `backend/app/services/feature_extractor.py`, the same code used at inference. The notebook groups them into five families: **length**, **character composition**, **host structure**, **scheme/path/query**, and **curated lexicons** (shorteners, high-abuse TLDs, urgency tokens, brand impersonation). The lexicon lists are documented in the module.

Schema 1.1.0 fixed the registrable-domain helper for deep subdomains under two-part suffixes (for example `*.co.uk`). Before the fix, brand impersonation on such hosts went undetected.

## 5. Methodology

1. **Domain-disjoint hold-out.** 20% of URLs (2,110) form a test set that shares no registrable domain with the development set (`StratifiedGroupKFold`, seed 42).
2. **Comparison.** Eight learners plus a majority baseline and a hand-written red-flag rule, compared under 5-fold domain-grouped CV on the development set. PR-AUC is the primary metric.
3. **Tuning.** Randomised search for logistic regression, random forest, extra trees and histogram gradient boosting, on the same grouped folds.
4. **Statistics.** 3 × 5 repeated grouped CV with Nadeau–Bengio corrected resampled *t*-tests.
5. **Selection rule** (fixed before tuning). Only models with exact per-URL explanations are eligible (logistic regression, random forest, extra trees). Pick the highest PR-AUC; prefer logistic regression only if it is within 0.01 and not significantly worse.
6. **Single test evaluation**, with 95% CIs from a domain-cluster bootstrap (2,000 replicates).
7. **Deployment fit.** The same configuration is refit on all 11,203 URLs.

## 6. Results

**Model selection (repeated grouped CV, PR-AUC):** gradient boosting 0.918 · **Extra Trees 0.909 (selected)** · Random Forest 0.908 · logistic regression 0.883. Gradient boosting's lead over Extra Trees (0.009) is not significant (*p* = 0.09), so the cost of requiring exact explanations is negligible. Extra Trees and Random Forest are statistically tied.

**Held-out test set: 2,110 URLs from unseen domains, threshold 0.5**

| Metric | Value | 95% CI |
|---|---|---|
| PR-AUC | 0.928 | 0.901–0.949 |
| ROC-AUC | 0.931 | 0.910–0.948 |
| Accuracy | 0.857 | 0.823–0.887 |
| Precision | 0.894 | 0.857–0.923 |
| Recall | 0.771 | 0.719–0.816 |
| Specificity | 0.926 | 0.897–0.948 |
| F1 | 0.828 | 0.789–0.861 |
| MCC | 0.712 | 0.651–0.765 |
| Confusion matrix | TN 1,083 · FP 86 · FN 216 · TP 725 | |

**Generalisation checks**

| Check | Result | Interpretation |
|---|---|---|
| Random 5-fold split instead of domain-grouped | PR-AUC +0.040 | Random splits overstate performance through domain memorisation |
| Dataset's official train/test split | PR-AUC +0.037; 49% of its test URLs share a domain with training | The official split leaks domains too |
| OpenPhish feed, 300 URLs not in the corpus | 78.7% flagged (deployed model) | Recall carries over to a later, independent feed |
| Majestic top 1,000 domains (`https://<domain>`) | 3.1% flagged (deployed model) | Mostly URL shorteners and Outlook login hosts |

## 7. Output semantics

- `predict_proba` gives an **estimated model probability** for the phishing class. It is not calibrated (ECE 0.104) and is not a measured probability of criminal activity.
- Bands: `likely_benign` < 0.50 · `suspicious` 0.50–0.80 · `high_risk` ≥ 0.80 · *uncertain* flag at 0.35–0.65.
- Observed phishing rate per band on the test set: high risk 98.6%, suspicious 78.7%, **likely benign 16.6%**. "Likely benign" is not "safe".
- The uncertain flag fires on 22% of test URLs; accuracy is 0.62 inside the band and 0.92 outside.
- Risk score = round(probability × 100). It is a display of the model output, not a risk measurement.

## 8. Explanations

Exact decision-path decomposition (the treeinterpreter method): each tree's change in phishing probability along the URL's path is attributed to the split feature, then averaged over the 200 trees. On 500 test URLs, bias plus contributions reproduced `predict_proba` with a maximum absolute error of 0.0. Rule-derived "observed characteristics" are always shown separately from model contributions.

Isotonic calibration would reduce ECE to 0.044, but it is not applied, because a non-additive calibration map would break exact explanations.

## 9. Known limitations and failure modes

- **Lexical only.** Phishing on short, clean-looking URLs is missed most often: FNR is 36% in the shortest length quartile, against 23% overall.
- **One corpus from about 2020, balanced 50/50.** Real traffic is mostly legitimate, so precision in deployment will be lower.
- **URL shorteners and genuine login pages** of popular services score as phishing-like. Outlook login hosts are flagged in the Majestic probe, and Google's real sign-in URL (`accounts.google.com/signin/...`) scores 0.64 ("suspicious") in the validator smoke test. Login vocabulary in a URL is exactly what phishing imitates.
- **Rare red flags.** Punycode, non-standard ports, executable downloads and credentials-in-URL almost never occur in the corpus, so the model has barely learned them.
- **Approximate domains.** Registrable domains use a small suffix list, not the full Public Suffix List.
- **No adversarial testing.** Attackers can adapt URLs to evade lexical models.

## 10. Versioning and integrity

- The feature schema version (1.1.0) is stored in the artefacts and checked against the code. The API refuses to serve on a mismatch.
- Only artefacts produced by this repository's notebook are loaded. Downloaded serialised models are treated as untrusted.
- Retraining: run the notebook top to bottom. Its deployment section writes all four artefacts and runs `backend/scripts/validate_model.py`.
