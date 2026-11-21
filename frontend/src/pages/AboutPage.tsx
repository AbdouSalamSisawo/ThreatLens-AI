import { Link } from "react-router-dom";
import { GraduationCap, MapPin, Rocket, Target, Users } from "lucide-react";
import { Layout } from "../components/Layout";

export function AboutPage() {
  return (
    <Layout>
      <div className="border-b border-border">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <GraduationCap size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">
                About the Project
              </h1>
              <p className="text-sm text-text-dim">
                ThreatLens AI is a student-built cybersecurity prototype.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl space-y-6 px-4 py-10 sm:px-6">
        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Target size={18} className="text-accent" aria-hidden /> The problem
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            Phishing attacks use deceptive URLs to trick people into revealing
            credentials or visiting fraudulent websites. University students
            and other non-technical internet users are frequent targets,
            particularly when a message appears to come from a trusted
            institution — a bursary notice, a “blocked account”, a scholarship
            portal. Most users have no practical way to inspect a link before
            clicking, and the tools that exist either give a bare verdict with
            no reasoning, or send the link to someone else's cloud.
          </p>
        </section>

        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Users size={18} className="text-accent" aria-hidden /> Intended users
          </h2>
          <ul className="mt-3 grid gap-2 text-sm leading-relaxed text-text-dim sm:grid-cols-2">
            <li>• University students checking links from email or chat.</li>
            <li>• Lecturers and university staff handling administrative mail.</li>
            <li>• Non-technical internet users who want explanations, not just verdicts.</li>
            <li>• Campus IT and cybersecurity awareness teams running training.</li>
          </ul>
        </section>

        <section className="panel p-5 sm:p-6">
          <h2 className="text-base font-semibold text-text">Technical approach &amp; the role of explainable ML</h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            The system pairs a supervised classifier (a tree ensemble over 57
            lexical URL features) with an explanation layer that decomposes
            every prediction into exact per-feature contributions and
            human-readable observations. Explainability is not a bolt-on: it
            shapes the model selection policy (only models whose every prediction
            can be explained exactly are eligible for deployment), the result
            interface, and the safety guidance, which is derived from evidence
            rather than from the verdict alone. The campus cyber-safety impact
            is intended to be double: better decisions about individual links,
            and better-trained instincts about the signals of phishing.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            Full methodology: <Link to="/how-it-works" className="text-info hover:underline">How It Works</Link> ·{" "}
            <Link to="/model-performance" className="text-info hover:underline">Model Performance</Link>.
          </p>
        </section>

        <section className="panel p-5 sm:p-6">
          <h2 className="text-base font-semibold text-text">Prototype limitations</h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li>• Single-user prototype: no accounts, no multi-user history isolation.</li>
            <li>• URL-lexical only: page content and behaviour are out of scope by design.</li>
            <li>• No live threat-intelligence integration; the status is reported honestly rather than simulated.</li>
            <li>• The model requires periodic retraining as phishing techniques evolve.</li>
            <li>• In-process rate limiting suits single-instance deployment only.</li>
          </ul>
        </section>

        <section className="panel p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text">
            <Rocket size={18} className="text-accent" aria-hidden /> Potential future development
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-dim">
            <li>• Optional Google Safe Browsing / PhishTank integration with explicit data-flow disclosure.</li>
            <li>• Scheduled retraining pipeline with drift monitoring on fresh feeds.</li>
            <li>• Probability calibration and per-band threshold tuning with campus feedback.</li>
            <li>• Campus reporting integration: one-click submission of flagged URLs to the IT service desk.</li>
            <li>• Multi-user deployment with authentication and per-user history isolation.</li>
          </ul>
        </section>

        <section className="panel p-5 sm:p-6">
          <h2 className="text-base font-semibold text-text">Technology stack</h2>
          <dl className="mt-4 grid gap-4 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-medium uppercase tracking-wider text-text-faint">Frontend</dt>
              <dd className="mt-1 leading-relaxed text-text-dim">
                React 19, TypeScript, Vite, Tailwind CSS, Lucide icons, Recharts, Framer Motion (subtle, reduced-motion aware)
              </dd>
            </div>
            <div>
              <dt className="font-medium uppercase tracking-wider text-text-faint">Backend</dt>
              <dd className="mt-1 leading-relaxed text-text-dim">
                Python 3.12, FastAPI, Pydantic, scikit-learn, pandas/NumPy, joblib, SQLite (optional), pytest
              </dd>
            </div>
            <div>
              <dt className="font-medium uppercase tracking-wider text-text-faint">Machine learning</dt>
              <dd className="mt-1 leading-relaxed text-text-dim">
                Tree-ensemble classifier selected from eight learners under domain-grouped cross-validation, exact tree-path explanations, versioned feature schema
              </dd>
            </div>
            <div>
              <dt className="font-medium uppercase tracking-wider text-text-faint">Data</dt>
              <dd className="mt-1 leading-relaxed text-text-dim">
                Public research phishing-URL corpus (CC-BY-4.0), OpenPhish free feed &amp; Majestic Million (out-of-source probes) — full provenance in the AI &amp; Data Declaration
              </dd>
            </div>
          </dl>
        </section>

        {/* Team placeholders - names deliberately not invented */}
        <section className="panel p-5 sm:p-6">
          <h2 className="text-base font-semibold text-text">Team</h2>
          <p className="mt-3 text-sm leading-relaxed text-text-dim">
            The project is developed by a student team at the{" "}
            <strong className="text-text">School of Computing &amp; Informatics, Albukhary International University (AIU)</strong>{" "}
            for the <strong className="text-text">MMC Upstart 2026 Catalyst: Igniting Future Innovation</strong> competition.
            Team member names, roles and contributions will be listed here once
            finalised.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="panel-inset flex items-center gap-3 px-4 py-3 opacity-70">
                <span className="flex h-9 w-9 items-center justify-center rounded-full border border-dashed border-border-strong text-text-faint" aria-hidden>
                  ?
                </span>
                <div>
                  <p className="text-sm text-text-faint">Team member {i + 1}</p>
                  <p className="text-[11px] text-text-faint">name &amp; role — placeholder</p>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 flex items-start gap-2 text-[11px] leading-relaxed text-text-faint">
            <MapPin size={13} className="mt-0.5 shrink-0" aria-hidden />
            Educational and research-oriented purpose. No institutional
            endorsement, certification or partnership is claimed; competition
            entry status does not imply approval by MMC or AIU.
          </p>
        </section>
      </div>
    </Layout>
  );
}
