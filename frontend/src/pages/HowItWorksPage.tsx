import { Link } from "react-router-dom";
import {
  BrainCircuit,
  CheckCircle2,
  Cpu,
  FileSearch,
  GitBranch,
  Lightbulb,
  ListOrdered,
  ScanSearch,
  ShieldAlert,
  Split,
  XCircle,
} from "lucide-react";
import { Layout } from "../components/Layout";

const STEPS = [
  {
    icon: ScanSearch,
    title: "1 · URL input & validation",
    body: "You submit a link in the scanner. The frontend performs light formatting, then the backend independently re-validates everything: string type, length limit (2048 chars), allowed schemes (http/https, or a bare domain as a documented convenience), control characters, and malformed hostnames. Client-side validation is never trusted.",
  },
  {
    icon: Split,
    title: "2 · URL parsing",
    body: "The validated string is parsed with Python's urllib into scheme, hostname, port, path, query and fragment. A bare domain records that no scheme was present in the original submission — the system never pretends an invented scheme existed. The destination website is not contacted at any point.",
  },
  {
    icon: FileSearch,
    title: "3 · Lexical feature extraction",
    body: "One shared, versioned module (the exact same code used in training) computes 33 features: lengths, dot/hyphen/digit counts, digit ratios, percent-encoding counts, query parameters, '@' and credential patterns, IP-address hostnames, non-standard ports, shortener and suspicious-TLD indicators, punycode, brand-impersonation structure, hostname entropy and more. Each is a signal, never a verdict.",
  },
  {
    icon: BrainCircuit,
    title: "4 · Model inference",
    body: "The feature vector is fed to the trained scikit-learn tree-ensemble classifier, which outputs an estimated probability for the phishing class. The model is loaded once at server start from trusted artefacts produced by the project's research notebook. If artefacts are missing or incompatible, the API reports an explicit error — it never substitutes guesses.",
  },
  {
    icon: Lightbulb,
    title: "5 · Explanation generation",
    body: "The explanation service combines two layers: (a) observed characteristics — human-readable statements about what is actually present in the URL; (b) model evidence — an exact decision-path decomposition that attributes the forest's probability change to individual features (verified to reproduce predict_proba to 1e-6). Heuristic wording is clearly separated from model-derived numbers.",
  },
  {
    icon: CheckCircle2,
    title: "6 · Risk interpretation & guidance",
    body: "The probability maps to a documented band (likely benign < 0.50, suspicious ≥ 0.50, high risk ≥ 0.80) with an explicit uncertainty flag between 0.35–0.65. Recommendations follow the band and the observed evidence — e.g. verify the domain via an official source — and never suggest opening the link.",
  },
];

const DISTINCTIONS = [
  {
    icon: BrainCircuit,
    title: "Machine-learning prediction",
    yes: "What ThreatLens provides",
    body: "A statistical estimate from a model trained on a public corpus of labelled URLs. It generalises, it can be wrong, and it is transparent about its uncertainty.",
  },
  {
    icon: Split,
    title: "Heuristic indicator",
    yes: "Provided (as observations)",
    body: "Deterministic observations such as “hostname is an IP address”. Each list (shorteners, TLDs, tokens, brands) is documented in code. Indicators inform the model; they do not decide the outcome alone.",
  },
  {
    icon: GitBranch,
    title: "Threat-intelligence match",
    yes: "Not integrated",
    body: "A confirmed listing from a reputation provider (Google Safe Browsing, PhishTank…). ThreatLens reports an honest 'unavailable — not integrated' status instead of simulating one. Architecture exists to add a provider later.",
  },
  {
    icon: ShieldAlert,
    title: "Verified malicious website",
    yes: "Out of scope",
    body: "Only expert analysis or confirmed intelligence can establish this. A URL scanner — especially one that never visits the site — cannot and must not claim it.",
  },
];

