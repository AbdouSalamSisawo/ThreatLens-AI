import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { api, ApiRequestError } from "../services/api";
import type { ScanResult } from "../types/api";

const EXAMPLES: { label: string; url: string; note: string }[] = [
  {
    label: "Ordinary site",
    url: "https://www.wikipedia.org/",
    note: "A well-known website.",
  },
  {
    label: "Suspicious-looking",
    url: "http://paypal-secure-login.verify-account.example.tk/login/confirm.php?user=x",
    note: "Non-operational example address built for demonstration (RFC 2606 / TEST-NET style). The real model decides — do not assume the label.",
  },
  {
    label: "Misleading structure",
    url: "https://www.google.com.search-results.example.com/account/verify?id=4821",
    note: "A real brand token placed before the actual domain.",
  },
  {
    label: "Unusually long",
    url:
      "https://example.com/very/long/path/" + "segment/".repeat(8) + "?q=" + "a".repeat(40),
    note: "Deep path and long query string.",
  },
  {
    label: "Malformed",
    url: "ht!tp://not-a-valid-url",
    note: "Rejected by validation — no scan happens.",
  },
];

export function ScanInput({
  onResult,
  onError,
  onScanningChange,
  compact = false,
}: {
  onResult: (r: ScanResult) => void;
  onError: (e: ApiRequestError) => void;
  onScanningChange?: (scanning: boolean) => void;
  compact?: boolean;
}) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function submit(urlOverride?: string) {
    const candidate = (urlOverride ?? value).trim();
    if (!candidate) {
      setLocalError("Enter a URL to analyse, for example https://example.com");
      inputRef.current?.focus();
      return;
    }
    if (loading) return; // prevent double submission
    setLocalError(null);
    setLoading(true);
    onScanningChange?.(true);
    try {
      const result = await api.scan(candidate);
      onResult(result);
    } catch (err) {
      onError(
        err instanceof ApiRequestError
          ? err
          : new ApiRequestError("Unexpected error while scanning.", "unknown", 0),
      );
    } finally {
      setLoading(false);
      onScanningChange?.(false);
    }
  }

  return (
    <div className={compact ? "" : "w-full"}>
      <form
        className="flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        noValidate
      >
        <div className="relative flex-1">
          <label htmlFor="scan-url-input" className="sr-only">
            URL to analyse
          </label>
          <Search
            size={18}
            aria-hidden
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-faint"
          />
          <input
            id="scan-url-input"
            ref={inputRef}
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://example.com or example.com"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submit();
              }
            }}
            disabled={loading}
            aria-invalid={!!localError}
            aria-describedby="scan-url-help"
            className={`h-12 w-full rounded-lg border bg-bg-deep pl-10 pr-3 font-mono text-sm text-text placeholder:text-text-faint disabled:opacity-60 ${
              localError ? "border-danger/60" : "border-border-strong"
            } focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent`}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-accent px-6 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <Loader2 size={17} className="animate-spin" aria-hidden />
          ) : (
            <Search size={17} aria-hidden />
          )}
          {loading ? "Analysing…" : "Analyse URL"}
        </button>
      </form>

      <div id="scan-url-help" className="mt-2.5 space-y-1">
        {localError && (
          <p role="alert" className="text-sm text-danger">
            {localError}
          </p>
        )}
        {!localError && (
          <p className="text-xs leading-relaxed text-text-dim">
            Analysis is based on the URL's structure and a machine-learning
            model trained on public datasets. The destination website is{" "}
            <strong className="text-text">never contacted</strong>. Scans may
            be stored locally according to the configured{" "}
            <Link to="/security-privacy" className="text-info hover:underline">
              history policy
            </Link>
            . A benign result is not a safety guarantee.
          </p>
        )}
      </div>

      {!compact && (
        <div className="mt-5">
          <p className="text-xs font-medium uppercase tracking-wider text-text-faint">
            Example inputs <span className="normal-case tracking-normal">(documented, non-operational where suspicious-looking)</span>
          </p>
          <div className="mt-2 flex flex-wrap gap-2" role="list">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                role="listitem"
                disabled={loading}
                title={ex.note}
                onClick={() => {
                  setValue(ex.url);
                  setLocalError(null);
                }}
                className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-text-dim transition-colors hover:border-accent/40 hover:text-text disabled:opacity-50"
              >
                {ex.label}
              </button>
            ))}
            <Link
              to="/how-it-works"
              className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs text-info hover:underline"
            >
              How analysis works <ExternalLink size={12} aria-hidden />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
