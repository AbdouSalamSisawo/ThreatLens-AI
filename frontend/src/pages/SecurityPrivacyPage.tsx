import { Link } from "react-router-dom";
import {
  Database,
  EyeOff,
  FileWarning,
  Lock,
  Network,
  Server,
  ShieldAlert,
  Trash2,
  Wifi,
} from "lucide-react";
import { Layout } from "../components/Layout";

export function SecurityPrivacyPage() {
  return (
    <Layout>
      <div className="border-b border-border">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <Lock size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">
                Security &amp; Privacy
              </h1>
              <p className="text-sm text-text-dim">
                What this prototype actually does with data — every statement here maps to implemented code.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl space-y-6 px-4 py-10 sm:px-6">
        {/* What the scanner analyses */}
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Server size={18} className="text-accent" aria-hidden />
            What the scanner analyses
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            Only the URL <strong className="text-text">string itself</strong>.
            The backend parses the text you submit and computes 57 lexical
            features from it — lengths, character counts, hostname structure,
            encoding, tokens. A trained tree-ensemble model then classifies those
            features. No page content, no screenshots, no redirects are
            resolved, no cookies or credentials are collected, and no browser
            profile is touched.
          </p>
        </section>

        {/* No fetching */}
        <section className="panel border-accent/25 p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Wifi size={18} className="text-accent" aria-hidden />
            The destination website is never contacted
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            There is no HTTP client anywhere in the scan code path. The scanner
            cannot visit, fetch, resolve or render the submitted URL — which
            removes an entire class of server-side request forgery (SSRF) risks
            and means the analysis never alerts the operator of a malicious
            site. It also defines the tool's honest boundary:{" "}
            <strong className="text-text">
              URL-only analysis cannot see what a website actually serves.
            </strong>
          </p>
        </section>

        {/* Storage */}
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Database size={18} className="text-accent" aria-hidden />
            Whether scans are stored, and how to delete them
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            Storage is configurable in the backend <span className="font-mono text-info">.env</span>:
          </p>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li className="flex gap-2.5">
              <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="font-mono text-text">HISTORY_MODE=sqlite</span> (default): scan records stay in a local database file, capped at the most recent 500 entries. Each record stores the URL, classification, score, probability, timestamp, model version and the full result JSON so a scan can be reopened.</span>
            </li>
            <li className="flex gap-2.5">
              <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="font-mono text-text">HISTORY_MODE=memory</span>: records live in RAM only and vanish when the server restarts.</span>
            </li>
            <li className="flex gap-2.5">
              <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="font-mono text-text">HISTORY_MODE=disabled</span>: nothing is stored anywhere; the scanner works exactly the same.</span>
            </li>
          </ul>
          <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-text-dim">
            <Trash2 size={16} className="mt-0.5 shrink-0 text-info" aria-hidden />
            Individual records and the entire history can be deleted from the{" "}
            <Link to="/app/history" className="text-info hover:underline">History</Link> page or the DELETE API endpoints at any time.
            This prototype is single-user: history is local to the deployment and no accounts exist.
          </p>
        </section>

        {/* External providers */}
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Network size={18} className="text-accent" aria-hidden />
            What is sent to external providers
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            <strong className="text-text">Nothing.</strong> No threat-intelligence
            provider is integrated; no generative-AI service is used at scan
            time; no submitted URL ever leaves the deployment. The result panel
            reports the threat-intelligence status as{" "}
            <span className="font-mono text-xs text-warn">unavailable — not integrated</span>{" "}
            rather than simulating a lookup. If a provider is added in the
            future, that will be a separate, documented data-flow decision.
          </p>
        </section>

        {/* What the system cannot determine */}
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <EyeOff size={18} className="text-accent" aria-hidden />
            What the system cannot determine
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li>• Whether the destination page is malicious — the site is never visited.</li>
            <li>• Whether a domain has a known bad or good reputation.</li>
            <li>• Whether novel phishing techniques that differ from the training data will be caught.</li>
            <li>• Whether the estimated probability reflects real-world risk — it is uncalibrated.</li>
            <li>• Intent. A suspicious-looking URL is not proof of malicious intent, and a clean-looking URL is not proof of safety.</li>
          </ul>
        </section>

        {/* Model limitations */}
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <ShieldAlert size={18} className="text-accent" aria-hidden />
            Known model limitations
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li>• The classifier makes mistakes in both directions; see the published confusion matrix.</li>
            <li>• The training corpus is a public research snapshot — real-world traffic mix and current campaigns differ.</li>
            <li>• Dataset bias affects performance: benign URLs skew towards well-known sites, so less-famous legitimate sites with unusual structures are more likely to be flagged.</li>
            <li>• Lexical signals can be trivially changed by attackers; the model must be retrained regularly to stay relevant.</li>
            <li>• Classification bands are decision aids, not measured risk levels.</li>
          </ul>
        </section>

        {/* Responsible use */}
        <section className="panel border-warn/25 p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <FileWarning size={18} className="text-warn" aria-hidden />
            Responsible-use guidance
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li>• Treat ThreatLens as one signal among several — never as a permission to trust a link.</li>
            <li>• Verify domains through independently obtained official sources (type them yourself, or use a bookmark).</li>
            <li>• Report suspected phishing through your institution's official process (at AIU: the campus IT service desk).</li>
            <li>• Never enter credentials or payment details into a page you reached via an unverified link.</li>
            <li>• Never open a suspicious link “to check it” — including to test this tool.</li>
          </ul>
        </section>

        {/* Data protection note */}
        <section className="panel p-5 sm:p-6">
          <h2 className="text-base font-semibold text-text">
            A note on data protection (Malaysia)
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            This prototype processes URL strings locally and stores, at most,
            the scan records described above. It is designed to minimise
            personal-data exposure, consistent with data-protection good
            practice and with the principles of Malaysia's Personal Data
            Protection Act 2010 (PDPA). This statement is an engineering
            description, <strong className="text-text">not legal advice or a
            compliance certification</strong>: no regulatory approval is claimed
            or implied. Operators deploying the tool in production should
            conduct their own data-protection assessment.
          </p>
        </section>
      </div>
    </Layout>
  );
}
