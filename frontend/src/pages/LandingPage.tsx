import { Link } from "react-router-dom";
import { useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  Eye,
  Gauge,
  History,
  Lock,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { Layout } from "../components/Layout";
import { useAuth } from "../auth/AuthProvider";

/* Restrained network-node visual: a static topology with a slow radar sweep.
   It communicates "local analysis" — nothing here pretends to query the web. */
function HeroVisual() {
  const reduce = useReducedMotion();
  const nodes = [
    { cx: 32, cy: 32, r: 3, core: true },
    { cx: 90, cy: 22, r: 2 },
    { cx: 140, cy: 48, r: 2.5 },
    { cx: 72, cy: 86, r: 2 },
    { cx: 130, cy: 98, r: 2 },
    { cx: 42, cy: 120, r: 2.5 },
    { cx: 168, cy: 84, r: 2 },
    { cx: 106, cy: 128, r: 2 },
  ];
  const links: [number, number][] = [
    [0, 1], [1, 2], [0, 3], [2, 4], [3, 5], [2, 6], [4, 7], [0, 2], [3, 1],
  ];
  return (
    <svg
      viewBox="0 0 200 150"
      className="h-full w-full"
      role="img"
      aria-label="Illustration of URLs being analysed locally by the ThreatLens model"
    >
      <defs>
        <linearGradient id="tl-link" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#38D9C3" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#66B9FF" stopOpacity="0.25" />
        </linearGradient>
        <radialGradient id="tl-core" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#38D9C3" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#38D9C3" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="32" cy="32" r="58" fill="url(#tl-core)" />
      {links.map(([a, b], i) => (
        <line
          key={i}
          x1={nodes[a].cx}
          y1={nodes[a].cy}
          x2={nodes[b].cx}
          y2={nodes[b].cy}
          stroke="url(#tl-link)"
          strokeWidth="1"
        />
      ))}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle
            cx={n.cx}
            cy={n.cy}
            r={n.r}
            fill={n.core ? "#38D9C3" : "#66B9FF"}
            className={reduce ? "" : i % 3 === 0 ? "pulse-dot" : ""}
            style={n.core ? { filter: "drop-shadow(0 0 6px rgba(56,217,195,0.8))" } : undefined}
          />
        </g>
      ))}
      {/* radar sweep over the core node */}
      <g className={reduce ? "" : "radar-sweep"} style={{ transformOrigin: "32px 32px" }}>
        <line x1="32" y1="32" x2="90" y2="32" stroke="#38D9C3" strokeOpacity="0.55" strokeWidth="1.5" />
        <circle cx="32" cy="32" r="14" fill="none" stroke="#38D9C3" strokeOpacity="0.3" strokeWidth="1" />
        <circle cx="32" cy="32" r="24" fill="none" stroke="#38D9C3" strokeOpacity="0.18" strokeWidth="1" />
        <circle cx="32" cy="32" r="34" fill="none" stroke="#38D9C3" strokeOpacity="0.1" strokeWidth="1" />
      </g>
    </svg>
  );
}

const PIPELINE = [
  { step: 1, title: "Submit a URL", desc: "You paste a link into the scanner." },
  { step: 2, title: "Validate & parse", desc: "The backend re-validates the input and parses its structure. The site is never visited." },
  { step: 3, title: "Extract features", desc: "57 lexical characteristics — lengths, tokens, encoding, hostname structure — are computed locally." },
  { step: 4, title: "Run the model", desc: "A trained tree-ensemble classifier scores the feature vector and outputs an estimated probability." },
  { step: 5, title: "Explain the result", desc: "Exact per-feature contributions and observed signals show why the decision was made." },
  { step: 6, title: "Guide the response", desc: "Proportionate safety recommendations follow the evidence — never “open the link to check”." },
];

const FEATURES = [
  { icon: ScanSearch, title: "ML-based URL classification", desc: "A tree-ensemble model trained on 11,000+ labelled URLs from a public research corpus scores every submission." },
  { icon: Eye, title: "Explainable indicators", desc: "Observed characteristics and exact feature contributions — no black box, no invented evidence." },
  { icon: BarChart3, title: "Model performance transparency", desc: "Real held-out evaluation metrics, confusion matrix, and honest generalisation checks are published, not promised." },
  { icon: Lock, title: "Privacy-conscious processing", desc: "URL strings are analysed locally. The destination website is never contacted, and history retention is configurable." },
  { icon: History, title: "Scan history (optional)", desc: "Capped, searchable, deletable history with a privacy-strict disabled mode." },
  { icon: BookOpenCheck, title: "Phishing awareness", desc: "Every result teaches the signals behind the verdict so users get better at spotting links themselves." },
];

