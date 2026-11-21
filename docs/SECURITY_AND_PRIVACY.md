# Security & Privacy — ThreatLens AI

This document describes the security controls and data handling **as actually implemented**, the known risks, and the remaining security work. Every claim below maps to code in this repository; where something is *not* implemented, it is listed as remaining work.

---

## 1. What the scanner analyses

Only the submitted URL **string**. The backend parses the text and computes 57 lexical features; the trained tree-ensemble model classifies them. No page content, screenshots, downloads, redirects, cookies, credentials, or browser state are involved.

## 2. The destination website is never contacted

There is **no HTTP client, browser automation, screenshot service, redirect resolver, or server-side fetch anywhere in the scan code path**. Consequences:

- No SSRF surface: a submitted URL can never become a backend request destination.
- Malicious infrastructure is never alerted to the analysis.
- Honest boundary: the system cannot know what the destination actually serves.

Optional external lookups (none integrated) would be a separate, documented operation with an allow-listed provider endpoint — never a user-controlled destination.

## 3. Input validation (server-side)

- Type checks (string), empty-input rejection, 2048-character URL limit, 16 KB request-body cap.
- Scheme allow-list: `http://`, `https://`, or a bare domain under a **documented** parsing rule (the response records `scheme_was_inferred`; no invented scheme is pretended).
- Control characters, malformed hostnames, invalid ports and local hostnames (`localhost`, `*.local`) rejected.
- Frontend validation is treated as UX only — the backend re-validates everything.
- Consistent error envelope `{"error": {"code", "message"}}`; the frontend maps error codes to plain-language guidance.

## 4. Rate limiting and abuse prevention

- In-process sliding-window limiter on `POST /api/scan` (default 30 requests/minute/client, `RATE_LIMIT_SCAN_PER_MINUTE`), returning HTTP 429 with `Retry-After`.
- **Documented limitation:** per-process memory — appropriate for the single-instance prototype; a multi-instance deployment must replace it with a shared store (e.g. Redis).

## 5. Frontend security

- All user-supplied URLs render as inert text (`word-break` styling, never an anchor `href`); the app contains no `dangerouslySetInnerHTML` and never navigates the browser to a submitted URL.
- Response headers set by the API: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, restrictive `Permissions-Policy`.
- No secrets, keys, or backend internals exist in frontend code; the frontend is static assets only.
- Meta referrer `no-referrer` on the SPA.

## 6. Secrets and configuration

- `.env.example` files contain placeholders only; real `.env` files are git-ignored. The only Supabase credential used anywhere is the **publishable** key (public by design) plus the project URL. No service-role key, database password, OAuth client secret, or JWT signing secret exists in this codebase.
- `.gitignore` excludes `.env`, SQLite databases, model artefacts, `node_modules`, build output.
- Fail-safe behaviour: missing configuration produces explicit, actionable errors (e.g. auth returns 503 `auth_not_configured` until Supabase env vars are set); missing model artefacts produce explicit errors and a 503 — never a substitute prediction.

## 7. Data flow and retention

| Data | Where it goes | Retention |
|---|---|---|
| Submitted URL | Backend memory → feature extraction → model | Ephemeral; not persisted unless history is on |
| Scan result | Returned to the requesting (authenticated) client | — |
| Scan record (URL, classification, score, probability, timestamp, model version, result JSON) | `HISTORY_MODE=supabase`: one row in Supabase Postgres **owned by the authenticated user** (`user_id = auth.uid()`, enforced by RLS) | Until deleted by the user (single record or clear-all via API/UI); deleting the auth account cascades the row deletion |
| Scan record (same fields) | `HISTORY_MODE=sqlite`: local SQLite file, capped at 500 (FIFO), keyed by verified user id | Until deleted by the user |
| `HISTORY_MODE=memory` | In-process RAM | Cleared on restart |
| `HISTORY_MODE=disabled` | Nowhere | Nothing stored |
| Credentials (password, tokens) | **Supabase Auth only** — never stored, logged, or proxied by this application | Managed by Supabase Auth (bcrypt server-side, JWT sessions) |
| Profile row (display name, timestamps) | `public.profiles`, owner-only via RLS | Until account deletion |
| Logs | stdout | URLs redacted to scheme + host; tokens and passwords never logged |
| Anything to third parties | **Nothing** beyond Supabase Auth/Postgres (the configured project) | — |

**Multi-user isolation:** every protected endpoint authenticates the caller's Supabase access token (JWKS signature verification, or the Auth `/user` endpoint fallback) and derives the user id exclusively from verified claims. In `supabase` mode even the backend cannot bypass Row Level Security because it holds no privileged key. Deletion endpoints: `DELETE /api/history/{id}`, `DELETE /api/history`.

## 8. External providers

None integrated. The scan response's `threat_intelligence` object reports status `unavailable` with a plain-language message rather than simulating a lookup. "No match returned ≠ safe" semantics are codified in the reputation service interface for future providers.

## 9. Data-protection considerations (Malaysia)

The prototype is designed to minimise personal-data exposure: URL strings processed locally, optional capped storage, user-controlled deletion, no third-party transfers, no profiling. This is consistent with the spirit of good practice under Malaysia's **Personal Data Protection Act 2010 (PDPA)**. This statement is an engineering description only — **not legal advice, not a compliance certification, and no regulatory approval is claimed**. Production operators should perform their own assessment.

## 10. What the system cannot determine

- Whether the destination website is malicious or safe (it is never visited).
- Reputation of a domain (no provider integrated).
- Whether novel phishing techniques differing from the training data will be caught.
- Whether the model probability reflects real-world risk (uncalibrated estimate).
- Intent behind a URL (suspicious-looking ≠ malicious; clean-looking ≠ safe).

## 11. Known risks & remaining security work

1. **Email-confirmation dependency for full end-to-end testing** — with *Confirm email* ON and the built-in SMTP rate limit, a new signup cannot be completed from this environment without access to a real inbox; the flow was verified up to the provider boundary (signup call, validation errors, rate-limit handling) and the remaining steps are documented in README §8.6.
2. **Google OAuth** — the frontend flow is fully wired (PKCE, callback route, provider auto-detection) but the provider is not yet enabled in the Supabase dashboard, so the live OAuth redirect has not been exercised end-to-end. Configure per README §8.6 step 5.
3. **Distributed rate limiting** — in-process only; replace for multi-instance deployment.
4. **Security-header hardening at the static host** — the API sets headers; a production reverse proxy should also enforce CSP and HSTS.
5. **Model artefact integrity** — artefacts are trusted as locally trained; a production deployment should add checksum verification of `phishing_model.joblib`.
6. **Dependency audit** — pinned ranges used; run `pip audit` / `npm audit` before any public deployment.
7. **Retraining pipeline hardening** — dataset download should verify hashes/manifests when automated.
