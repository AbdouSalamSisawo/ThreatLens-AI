import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Copy,
  Eye,
  ListChecks,
  RefreshCw,
  Scale,
} from "lucide-react";
import type { ScanResult, ModelContribution } from "../types/api";
import { CLASSIFICATION_META, SeverityDot, StatusBadge } from "./StatusBadge";

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          setCopied(false);
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-dim transition-colors hover:border-accent/40 hover:text-text"
      aria-label={label}
    >
      {copied ? (
        <Check size={13} className="text-ok" aria-hidden />
      ) : (
        <Copy size={13} aria-hidden />
      )}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function truncateUrl(url: string, max = 96) {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

function RiskGauge({ score, classification }: { score: number; classification: string }) {
  const meta = CLASSIFICATION_META[classification as keyof typeof CLASSIFICATION_META];
  const colorClass =
    classification === "high_risk"
      ? "text-danger"
      : classification === "suspicious"
        ? "text-warn"
        : "text-ok";
  return (
    <div className="panel-inset px-4 py-3" aria-label={`Risk score ${score} out of 100`}>
      <p className="text-[11px] font-medium uppercase tracking-wider text-text-faint">
        Model risk score
      </p>
      <p className={`mt-1 font-mono text-3xl font-semibold ${colorClass}`}>
        {score}
        <span className="text-sm text-text-faint">/100</span>
      </p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className={`h-full rounded-full ${meta.dot}`}
          style={{ width: `${score}%` }}
          role="presentation"
        />
      </div>
      <p className="mt-2 text-[11px] leading-snug text-text-faint">
        Derived from the model's estimated phishing-class probability.
        Not a calibrated probability of criminal activity.
      </p>
    </div>
  );
}

function ContributionBars({ items }: { items: ModelContribution[] }) {
  const reduce = useReducedMotion();
  const max = Math.max(...items.map((c) => Math.abs(c.contribution)), 1e-9);
  return (
    <ul className="space-y-2.5" aria-label="Feature contributions toward the prediction">
      {items.map((c) => {
        const width = Math.max(4, (Math.abs(c.contribution) / max) * 100);
        const towardPhish = c.direction === "toward_phishing";
        return (
          <li key={c.feature}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <span className="text-xs font-medium text-text">{c.feature_label}</span>
              <span
                className={`font-mono text-[11px] ${towardPhish ? "text-danger" : "text-ok"}`}
              >
                {towardPhish ? "+" : "−"}
                {Math.abs(c.contribution).toFixed(4)}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                <motion.div
                  className={`h-full rounded-full ${towardPhish ? "bg-danger/80" : "bg-ok/80"}`}
                  initial={reduce ? false : { width: 0 }}
                  animate={{ width: `${width}%` }}
                  transition={{ duration: 0.55, ease: "easeOut", delay: 0.05 }}
                />
              </div>
              <span className="w-28 shrink-0 text-right text-[10px] text-text-faint">
                {towardPhish ? "toward phishing" : "toward benign"}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Collapsible({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="panel">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-medium text-text">{title}</span>
        <ChevronDown
          size={16}
          aria-hidden
          className={`text-text-dim transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="border-t border-border px-4 py-4">{children}</div>}
    </div>
  );
}

export function ScanResultView({
  result,
  onRescan,
}: {
  result: ScanResult;
  onRescan: () => void;
}) {
  const meta = CLASSIFICATION_META[result.classification];
  const evidence = result.explanation.model_evidence;

  return (
    <motion.section
      aria-label="Scan result"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="space-y-5"
    >
      {/* Header */}
      <div className={`panel ticks p-5 sm:p-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge classification={result.classification} />
              {result.is_uncertain && (
                <span className="rounded-md border border-info/30 bg-info/10 px-2 py-0.5 text-xs text-info">
                  uncertain
                </span>
              )}
            </div>
            <p
              className="url-text mt-3 font-mono text-sm leading-relaxed text-text"
              title={result.url}
            >
              {truncateUrl(result.url)}
            </p>
            <p className="mt-2 text-xs text-text-faint">
              {result.scheme_was_inferred
                ? "No scheme was submitted — parsed as a domain without pretending https:// existed."
                : ""}
              {result.scheme_was_inferred ? " " : ""}
              Scan {result.scan_id} ·{" "}
              {new Date(result.scan_timestamp).toLocaleString()} · model inference{" "}
              {result.scan_duration_ms} ms
              {result.history_saved ? " · saved to history" : " · not saved"}
            </p>
          </div>
          <div className="w-full max-w-[220px] shrink-0">
            <RiskGauge score={result.risk_score} classification={result.classification} />
          </div>
        </div>

        <div className={`mt-4 rounded-lg border ${meta.border} ${meta.bg} p-4`}>
          <p className="text-sm leading-relaxed text-text">
            {result.explanation.summary}
          </p>
          <p className="mt-2 font-mono text-xs text-text-dim">
            Estimated model probability (phishing class):{" "}
            <span className="text-text">
              {(result.model_probability * 100).toFixed(1)}%
            </span>{" "}
            · binary decision:{" "}
            <span className="text-text">{result.binary_prediction}</span>
            {result.binary_prediction === "benign" && (
              <span className="text-warn"> · not a safety guarantee</span>
            )}
          </p>
        </div>
      </div>

      {/* Evidence grid */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Observed characteristics */}
        <div className="panel p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
            <Eye size={16} className="text-accent" aria-hidden />
            Observed URL characteristics
          </h3>
          <p className="mt-1 text-xs text-text-faint">
            Directly measured properties of the submitted URL string.
          </p>
          <ul className="mt-4 space-y-3">
            {result.explanation.observed_characteristics.map((o) => (
              <li key={o.label} className="flex gap-3">
                <SeverityDot severity={o.severity} />
                <div>
                  <p className="text-sm font-medium text-text">{o.label}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-text-dim">
                    {o.detail}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Model evidence */}
        <div className="panel p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
            <Scale size={16} className="text-accent" aria-hidden />
            Model evidence
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-text-faint">
            {evidence.method_description}
          </p>
          {evidence.top_contributions.length > 0 ? (
            <div className="mt-4">
              <ContributionBars items={evidence.top_contributions} />
            </div>
          ) : (
            <p className="mt-4 rounded-md border border-warn/30 bg-warn/10 p-3 text-xs leading-relaxed text-warn">
              Per-instance model contributions are unavailable for this model
              type. Only measured URL characteristics are shown; nothing is
              simulated.
            </p>
          )}
          <p className="mt-4 text-[11px] leading-relaxed text-text-faint">
            {evidence.disclaimer}
          </p>
        </div>
      </div>

      {/* Recommendations + limitations */}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="panel p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
            <ListChecks size={16} className="text-accent" aria-hidden />
            Recommended next steps
          </h3>
          <ul className="mt-4 space-y-2.5">
            {result.explanation.recommended_actions.map((a, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-text-dim">
                <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {a}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
            <AlertTriangle size={16} className="text-warn" aria-hidden />
            What this result cannot tell you
          </h3>
          <ul className="mt-4 space-y-2.5">
            {result.explanation.cannot_determine.concat(result.limitations.slice(0, 1)).map((l, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-text-dim">
                <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
                {l}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Threat intel status (honest) */}
      <div className="panel p-5">
        <h3 className="text-sm font-semibold text-text">Threat-intelligence status</h3>
        <p className="mt-2 text-sm leading-relaxed text-text-dim">
          <span className="font-mono text-xs text-warn">
            {result.threat_intelligence.status}
          </span>{" "}
          — {result.threat_intelligence.message}
        </p>
      </div>

      {/* Expandable technical detail */}
      <Collapsible title="Technical details — all extracted features">
        <div className="slim-scroll max-h-96 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">
              All lexical features extracted from the submitted URL
            </caption>
            <thead className="sticky top-0 bg-surface">
              <tr className="text-text-faint">
                <th scope="col" className="py-2 pr-3 font-medium">Feature</th>
                <th scope="col" className="py-2 pr-3 font-medium">Value</th>
                <th scope="col" className="py-2 font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {result.observed_features.map((f) => (
                <tr key={f.name}>
                  <td className="py-2 pr-3 font-mono text-[11px] text-info">{f.name}</td>
                  <td className="py-2 pr-3 font-mono text-text">{f.value}</td>
                  <td className="py-2 text-text-dim">{f.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Collapsible>

      <Collapsible title="Model & provenance for this scan">
        <dl className="grid gap-x-8 gap-y-2 text-xs sm:grid-cols-2">
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Model ID</dt>
            <dd className="font-mono text-text">{result.model_id}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Model version</dt>
            <dd className="font-mono text-text">{result.model_version}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Selected model</dt>
            <dd className="font-mono text-text">{result.selected_model}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Feature schema</dt>
            <dd className="font-mono text-text">v{result.feature_schema_version}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Evidence method</dt>
            <dd className="font-mono text-text">{evidence.method}</dd>
          </div>
          {evidence.probability_check && (
            <div className="flex justify-between gap-4">
              <dt className="text-text-faint">Decomposition exact</dt>
              <dd className="font-mono text-ok">
                {String(evidence.probability_check.exact)}
              </dd>
            </div>
          )}
        </dl>
      </Collapsible>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onRescan}
          className="inline-flex items-center gap-2 rounded-lg border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/20"
        >
          <RefreshCw size={15} aria-hidden />
          Analyse another URL
        </button>
        <CopyButton text={result.url} label="Copy the submitted URL" />
        <CopyButton
          text={`${result.classification.toUpperCase()} (${result.risk_score}/100) — ${result.url} — ThreatLens AI scan ${result.scan_id}`}
          label="Copy a result summary"
        />
      </div>
    </motion.section>
  );
}