export function LandingPage() {
  const { status } = useAuth();
  const authed = status === "authenticated";

  return (
    <Layout>
      {/* Hero */}
      <section className="grid-bg border-b border-border">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.2fr_0.8fr] lg:py-20">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/5 px-3 py-1 text-xs text-accent">
              <Sparkles size={12} aria-hidden />
              Student-built · MMC Upstart 2026 Catalyst
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight text-text sm:text-5xl">
              See the Signals Behind{" "}
              <span className="text-accent">Suspicious Links.</span>
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-text-dim sm:text-lg">
              Analyse a URL, understand the warning signs, and make a more
              informed decision before you interact with a suspicious link —
              inside your own private security workspace.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link
                to={authed ? "/app/scanner" : "/signup"}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-bg transition-colors hover:bg-accent/85"
              >
                <ScanSearch size={16} aria-hidden />
                {authed ? "Open the scanner" : "Get Started — create your workspace"}
              </Link>
              {!authed && (
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 rounded-lg border border-border-strong bg-surface-2 px-6 py-3 text-sm font-medium text-text transition-colors hover:bg-border/30"
                >
                  Sign in
                </Link>
              )}
            </div>
            <p className="mt-3 text-xs text-text-faint">
              Free student prototype · Your scans stay private to your account ·
              The destination website is never contacted.
            </p>
          </div>
          <div className="mx-auto hidden w-full max-w-sm lg:block" aria-hidden>
            <div className="panel ticks p-4">
              <div className="panel-inset h-64 p-2">
                <HeroVisual />
              </div>
              <p className="mt-3 text-center font-mono text-[11px] text-text-faint">
                local lexical analysis · no destination fetching
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Labelled illustrative preview (no live scanning on the public page) */}
      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <IllustrativePreview />
        <div className="mt-6 flex flex-col items-center gap-3 text-center">
          <p className="max-w-xl text-sm leading-relaxed text-text-dim">
            The scanner lives inside your account. Create a free workspace to
            run real analyses with full, saved evidence for every URL.
          </p>
          <Link
            to={authed ? "/app/scanner" : "/signup"}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-bg transition-colors hover:bg-accent/85"
          >
            <ScanSearch size={16} aria-hidden />
            {authed ? "Scan a URL" : "Analyse your first URL"}
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-border bg-bg-deep/60">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-text">
            How it works
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-dim">
            The real pipeline, in order. Every stage runs on the server and
            every claim maps to implemented code.
          </p>
          <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PIPELINE.map((p) => (
              <li key={p.step} className="panel p-5">
                <span className="font-mono text-xs text-accent">
                  {String(p.step).padStart(2, "0")}
                </span>
                <h3 className="mt-2 text-sm font-semibold text-text">{p.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-text-dim">{p.desc}</p>
              </li>
            ))}
          </ol>
          <Link
            to="/how-it-works"
            className="mt-6 inline-flex items-center gap-1.5 text-sm text-info hover:underline"
          >
            Full methodology <ArrowRight size={14} aria-hidden />
          </Link>
        </div>
      </section>

      {/* Feature overview */}
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-2xl font-semibold tracking-tight text-text">
          What the system actually does
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="panel p-5">
              <f.icon size={20} className="text-accent" aria-hidden />
              <h3 className="mt-3 text-sm font-semibold text-text">{f.title}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-text-dim">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Responsible use */}
      <section className="border-t border-border bg-bg-deep/60">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="panel border-warn/25 p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <ShieldAlert size={24} className="mt-1 shrink-0 text-warn" aria-hidden />
              <div>
                <h2 className="text-lg font-semibold text-text">Responsible use</h2>
                <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-dim">
                  ThreatLens AI is an <strong className="text-text">assistive screening system</strong>,
                  not a definitive security verdict. The classifier can make
                  mistakes, novel phishing techniques may differ from its
                  training data, and a benign prediction is never a guarantee
                  that a site is safe. Treat every unexpected link with
                  caution, verify domains through independently obtained
                  official sources, and report suspected phishing through your
                  institution's official process.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    to="/app/scanner"
                    className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85"
                  >
                    <ShieldCheck size={16} aria-hidden />
                    Analyse a URL
                  </Link>
                  <Link
                    to="/model-performance"
                    className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm text-text-dim transition-colors hover:text-text"
                  >
                    <Gauge size={16} aria-hidden />
                    See real model metrics
                  </Link>
                  <Link
                    to="/security-privacy"
                    className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm text-text-dim transition-colors hover:text-text"
                  >
                    <Waypoints size={16} aria-hidden />
                    Security &amp; privacy
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </Layout>
  );
}

/* Clearly-labelled illustrative preview - NOT a real scan, not counted. */
function IllustrativePreview() {
  return (
    <div className="panel relative overflow-hidden p-5 sm:p-6">
      <span className="absolute right-4 top-4 rounded-full border border-warn/40 bg-warn/10 px-3 py-1 text-[11px] font-medium text-warn">
        Illustrative example — not a real scan
      </span>
      <h2 className="text-sm font-semibold text-text">What a result looks like</h2>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="panel-inset p-4">
          <p className="font-mono text-xs text-text-dim url-text">
            http://secure-login.verify-account.example.com/webscr/confirm
          </p>
          <div className="mt-3 flex items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-1.5 text-sm font-medium text-danger">
              <ShieldAlert size={15} aria-hidden /> High risk
            </span>
            <span className="font-mono text-2xl font-semibold text-danger">91<span className="text-xs text-text-faint">/100</span></span>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-text-dim">
            Example observation: “A well-known brand token appears in the URL
            but not in the actual registrable domain — a common impersonation
            pattern.”
          </p>
        </div>
        <div className="panel-inset p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-text-faint">
            Model evidence (example)
          </p>
          <div className="mt-3 space-y-2.5">
            {[
              ["Security-themed wording", 82, "toward phishing"],
              ["Deep subdomain nesting", 64, "toward phishing"],
              ["No HTTPS", 41, "toward phishing"],
            ].map(([label, w, dir]) => (
              <div key={label as string}>
                <div className="flex justify-between text-[11px]">
                  <span className="text-text">{label}</span>
                  <span className="text-danger">{dir}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-border">
                  <div className="h-full rounded-full bg-danger/80" style={{ width: `${w}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-4 text-xs text-text-faint">
        This panel is a static illustration for first-time visitors — not live
        output. Sign in to run real scans; results come only from the actual
        trained model.
      </p>
    </div>
  );
}
