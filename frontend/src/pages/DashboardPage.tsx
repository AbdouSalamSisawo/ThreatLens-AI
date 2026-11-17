import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Database,
  LayoutDashboard,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Layout } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { api, ApiRequestError } from "../services/api";
import type { DashboardData } from "../types/api";
import { ErrorPanel } from "../components/ErrorPanel";
import { useAuth } from "../auth/AuthProvider";

const CLASS_COLORS: Record<string, string> = {
  likely_benign: "#4ade80",
  suspicious: "#e8b64c",
  high_risk: "#f0716c",
};

function DashboardGreeting() {
  const { user, profile, profileLoading } = useAuth();
  const displayName =
    profile?.display_name ?? user?.user_metadata?.display_name ?? null;
  const fallback = user?.email ? user.email.split("@")[0] : "Analyst";
  return (
    <h1 className="text-2xl font-semibold tracking-tight text-text">
      {profileLoading ? "Welcome back" : `Welcome back, ${displayName || fallback}`}
    </h1>
  );
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.dashboard());
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? err
          : new ApiRequestError("Failed to load dashboard.", "unknown", 0),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Layout>
      <div className="border-b border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-8 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <LayoutDashboard size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <DashboardGreeting />
              <p className="text-sm text-text-dim">
                Every number below comes from your own records and the verified model artefacts.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-text-dim transition-colors hover:border-accent/40 hover:text-text"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} aria-hidden />
            Refresh
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6" aria-live="polite">
        {error && <ErrorPanel error={error} />}
        {loading && !data && !error && (
          <div className="grid gap-4 sm:grid-cols-3" role="status" aria-label="Loading dashboard">
            {[0, 1, 2].map((i) => (
              <div key={i} className="panel h-28 animate-pulse bg-surface-2/50" />
            ))}
          </div>
        )}
        {data && <DashboardContent data={data} onChanged={load} />}
      </div>
    </Layout>
  );
}

