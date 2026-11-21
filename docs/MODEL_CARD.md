# Model Card — ThreatLens Phishing URL Classifier

| | |
|---|---|
| **Model ID** | `threatlens-phishing-url-classifier` |
| **Version** | 3.0.0 (UTC training timestamp in `backend/artifacts/model_metadata.json`) |
| **Model** | Histogram gradient boosting (`HistGradientBoostingClassifier`): 200 trees, learning rate 0.034, up to 63 leaves and depth 10 per tree, `min_samples_leaf=5`, L2 regularisation 0.84 |
| **Framework** | scikit-learn 1.6.1 (pinned in `backend/` and `ml/` requirements) |
| **Feature schema** | 2.0.0 — 57 lexical features computed on a canonical form of the URL |
| **Size / speed** | 0.6 MB; about 15 ms to score and about 25 ms to explain a URL on one CPU core |
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
- **Known artefact:** 67% of legitimate but only 21% of phishing URLs start with `www.` (a result of crawling). Canonical features neutralise it (§6).

## 4. Features

57 lexical features from the shared module `backend/app/services/feature_extractor.py`, the same code used at inference. Six families: **length**, **character composition**, **host structure** (including how random the main domain name looks and domain endings hidden in subdomains), **scheme/path/query** (including embedded `http`, page extensions and home-page detection), **word statistics**, and **curated lexicons** (shorteners, high-abuse TLDs, urgency tokens, brand impersonation).

Every feature is computed on a **canonical URL**: scheme and host lower-cased, one leading `www.` removed, and an empty path written as `/`. These edits never change where a link leads, so they cannot change a prediction.

## 5. Methodology

1. **Domain-disjoint hold-out.** 20% of URLs (2,110 from 1,288 domains) form a test set that shares no registrable domain with the development set (`StratifiedGroupKFold`, seed 42).
2. **Comparison.** Eight learners plus a majority baseline and a hand-written red-flag rule, compared under 5-fold domain-grouped CV on the development set. PR-AUC is the primary metric.
3. **Tuning.** Randomised search for logistic regression (30 configurations), random forest and extra trees (40 each) and gradient boosting (60), on the same grouped folds.
4. **Statistics.** 3 × 5 repeated grouped CV with Nadeau–Bengio corrected resampled *t*-tests.
5. **Selection rule** (fixed before tuning). Only models with exact per-URL explanations are eligible: all four tuned families since gradient boosting gained an exact decomposition. Pick the highest PR-AUC; prefer logistic regression only if it is within 0.01 and not significantly worse.
6. **Single test evaluation**, with 95% CIs from a domain-cluster bootstrap (2,000 replicates).
7. **Deployment fit.** The same configuration is refit on all 11,203 URLs.

## 6. Results

**Model selection (repeated grouped CV, PR-AUC):** **gradient boosting 0.932 (selected)** · random forest 0.925 · extra trees 0.920 · logistic regression 0.901. Gradient boosting is significantly better than each of the others (*p* = 0.047, 0.015, 0.006). Exact explainability costs nothing.

**Held-out test set: 2,110 URLs from unseen domains, threshold 0.5**

| Metric | Value | 95% CI |
|---|---|---|
| PR-AUC | 0.945 | 0.924–0.962 |
| ROC-AUC | 0.950 | 0.934–0.964 |
| Accuracy | 0.887 | 0.861–0.911 |
| Precision | 0.882 | 0.844–0.916 |
| Recall | 0.861 | 0.829–0.891 |
| Specificity | 0.908 | 0.872–0.938 |
| F1 | 0.871 | 0.843–0.898 |
| MCC | 0.770 | 0.719–0.814 |
| Confusion matrix | TN 1,061 · FP 108 · FN 131 · TP 810 | |

**Robustness and generalisation**

| Check | Result | Interpretation |
|---|---|---|
| Add/remove `www.` (validation URLs) | **0%** of decisions flip (24% with the schema-1 features on raw URLs) | Canonical features remove a free evasion route |
| Add/remove trailing slash on home pages | **0%** flip (11–19% on raw URLs) | Same |
| Random 5-fold split instead of domain-grouped | PR-AUC +0.032 | Random splits overstate performance through domain memorisation |
| Dataset's official train/test split | PR-AUC +0.031; 49% of its test URLs share a domain with training | The official split leaks domains too |
| OpenPhish feed, 300 URLs not in the corpus | 90.0% flagged (deployed model) | Recall carries over to a later, independent feed |
| Majestic top 1,000 domains (`https://<domain>`) | 1.3% flagged (deployed model) | Mostly genuine login and content hosts of large platforms |

**Previous versions for comparison:** v2.0.0 (Extra Trees, 33 features) scored test PR-AUC 0.928, recall 0.771, OpenPhish 79% and Majestic 3.1%.

## 7. Output semantics

- `predict_proba` gives an **estimated model probability** for the phishing class. It is well calibrated on the test set (Brier 0.084, ECE 0.025), but it is not a measured probability of criminal activity.
- Bands: `likely_benign` < 0.50 · `suspicious` 0.50–0.80 · `high_risk` ≥ 0.80 · *uncertain* flag at 0.35–0.65.
- Observed phishing rate per band on the test set: high risk 95.3%, suspicious 70.7%, **likely benign 11.0%**. "Likely benign" is not "safe".
- The uncertain flag fires on 11.2% of test URLs; accuracy is 0.57 inside the band and 0.93 outside.
- Risk score = round(probability × 100). It is a display of the model output, not a risk measurement.

## 8. Explanations

Exact decision-path decomposition in **log-odds**. Every tree node is given its expected output, the training-sample-weighted mean of the leaf values below it. Along the path a URL takes through each tree, each change in expected output is attributed to the feature that made the split, and the changes are summed over all 200 trees. The bias is the average log-odds of the training data. Then sigmoid(bias + Σ contributions) equals `predict_proba`: on 500 test URLs the maximum error was 0.0, and each feature's contribution averages to zero over the training data.

The backend shows the decomposition only when it reproduces the model's probability on that request. Rule-derived "observed characteristics" are always shown separately from model contributions.

## 9. Known limitations and failure modes

- **Short look-alike domains.** Bare domains such as `google-apps[.]cz` carry little lexical evidence. FNR is 41% in the shortest length quartile, against 14% overall. A URL-only model cannot tell which brand a short domain imitates.
- **Genuine login pages of large platforms** score as phishing-like: Outlook web hosts in the Majestic probe, and Google's real sign-in URL (`accounts.google.com/signin/...`, 0.96) in the validator smoke test. Login vocabulary on an unfamiliar-looking host is exactly what phishing imitates.
- **One corpus from about 2020, balanced 50/50.** Real traffic is mostly legitimate, so precision in deployment will be lower.
- **Rare red flags.** Punycode, non-standard ports, executable downloads and credentials-in-URL almost never occur in the corpus, so the model has barely learned them.
- **Approximate domains.** Registrable domains use a small suffix list, not the full Public Suffix List.
- **Limited adversarial testing.** Only three meaning-preserving edits were tested; attackers can adapt URLs in other ways.
- **Test-set reuse.** Feature schema 2.0.0 was designed after an earlier iteration of the study had seen the test set (guided by development-set experiments, not test scores).

## 10. Versioning and integrity

- The feature schema version (2.0.0) is stored in the artefacts and checked against the code. The API refuses to serve on a mismatch, so models built on schema 1.x are refused.
- Only artefacts produced by this repository's notebook are loaded. Downloaded serialised models are treated as untrusted.
- Retraining: run the notebook top to bottom. Its deployment section writes all four artefacts and runs `backend/scripts/validate_model.py`.
