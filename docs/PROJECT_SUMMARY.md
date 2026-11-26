# ThreatLens AI — Project Summary

**Competition:** MMC Upstart 2026 Catalyst: Igniting Future Innovation
**Institution:** Albukhary International University (AIU), School of Computing & Informatics
**Category:** Cybersecurity, trustworthy AI, digital integrity, applied machine learning

---

## Project title

**ThreatLens AI — Explainable Phishing URL Detection**

## Problem addressed

Phishing attacks rely on deceptive URLs to harvest credentials and sensitive information. Students and other non-technical internet users — frequent targets of fake "bursary", "account blocked" and "scholarship" messages — have no practical way to inspect a link before interacting with it, and existing tools either provide verdicts without reasoning or outsource the analysis to third-party infrastructure.

## Intended users

University students; lecturers and staff; non-technical internet users; campus IT and cybersecurity-awareness teams.

## Proposed solution

A web application where a user pastes any URL and receives, within a second:

1. A **classification** — Likely benign / Suspicious / High risk, with an explicit uncertainty flag.
2. An **explanation** — the observed URL characteristics and the exact feature contributions that drove the model's decision.
3. **Safety recommendations** matched to the evidence.
4. **Honest limitations** — what the system cannot determine.

The destination website is never contacted: the entire analysis operates on the URL string, which removes SSRF risk and never alerts malicious operators.

## Technical approach

- **Data:** a public research corpus of 11,203 raw URLs (5,488 phishing / 5,715 legitimate, CC-BY-4.0, arXiv:2010.12847), validated, de-duplicated and split so that no website domain appears in both training and test data. Provenance and checksums documented.
- **Features:** one shared, versioned extractor computes 57 lexical features (structure, tokens, encoding, hostname composition, word statistics, entropy) on a canonical form of the URL, so edits that do not change the destination, such as adding `www.`, cannot change the verdict. The *same* code path powers training and live inference, eliminating train/serve skew by construction; a schema-version check refuses to serve mismatched artefacts.
- **Model:** gradient-boosted trees, selected from eight learners and two baselines under domain-grouped cross-validation, randomised tuning and corrected significance tests. Gradient boosting is significantly better than every other family, and because the project extended exact explanations to boosted trees, choosing it costs no explainability. The full study is in the separate Phishing-url-detection-ML research project.
- **Explainability:** exact decision-path decomposition in log-odds (treeinterpreter method with expected node values), verified on 500 test URLs to reproduce `predict_proba` exactly, plus rule-derived observations, clearly separated from model-derived numbers.
- **Stack:** React 19 + TypeScript + Vite + Tailwind; Python FastAPI + Pydantic; scikit-learn; Supabase Auth + Postgres with Row Level Security (SQLite for local development); pytest (141 tests); Jupyter research notebook for the ML workflow.

## Innovation

ThreatLens combines **automated detection with exact, per-prediction explanations** rather than post-hoc global importances; evaluates on **domains the model has never seen** and measures how much random splits would have overstated performance (+0.032 PR-AUC) and how much a crawl artefact (`www.`) could swing verdicts (24% of decisions without canonical features, none with them), with out-of-source probes alongside the headline metrics; and treats **responsible AI as an engineering constraint** — honest uncertainty bands, honest "not integrated" statuses for absent integrations, and guidance that never tells users to open suspicious links.

## Expected impact

- Immediate: better-informed decisions about individual links on campus.
- Educational: every result teaches the signals of phishing, building durable instincts.
- Institutional: a foundation for awareness training and, later, one-click reporting into campus IT processes.

## Demonstrated outcomes (verified during this build)

- End-to-end scan flow verified through a real browser: submit → backend inference (55–60 ms) → explained result.
- Held-out test performance on 2,110 URLs from unseen domains: PR-AUC 0.945 (95% CI 0.924–0.962), accuracy 88.7%, precision 88.2%, recall 86.1%, F1 87.1% (confusion matrix: TN 1,061, FP 108, FN 131, TP 810).
- Out-of-source probes (deployed model): 90.0% recall proxy on 300 fresh OpenPhish URLs; 1.3% false-positive rate on the 1,000 most-linked domains.
- 120/120 automated backend tests passing; frontend production build succeeds; all eight pages render on desktop and mobile viewports.

## Limitations

URL-lexical analysis cannot see page content or server behaviour; the classifier makes mistakes in both directions (published confusion matrix); dataset bias skews benign examples towards popular sites; no threat-intelligence integration (reported honestly, not simulated); in-process rate limiting (single instance); model requires periodic retraining as phishing evolves.

## Future development

Optional Safe Browsing/PhishTank integration with explicit disclosure; scheduled retraining with drift monitoring; probability calibration; campus reporting integration; multi-user deployment with authentication.

---

*Educational, research-oriented student project. No institutional endorsement implied.*
