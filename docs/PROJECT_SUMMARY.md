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

- **Data:** a public research corpus of 11,203 raw URLs (5,488 phishing / 5,715 legitimate, CC-BY-4.0, arXiv:2010.12847), validated, de-duplicated and re-split with leakage controls. Provenance documented.
- **Features:** one shared, versioned extractor computes 33 lexical features (structure, tokens, encoding, hostname composition, entropy). The *same* code path powers training and live inference, eliminating train/serve skew by construction; a schema-version check refuses to serve mismatched artefacts.
- **Model:** Random Forest selected over Logistic Regression and Hist Gradient Boosting by validation PR-AUC under a documented, explainability-aware tie-break policy.
- **Explainability:** exact decision-path decomposition (treeinterpreter method) — verified in tests to reproduce `predict_proba` to 1e-6 — plus rule-derived observations, clearly separated from model-derived numbers.
- **Stack:** React 19 + TypeScript + Vite + Tailwind; Python FastAPI + Pydantic; scikit-learn; SQLite behind a swappable service layer; pytest (80 tests).

## Innovation

ThreatLens combines **automated detection with exact, per-prediction explanations** rather than post-hoc global importances; publishes **stricter generalisation checks** (domain-grouped split, out-of-source probes) alongside headline metrics; and treats **responsible AI as an engineering constraint** — honest uncertainty bands, honest "not integrated" statuses for absent integrations, and guidance that never tells users to open suspicious links.

## Expected impact

- Immediate: better-informed decisions about individual links on campus.
- Educational: every result teaches the signals of phishing, building durable instincts.
- Institutional: a foundation for awareness training and, later, one-click reporting into campus IT processes.

## Demonstrated outcomes (verified during this build)

- End-to-end scan flow verified through a real browser: submit → backend inference (55–60 ms) → explained result.
- Held-out test performance: accuracy 86.26%, precision 89.03%, recall 82.06%, F1 85.40%, PR-AUC 0.9423 (confusion matrix: TN 1032, FP 111, FN 197, TP 901).
- Out-of-source probes: 79.3% recall proxy on 300 fresh OpenPhish URLs; 2.3% false-positive rate on the 1,000 most-visited domains.
- 80/80 automated backend tests passing; frontend production build succeeds; all eight pages render on desktop and mobile viewports.

## Limitations

URL-lexical analysis cannot see page content or server behaviour; the classifier makes mistakes in both directions (published confusion matrix); dataset bias skews benign examples towards popular sites; no threat-intelligence integration (reported honestly, not simulated); single-user prototype without accounts; model requires periodic retraining as phishing evolves.

## Future development

Optional Safe Browsing/PhishTank integration with explicit disclosure; scheduled retraining with drift monitoring; probability calibration; campus reporting integration; multi-user deployment with authentication.

---

*Educational, research-oriented student project. No institutional endorsement implied.*
