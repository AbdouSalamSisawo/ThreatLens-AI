# Demonstration Script — ThreatLens AI

A reliable ~6-minute live demo for the MMC Upstart 2026 Catalyst judging. Everything runs locally — **no external API, no internet dependency, no live phishing links**.

## Before the demo (preparation checklist)

1. Backend running: `cd backend && python -m uvicorn app.main:app --port 8000`
2. Frontend running: `cd frontend && bun run dev` → open the shown URL (or use the single-origin build on :8000).
3. Verify readiness: the scanner page loads with no warning banner (the app checks `GET /api/ready` itself).
4. Have the **Model Performance** page open in a second tab.
5. Clear history for a clean start (optional): History page → *Clear all history* → confirm.

## 1. The problem (30 seconds)

> "Phishing works because a link is the one part of a message we're trained to click before we think. Students get fake bursary notices, blocked-account warnings, scholarship portals. Verdict-only tools don't teach anything — and they can't tell you *why*. ThreatLens was built to change that: it analyses the link, shows its evidence, and admits what it cannot know."

## 2. Scan a suspicious-looking URL (90 seconds)

On the Scanner page, click the example chip **"Suspicious-looking"** (a documented, non-operational address built on `example.tk` — nothing dangerous is contacted) and press **Analyse URL**.

Point out, reading the real result:

- The **classification** and the **risk score** — "this comes from the model's estimated phishing probability; the mapping is documented."
- **Observed URL characteristics** — "every line is measured from the actual string: brand token outside the domain, security vocabulary, non-HTTPS…"
- **Model evidence** — "these bars are an *exact* decomposition of the model's decision — our tests verify the decomposition reproduces the model's probability to six decimal places. We never show invented importance numbers."
- **Recommended next steps** — "notice it never says 'open the link to check'."
- **What this result cannot tell you** — "we say the quiet part out loud."

## 3. Contrast with a benign URL (60 seconds)

Click **"Ordinary site"** (e.g. `https://www.wikipedia.org/`) → Analyse.

- Result: *Likely benign* — "and immediately the UI tells you this is **not a safety certificate**. If the model is genuinely torn, the result is flagged *uncertain* instead of pretending confidence."
- Demo the **malformed** example to show server-side validation rejects junk gracefully.

## 4. The evidence trail: Dashboard & History (60 seconds)

- **Dashboard:** "every number here is a real query against the local store — no fake totals, no demo filler. Fresh installs show an honest empty state."
- **History:** search, filter by classification, open a stored result, delete a record. "Storage is configurable: `disabled` stores nothing at all, `memory` keeps RAM-only, `sqlite` caps at 500 deletable records."

## 5. Genuine model performance (90 seconds)

Switch to the **Model Performance** tab:

- "These metrics come from a single evaluation on a held-out test set — 11,203 public, licence-documented URLs. Accuracy 86%, **precision 89%**, **recall 82%**. We publish the confusion matrix because the two error types hurt different people."
- "And because random-split numbers flatter models, we publish **stricter checks**: a domain-grouped split where performance drops, plus probes on 300 fresh OpenPhish URLs and the 1,000 most-visited domains. What you see is the model as it really is."

## 6. Responsible AI & limitations (45 seconds)

- "No threat-intelligence provider is integrated — the result says *unavailable* instead of pretending. No generative AI is used anywhere. The destination site is never contacted — that's a security decision, not a limitation we hid."
- Close with the Responsible-use section: "This is an assistive screening system. It teaches signals, exposes uncertainty, and routes people to official reporting channels — which is exactly what campus cyber-safety needs."

## Suggested Q&A ammunition

| Likely question | Grounded answer |
|---|---|
| "Is 82% recall good enough?" | It's honest for a lexical-only model on a public corpus; the grouped-split and fresh-feed numbers show the real range. Roadmap: content-level features and scheduled retraining. |
| "Could attackers evade it?" | Yes — lexical signals can be changed. That's why the system discloses limitations and why retraining + optional reputation feeds are roadmap items. |
| "Where do the explanations come from?" | Exact tree-path decomposition of the forest (treeinterpreter method), tested for exactness; rule-derived observations are labelled separately from model evidence. |
| "What about privacy?" | The destination is never fetched; storage is off/RAM/capped-local; logs redact URLs; nothing leaves the deployment. |
| "How was it trained?" | Public CC-BY-4.0 corpus of 11,203 de-duplicated URLs; one shared feature extractor for training and inference; documented split and selection policy. |

## Fall-back plan

If the live scan fails for any reason (e.g. port conflict), refresh the page — the app surfaces the backend status itself. If the model artefacts were wiped, the scan endpoint returns an explicit 503 with the exact training command, which is itself a demonstration of the system's fail-safe honesty.
