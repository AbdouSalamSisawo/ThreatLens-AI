import { AlertCircle, ServerCrash } from "lucide-react";
import type { ApiRequestError } from "../services/api";

/* Plain-language error panel with a next action. Never shows stack traces. */

const HINTS: Record<string, string> = {
  network_error:
    "The frontend could not reach the backend API. If you are running locally, make sure the FastAPI server is started (see the README).",
  model_unavailable:
    "The trained model is not loaded on the server. Train it with the documented pipeline: prepare the dataset, then run the training script.",
  rate_limited:
    "Too many scans were requested from this address in a short window. Wait a minute and try again.",
  empty_input: "Type or paste a URL into the input field.",
  invalid_url:
    "Check the address for typos. A URL needs a domain, for example https://example.com",
  unsupported_scheme:
    "Only http:// and https:// links can be analysed. Downloads, data URIs and scripts are rejected by design.",
  url_too_long: "The submitted URL exceeds the maximum supported length.",
  validation_error: "The request was malformed. Try submitting the URL again.",
};

export function ErrorPanel({ error }: { error: ApiRequestError }) {
  const hint = HINTS[error.code];
  return (
    <div
      role="alert"
      className="panel border-danger/30 p-5 sm:p-6"
      aria-live="assertive"
    >
      <div className="flex items-start gap-4">
        {error.status === 0 ? (
          <ServerCrash size={22} className="mt-0.5 shrink-0 text-danger" aria-hidden />
        ) : (
          <AlertCircle size={22} className="mt-0.5 shrink-0 text-danger" aria-hidden />
        )}
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text">
            Analysis could not be completed
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-text-dim">{error.message}</p>
          {hint && (
            <p className="mt-2 rounded-md border border-border bg-bg-deep p-3 text-xs leading-relaxed text-text-dim">
              <span className="font-medium text-text">Suggestion: </span>
              {hint}
            </p>
          )}
          <p className="mt-3 font-mono text-[11px] text-text-faint">
            error code: {error.code}
            {error.status ? ` · HTTP ${error.status}` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
