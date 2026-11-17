# ML research workspace

This folder holds the complete, reproducible workflow behind the ThreatLens phishing-URL classifier: data acquisition, cleaning, exploratory analysis, model comparison, tuning, evaluation, interpretability, and deployment into the backend. It is written so the results can be reported in a research paper.

```
ml/
├── notebooks/
│   └── threatlens_phishing_url_detection.ipynb   the full study (run top to bottom)
├── data/                 downloaded by the notebook — not committed (see data/README.md)
│   ├── raw/              original source files, checksum-verified
│   └── processed/        cleaned corpus produced by the notebook
├── reports/
│   ├── figures/          every figure in the notebook, as PNG for the paper
│   └── tables/           every results table, as CSV
└── requirements.txt      pinned environment
```

## Workflow

| § | Stage | Output |
|---|---|---|
| 1 | Environment and reproducibility settings | package versions, seed |
| 2 | Data acquisition from the original sources + SHA-256 verification | `data/raw/`, provenance table |
| 3 | Cleaning: label normalisation, invalid URLs, label conflicts, de-duplication | `data/processed/`, cleaning-flow table |
| 4 | Exploratory data analysis | class balance, URL structure, TLDs, domain concentration |
| 5 | Feature extraction with the backend's shared extractor + univariate analysis | effect sizes, mutual information, correlation |
| 6 | Experimental protocol: domain-disjoint test split, grouped cross-validation | split audit (zero domain overlap) |
| 7 | Baselines and model comparison | 8 learners + 2 baselines under grouped CV |
| 8 | Hyperparameter tuning | tuned configurations |
| 9 | Statistical comparison and pre-registered model selection | corrected resampled *t*-tests |
| 10 | Held-out test evaluation with bootstrap confidence intervals | final metrics, ROC/PR curves |
| 11 | Threshold, risk-band and calibration analysis | reliability diagram, band validation |
| 12 | Leakage study: random vs domain-disjoint splits | inflation estimate |
| 13 | Out-of-source generalisation (OpenPhish, Majestic) | recall / false-positive probes |
| 14 | Interpretability: permutation importance, partial dependence, exact local explanations | feature-importance figures |
| 15 | Ablation and learning curve | feature-group contributions |
| 16 | Error analysis | error rates by URL segment |
| 17 | Computational cost | training time, latency, model size |
| 18 | Deployment into `backend/artifacts/` + automated validation | the four artefact files |
| 19 | Findings, limitations, threats to validity | — |

## Running it

### Locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ml/requirements.txt
jupyter lab ml/notebooks/threatlens_phishing_url_detection.ipynb
```

Run all cells. A full run takes about 10–20 minutes on an 8-core laptop. The notebook downloads any missing data on first run, so it needs internet access then.

### Google Colab

Open the notebook in Colab and run all cells. The first code cell detects Colab, clones this repository and installs `ml/requirements.txt`. If you change the pinned scikit-learn version, the exported model will not load in the backend.

## Design principles

- **One feature extractor.** The notebook imports `backend/app/services/feature_extractor.py`, so the features used in training are exactly the ones served in production.
- **Domain-disjoint evaluation.** No registrable domain appears in both training and test data. Random splits leak domains and inflate scores; §12 measures by how much.
- **The test set is used once.** All model selection happens with cross-validation on the development set.
- **Selection is pre-registered.** The rule for choosing the deployed model is stated before the results are seen (§9).
- **Explainability is a requirement.** The deployed model must support the backend's exact per-URL explanations (tree-path or coefficient decomposition).
- **Safe display.** Any phishing URL shown in the notebook is defanged (`hxxp://example[.]com`).
