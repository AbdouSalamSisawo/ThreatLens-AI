# AI and Data Declaration — ThreatLens AI

This document discloses, honestly and completely, every external data source, AI service, model and library used by the ThreatLens AI project, and the roles they play. It is written for the MMC Upstart 2026 Catalyst AI declaration. Placeholders are marked explicitly where information is not yet established.

---

## 1. AI tools used during development

| Tool | Role | Disclosure |
|---|---|---|
| Z.ai GLM coding assistant | Assisted with writing, refactoring and debugging the application code, training scripts, tests and documentation during development | The running application contains **no** development-time AI component; all shipped functionality is ordinary code + a locally trained scikit-learn model |

**Generative AI at runtime:** **None.** No LLM or generative service is called during any user-facing operation. All explanations are deterministic, computed from the trained model and extracted features.

## 2. Model providers and identifiers

| Component | Provider / origin | Identifier |
|---|---|---|
| URL classifier (the only ML model in the product) | Trained locally with scikit-learn from the project's own research notebook (`ml/notebooks/threatlens_phishing_url_detection.ipynb`) | `threatlens-phishing-url-classifier` v1.0.0 |
| External hosted AI APIs | **None used.** No OpenAI/Hugging Face/other inference APIs are called | — |

## 3. Training dataset sources

| | |
|---|---|
| **Dataset** | "TabNetone" phishing-URL corpus (Hugging Face id: `pirocheto/phishing-url`) |
| **Origin** | Compiled by A. Hannousse & S. Yahiouche for arXiv:2010.12847 (*"Phishing URL detection: a real-world assessment"*) from public phishing feeds and legitimate crawl sources |
| **Source URL** | https://huggingface.co/datasets/pirocheto/phishing-url (files `data/train.parquet`, `data/test.parquet`) |
| **Retrieval date** | 2026-10-29 |
| **Licence / usage terms** | CC-BY-4.0 — use with attribution; this declaration and the README provide it |
| **Fields used** | `url` (raw string), `status` ("phishing"/"legitimate"). All 87 pre-computed feature columns were **discarded** — ThreatLens computes its own features from raw URLs with one shared extractor |
| **Labels** | Binary: 1 = phishing, 0 = legitimate; mapped verbatim, no relabelling heuristics |
| **Preprocessing** | Schema validation → label normalisation → invalid/oversized URL removal → label-conflict detection → exact + normalised de-duplication (227 removed) → class-distribution report → leakage-aware split. Full report: `data/processed/phishing_clean.report.json` |
| **Class balance** | 5,488 phishing / 5,715 legitimate (approx. balanced; no resampling applied — documented) |

### Auxiliary (evaluation-only) sources — never used for training

| Source | URL | Retrieved | Licence | Role |
|---|---|---|---|---|
| OpenPhish free feed (300 URLs) | https://openphish.com/feed.txt | 2026-10-29 | OpenPhish Community Terms (non-commercial use with attribution) | Out-of-source recall proxy on fresh phishing |
| Majestic Million (top 1,000 domains) | https://downloads.majestic.com/majestic_million.csv | 2026-10-29 | Free public download with attribution | Out-of-source false-positive probe on popular legitimate domains |

## 4. Open-source libraries

| Layer | Libraries |
|---|---|
| Frontend | react, react-dom, react-router-dom, recharts, lucide-react, framer-motion, tailwindcss, vite, typescript (all MIT-style licences) |
| Backend | fastapi, uvicorn, pydantic, pydantic-settings (MIT/BSD); scikit-learn, pandas, numpy, joblib (BSD); sqlite3 (Python stdlib) |
| Testing | pytest, pytest-asyncio, FastAPI TestClient, httpx |

## 5. Optional external APIs

**None integrated.** The architecture defines a reputation-provider seam (`app/services/reputation_service.py`) for future Google Safe Browsing / PhishTank integration. In the current build the scan response reports threat-intelligence status as `unavailable` with an explanatory message — a lookup is never simulated.

## 6. Where machine learning is used

- **One place only:** `POST /api/scan` → the trained Random Forest assigns an estimated probability to the phishing class for the submitted URL's feature vector.

## 7. Where deterministic rules are used (no ML)

- Input validation and scheme allow-listing.
- URL parsing and all 33 lexical feature computations.
- **Observed characteristics** in the explanation layer (e.g. "hostname is an IP address") — derived directly from feature values with documented thresholds.
- Reference lists (shorteners, high-abuse TLDs, security/urgency vocabulary, brand tokens) — transparent, documented, used as *signals*; they never decide a verdict alone.
- Classification-band mapping (0.50/0.80 thresholds + 0.35–0.65 uncertainty flag) and the risk-score formula (probability × 100).
- Safety recommendations (rule-selected per band and per observed signal).

## 8. Generative AI usage

**Not used**, at runtime or in the training pipeline. If an optional explanation assistant is added later it must: stay behind the local model, receive minimum necessary data, never override the classifier, be labelled as AI-generated, and have a deterministic fallback — per the project's design rules (documented in the repository).

## 9. Privacy and security measures

- The submitted destination is never fetched (no HTTP client in the scan path).
- Server-side validation, request-size and URL-length limits, scheme allow-listing.
- In-process sliding-window rate limiting (30 scans/min default).
- Consistent error envelope; no stack traces in production responses; security headers set.
- Optional history: `disabled` (nothing stored) / `memory` (RAM only) / `sqlite` (local file, capped at 500, user-deletable). No cookies, credentials or page content are ever stored.
- Logs redact URLs to scheme + host. Secrets are environment-only (`.env.example` contains placeholders).

## 10. Bias and fairness considerations

- The corpus's benign class skews towards well-known websites; legitimate sites with unusual structures (long subdomains, unusual TLDs, IP hosting by small providers) are more likely to be flagged. This is disclosed on the Model Performance page.
- Phishing examples reflect the collection period of the public corpus; novel campaigns may differ.
- Metrics are reported per failure mode (FP vs FN) rather than as a single score, because the harms are asymmetric and affect different users.
- Out-of-source probes are published to expose generalisation gaps rather than hide them (79.3% recall proxy on fresh OpenPhish data vs 82.1% on the held-out corpus test set).

## 11. Known limitations

- URL-only analysis; no page content, behaviour or reputation signals.
- Uncalibrated probabilities; bands are decision aids, not measured risk.
- Single-user prototype: no accounts, in-process rate limiting, local history only.
- Model version 1.0.0 is a static snapshot; retraining required to track evolving phishing.

## 12. Human oversight

Every result is presented with its evidence, uncertainty flag and limitations; the UI never presents a verdict as a guaranteed truth. Users are directed to verify domains through independent official sources and to report suspected phishing through institutional channels. The deployment operator can disable storage, inspect every stored record, and delete any or all history.

## 13. Unestablished information (explicit placeholders)

- Final team member names and contribution split: *to be added by the team*.
- Institutional review/approval status of the project: *not obtained; none claimed*.
- Any future provider credentials (Safe Browsing key, etc.): *not configured; none exist*.