function DashboardContent({ data, onChanged }: { data: DashboardData; onChanged: () => void }) {
  const navigate = useNavigate();
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const hasScans = data.total_scans > 0;
  const test = data.model.test_metrics && "accuracy" in data.model.test_metrics
    ? data.model.test_metrics
    : null;

  const distData = data.classification_distribution.filter((d) => d.count > 0);

  async function clearAll() {
    setClearing(true);
    try {
      await api.clearHistory();
      setConfirmClear(false);
      onChanged();
    } catch {
      /* surfaced on next refresh */
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Policy note */}
      <div className="panel flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <p className="flex items-center gap-2 text-xs text-text-dim">
          <Database size={14} className="text-info" aria-hidden />
          History mode: <span className="font-mono text-text">{data.history_mode}</span>
          {data.history_mode === "sqlite" && " — records stored locally, capped and deletable."}
          {data.history_mode === "memory" && " — kept in RAM only, cleared on restart."}
          {data.history_mode === "disabled" && " — nothing is stored."}
        </p>
        {hasScans && (
          <button
            type="button"
            onClick={() => (confirmClear ? void clearAll() : setConfirmClear(true))}
            disabled={clearing}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors ${
              confirmClear
                ? "border-danger/60 bg-danger/10 text-danger"
                : "border-border text-text-dim hover:border-danger/40 hover:text-danger"
            }`}
          >
            <Trash2 size={13} aria-hidden />
            {confirmClear ? "Click again to confirm delete ALL history" : "Clear all history"}
          </button>
        )}
      </div>

      {!hasScans ? (
        <div className="panel flex flex-col items-center gap-4 px-6 py-16 text-center">
          <Activity size={36} className="text-text-faint" aria-hidden />
          <div>
            <h2 className="text-lg font-semibold text-text">No scans recorded yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-text-dim">
              This dashboard shows only real scan activity from the configured
              history store — it deliberately contains no sample or demo
              numbers. Analyse a URL and this page will populate with actual
              results.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/app/scanner")}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
          >
            <ShieldCheck size={16} aria-hidden />
            Analyse your first URL
          </button>
        </div>
      ) : (
        <>
          {/* KPI row */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Total scans" value={String(data.total_scans)} sub="from the local history store" />
            {(["likely_benign", "suspicious", "high_risk"] as const).map((c) => (
              <Kpi
                key={c}
                label={c === "likely_benign" ? "Likely benign" : c === "suspicious" ? "Suspicious" : "High risk"}
                value={String(data.by_classification[c] ?? 0)}
                color={CLASS_COLORS[c]}
              />
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-5">
            {/* Distribution */}
            <div className="panel p-5 lg:col-span-2">
              <h2 className="text-sm font-semibold text-text">Classification distribution</h2>
              {distData.length === 0 ? (
                <p className="mt-6 text-sm text-text-faint">No data.</p>
              ) : (
                <div className="mt-4 h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={distData}
                        dataKey="count"
                        nameKey="classification"
                        innerRadius={55}
                        outerRadius={85}
                        paddingAngle={3}
                        stroke="#0B1016"
                      >
                        {distData.map((d) => (
                          <Cell key={d.classification} fill={CLASS_COLORS[d.classification] ?? "#66B9FF"} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "#121A23",
                          border: "1px solid #1F2B38",
                          borderRadius: 8,
                          fontSize: 12,
                          color: "#EAF0F6",
                        }}
                        formatter={(v, n) => [`${v} scans`, String(n)]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-text-dim">
                {distData.map((d) => (
                  <span key={d.classification} className="inline-flex items-center gap-1.5">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ background: CLASS_COLORS[d.classification] }}
                      aria-hidden
                    />
                    {d.classification.replace("_", " ")} ({d.count})
                  </span>
                ))}
              </div>
            </div>

            {/* Model summary */}
            <div className="panel p-5 lg:col-span-3">
              <h2 className="text-sm font-semibold text-text">Model evaluation summary</h2>
              {!data.model.available ? (
                <p className="mt-4 text-sm text-warn">
                  Model not loaded — start the backend with trained artefacts.
                </p>
              ) : (
                <>
                  <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2.5 text-xs sm:grid-cols-3">
                    <Meta label="Model" value={data.model.selected_model ?? "—"} />
                    <Meta label="Version" value={data.model.model_version ?? "—"} />
                    <Meta
                      label="Trained"
                      value={data.model.trained_at ? new Date(data.model.trained_at).toLocaleDateString() : "—"}
                    />
                    {test && (
                      <>
                        <Meta label="Accuracy" value={(test.accuracy * 100).toFixed(1) + "%"} accent />
                        <Meta label="Precision" value={(test.precision * 100).toFixed(1) + "%"} accent />
                        <Meta label="Recall" value={(test.recall * 100).toFixed(1) + "%"} accent />
                        <Meta label="F1" value={(test.f1 * 100).toFixed(1) + "%"} accent />
                        {test.pr_auc != null && (
                          <Meta label="PR-AUC" value={test.pr_auc.toFixed(3)} accent />
                        )}
                        {test.roc_auc != null && (
                          <Meta label="ROC-AUC" value={test.roc_auc.toFixed(3)} accent />
                        )}
                      </>
                    )}
                  </dl>
                  <Link
                    to="/model-performance"
                    className="mt-4 inline-flex items-center gap-1.5 text-xs text-info hover:underline"
                  >
                    Full evaluation details <ArrowRight size={12} aria-hidden />
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* Recent scans */}
          <div className="panel p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text">Recent scans</h2>
              <Link to="/app/history" className="text-xs text-info hover:underline">
                View all ({data.total_scans})
              </Link>
            </div>
            <div className="slim-scroll mt-4 max-h-96 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-text-faint">
                    <th scope="col" className="py-2 pr-3 font-medium">URL</th>
                    <th scope="col" className="py-2 pr-3 font-medium">Classification</th>
                    <th scope="col" className="py-2 pr-3 font-medium">Score</th>
                    <th scope="col" className="py-2 font-medium">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.recent_scans.map((s) => (
                    <tr
                      key={s.id}
                      className="cursor-pointer transition-colors hover:bg-surface-2/60"
                      onClick={() => navigate(`/app/history?scan=${s.id}`)}
                    >
                      <td className="max-w-[280px] truncate py-2.5 pr-3 font-mono text-[11px] text-text">
                        {s.url}
                      </td>
                      <td className="py-2.5 pr-3"><StatusBadge classification={s.classification} size="sm" /></td>
                      <td className="py-2.5 pr-3 font-mono text-text">{s.risk_score}</td>
                      <td className="py-2.5 text-text-dim">
                        {new Date(s.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bar chart */}
          <div className="panel p-5">
            <h2 className="text-sm font-semibold text-text">Scans by classification</h2>
            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.classification_distribution}>
                  <XAxis
                    dataKey="classification"
                    tick={{ fill: "#9BA9B8", fontSize: 11 }}
                    tickFormatter={(v: string) => v.replace("_", " ")}
                    axisLine={{ stroke: "#1F2B38" }}
                    tickLine={false}
                  />
                  <YAxis allowDecimals={false} tick={{ fill: "#9BA9B8", fontSize: 11 }} axisLine={{ stroke: "#1F2B38" }} tickLine={false} width={32} />
                  <Tooltip
                    cursor={{ fill: "rgba(102,185,255,0.06)" }}
                    contentStyle={{
                      background: "#121A23",
                      border: "1px solid #1F2B38",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "#EAF0F6",
                    }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {data.classification_distribution.map((d) => (
                      <Cell key={d.classification} fill={CLASS_COLORS[d.classification] ?? "#66B9FF"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="panel px-5 py-4">
      <p className="text-[11px] font-medium uppercase tracking-wider text-text-faint">{label}</p>
      <p className="mt-1.5 font-mono text-3xl font-semibold" style={{ color: color ?? "#EAF0F6" }}>
        {value}
      </p>
      {sub && <p className="mt-1 text-[11px] text-text-faint">{sub}</p>}
    </div>
  );
}

function Meta({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <dt className="text-text-faint">{label}</dt>
      <dd className={`mt-0.5 font-mono ${accent ? "text-accent" : "text-text"}`}>{value}</dd>
    </div>
  );
}
