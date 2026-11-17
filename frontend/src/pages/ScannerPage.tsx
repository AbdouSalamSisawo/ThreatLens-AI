import { useState } from "react";
import { Link } from "react-router-dom";
import { ScanSearch } from "lucide-react";
import { Layout } from "../components/Layout";
import { ScanInput } from "../components/ScanInput";
import { ScanResultView } from "../components/ScanResultView";
import { ErrorPanel } from "../components/ErrorPanel";
import { ApiRequestError } from "../services/api";
import type { ScanResult } from "../types/api";

export function ScannerPage() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [scanning, setScanning] = useState(false);

  function handleResult(r: ScanResult) {
    setError(null);
    setResult(r);
  }

  function handleError(e: ApiRequestError) {
    setResult(null);
    setError(e);
  }

  const hasContent = result || error || scanning;

  return (
    <Layout>
      <div className="grid-bg border-b border-border">
        <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <ScanSearch size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">
                URL Scanner
              </h1>
              <p className="text-sm text-text-dim">
                Explainable phishing screening — the destination is never contacted.
              </p>
            </div>
          </div>

          <div className="mt-7 panel ticks p-5 sm:p-6">
            <ScanInput
              onResult={handleResult}
              onError={handleError}
              onScanningChange={setScanning}
              compact
            />
          </div>

          {scanning && <ScanningState />}
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6" aria-live="polite">
        {result && (
          <ScanResultView
            result={result}
            onRescan={() => {
              setResult(null);
              setError(null);
            }}
          />
        )}
        {error && <ErrorPanel error={error} />}
        {!hasContent && <IntroContent />}
      </div>
    </Layout>
  );
}

/* Honest indeterminate state: a scan animation while the real request runs.
   No fake stage completion, no invented percentages. */
function ScanningState() {
  return (
    <div className="mt-5 panel p-5" role="status" aria-live="polite">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-text">
          Analysing URL<span className="animate-pulse">…</span>
        </p>
        <p className="font-mono text-[11px] text-text-faint">
          validating → parsing → features → inference → explanation
        </p>
      </div>
      <div className="scanline-track mt-4 h-1.5 rounded-full" />
    </div>
  );
}

function IntroContent() {
  return (
    <div className="grid gap-5 md:grid-cols-3">
      <div className="panel p-5">
        <h2 className="text-sm font-semibold text-text">Accepted input</h2>
        <ul className="mt-3 space-y-2 text-xs leading-relaxed text-text-dim">
          <li>• Complete links: <span className="font-mono text-info">https://example.com/page</span></li>
          <li>• Bare domains: <span className="font-mono text-info">example.com</span> — parsed without pretending a scheme existed</li>
          <li>• Surrounding whitespace is trimmed automatically</li>
          <li>• Only <span className="font-mono">http</span> and <span className="font-mono">https</span> schemes are accepted</li>
          <li>• Maximum length 2048 characters</li>
        </ul>
      </div>
      <div className="panel p-5">
        <h2 className="text-sm font-semibold text-text">What happens on submit</h2>
        <ol className="mt-3 space-y-2 text-xs leading-relaxed text-text-dim">
          <li>1. The URL is re-validated on the server.</li>
          <li>2. It is parsed locally — no request is made to the destination.</li>
          <li>3. 33 lexical features are extracted.</li>
          <li>4. The trained model produces a probability.</li>
          <li>5. The explanation service derives exact evidence.</li>
          <li>6. Recommendations follow the evidence.</li>
        </ol>
      </div>
      <div className="panel p-5">
        <h2 className="text-sm font-semibold text-text">Read the result carefully</h2>
        <ul className="mt-3 space-y-2 text-xs leading-relaxed text-text-dim">
          <li>• <span className="text-warn">Suspicious</span> means meaningful indicators — not proof.</li>
          <li>• <span className="text-ok">Likely benign</span> is not a safety certificate.</li>
          <li>• Uncertain scores are flagged explicitly.</li>
          <li>• Never open a link to “check” it yourself.</li>
        </ul>
        <Link to="/security-privacy" className="mt-3 inline-block text-xs text-info hover:underline">
          Read the full limitations →
        </Link>
      </div>
    </div>
  );
}