export function HowItWorksPage() {
  return (
    <Layout>
      <div className="grid-bg border-b border-border">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <ListOrdered size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">How It Works</h1>
              <p className="text-sm text-text-dim">
                The actual implementation, explained for non-technical readers — with the technical detail one click away.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        {/* Pipeline */}
        <ol className="space-y-4">
          {STEPS.map((s) => (
            <li key={s.title} className="panel ticks p-5 sm:p-6">
              <div className="flex items-start gap-4">
                <span className="panel-inset flex h-11 w-11 shrink-0 items-center justify-center">
                  <s.icon size={20} className="text-accent" aria-hidden />
                </span>
                <div>
                  <h2 className="text-base font-semibold text-text">{s.title}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-text-dim">{s.body}</p>
                </div>
              </div>
            </li>
          ))}
        </ol>

        {/* Distinctions */}
        <h2 className="mt-12 text-xl font-semibold tracking-tight text-text">
          Prediction vs indicator vs threat-intelligence vs verified threat
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-text-dim">
          These terms are often conflated. ThreatLens is explicit about which
          ones it provides and which it deliberately does not.
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {DISTINCTIONS.map((d) => (
            <div key={d.title} className="panel p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-text">
                  <d.icon size={16} className="text-accent" aria-hidden />
                  {d.title}
                </h3>
                {d.yes.startsWith("Provided") || d.yes.startsWith("What") ? (
                  <CheckCircle2 size={16} className="shrink-0 text-ok" aria-hidden />
                ) : (
                  <XCircle size={16} className="shrink-0 text-warn" aria-hidden />
                )}
              </div>
              <p className="mt-1 text-[11px] font-medium uppercase tracking-wider text-text-faint">
                {d.yes}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-text-dim">{d.body}</p>
            </div>
          ))}
        </div>

        {/* Training explainer */}
        <h2 className="mt-12 text-xl font-semibold tracking-tight text-text">
          How the model was trained
        </h2>
        <div className="mt-5 panel p-5 sm:p-6">
          <ol className="space-y-3 text-sm leading-relaxed text-text-dim">
            <li>
              <strong className="text-text">Data.</strong> A public research
              corpus of ~11,200 raw URLs (5,488 phishing / 5,715 legitimate,
              CC-BY-4.0) was validated, de-duplicated and label-normalised.
              Provenance and retrieval date are documented on the{" "}
              <Link to="/model-performance" className="text-info hover:underline">Model Performance</Link> page.
            </li>
            <li>
              <strong className="text-text">Features.</strong> The same 33-feature
              extractor that runs live was applied to every URL — one code path
              for training and inference, so the model never sees features the
              scanner cannot compute.
            </li>
            <li>
              <strong className="text-text">Split.</strong> 20% of the URLs were
              held out as a test set with no website domain in common with the
              training data, because a scanner mostly meets domains it has never
              seen. Random splits would let the model memorise domains and
              overstate its accuracy. The test set was used exactly once.
            </li>
            <li>
              <strong className="text-text">Comparison.</strong> Eight learning
              methods and two simple baselines were compared with domain-grouped
              cross-validation (PR-AUC primary); the strongest were tuned and
              tested for statistically significant differences. Only models whose
              every prediction can be explained exactly were eligible for
              deployment.
            </li>
            <li>
              <strong className="text-text">Evaluation.</strong> The selected
              model reports accuracy, precision, recall, F1, ROC-AUC, PR-AUC and
              a confusion matrix with confidence intervals — plus out-of-source
              checks on fresh phishing feeds and popular legitimate sites that
              expose how far the headline numbers can be trusted.
            </li>
            <li>
              <strong className="text-text">What metrics mean.</strong> Precision
              protects legitimate sites from false alarms; recall protects users
              from missed phishing. Both failure modes are reported honestly —
              neither is hidden.
            </li>
          </ol>
        </div>

        {/* Advanced */}
        <details className="panel mt-8 p-5 sm:p-6">
          <summary className="cursor-pointer text-sm font-semibold text-text">
            Advanced: architecture &amp; feature engineering
          </summary>
          <div className="mt-4 space-y-4 text-xs leading-relaxed text-text-dim">
            <p>
              <span className="font-medium text-text">Stack.</span> React 19 + TypeScript + Vite + Tailwind on the frontend; Python FastAPI + Pydantic on the backend; scikit-learn for the model; SQLite (optional) for scan history behind a swappable service layer.
            </p>
            <p>
              <span className="font-medium text-text">Feature stability.</span> The extractor is versioned (feature schema v1.0.0). Model artefacts record the schema version they were trained with; the API refuses to serve if they mismatch, preventing silent train/serve skew.
            </p>
            <p>
              <span className="font-medium text-text">Explanation maths.</span> For a forest, each tree's predict_proba telescopes along the decision path: P(leaf) = P(root) + Σ (P(child) − P(node)), with each delta attributed to the split feature. Averaging over all trees reproduces the forest's exact probability. For Logistic Regression, contribution = coefficient × standardised value in log-odds space.
            </p>
            <p>
              <span className="font-medium text-text">Safety.</span> No HTTP client exists anywhere in the scan path (SSRF-safe by construction); requests are size-limited and rate-limited; URLs are rendered as inert text in the UI; the browser never navigates to a submitted URL from this app.
            </p>
            <p>
              Full details: <span className="font-mono text-info">ARCHITECTURE.md</span> and{" "}
              <span className="font-mono text-info">MODEL_CARD.md</span> in the repository.
            </p>
          </div>
        </details>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/app/scanner" className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85">
            <Cpu size={16} aria-hidden /> Try the scanner
          </Link>
          <Link to="/model-performance" className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm text-text-dim hover:text-text">
            See the real metrics <ArrowGlyph />
          </Link>
        </div>
      </div>
    </Layout>
  );
}

function ArrowGlyph() {
  return <span aria-hidden>→</span>;
}
