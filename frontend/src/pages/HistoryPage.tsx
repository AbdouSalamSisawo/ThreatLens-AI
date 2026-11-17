import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, History as HistoryIcon, Search, Trash2 } from "lucide-react";
import { Layout } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { api, ApiRequestError } from "../services/api";
import type { HistoryItem, HistoryResponse } from "../types/api";
import { ErrorPanel } from "../components/ErrorPanel";

const PAGE_SIZE = 15;

export function HistoryPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [classification, setClassification] = useState("");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState<HistoryItem | null>(null);

  const load = useCallback(
    async (opts?: { page?: number; search?: string; classification?: string; order?: "desc" | "asc" }) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.history({
          limit: PAGE_SIZE,
          offset: (opts?.page ?? page) * PAGE_SIZE,
          search: opts?.search ?? search,
          classification: opts?.classification ?? classification,
          order: opts?.order ?? order,
        });
        setData(res);
      } catch (err) {
        setError(
          err instanceof ApiRequestError
            ? err
            : new ApiRequestError("Failed to load history.", "unknown", 0),
        );
      } finally {
        setLoading(false);
      }
    },
    [page, search, classification, order],
  );

  useEffect(() => {
    void load({ page });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, classification, order]);

  useEffect(() => {
    const openScan = params.get("scan");
    if (openScan) {
      api
        .getScan(openScan)
        .then((r) =>
          setDetail({
            id: r.scan_id,
            created_at: r.created_at ?? r.scan_timestamp,
            url: r.url,
            classification: r.classification,
            binary_prediction: r.binary_prediction,
            risk_score: r.risk_score,
            probability: r.model_probability,
            model_version: r.model_version,
          }),
        )
        .catch(() => undefined);
    }
  }, [params]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Layout>
      <div className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="panel flex h-11 w-11 items-center justify-center">
              <HistoryIcon size={20} className="text-accent" aria-hidden />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">Scan History</h1>
              <p className="text-sm text-text-dim">
                {data
                  ? `${data.total} record${data.total === 1 ? "" : "s"} · storage mode: ${data.history_mode}`
                  : "Locally stored scan records."}
              </p>
            </div>
          </div>

          {/* Controls */}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <label htmlFor="history-search" className="sr-only">Search stored URLs</label>
              <Search size={15} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
              <input
                id="history-search"
                type="search"
                placeholder="Search stored URLs…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setPage(0);
                    void load({ page: 0, search });
                  }
                }}
                className="h-10 w-full rounded-lg border border-border-strong bg-bg-deep pl-9 pr-3 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
              />
            </div>
            <div className="flex gap-3">
              <div>
                <label htmlFor="history-class" className="sr-only">Filter by classification</label>
                <select
                  id="history-class"
                  value={classification}
                  onChange={(e) => {
                    setClassification(e.target.value);
                    setPage(0);
                  }}
                  className="h-10 rounded-lg border border-border-strong bg-bg-deep px-3 text-sm text-text focus:border-accent focus:outline-none"
                >
                  <option value="">All classifications</option>
                  <option value="likely_benign">Likely benign</option>
                  <option value="suspicious">Suspicious</option>
                  <option value="high_risk">High risk</option>
                </select>
              </div>
              <div>
                <label htmlFor="history-order" className="sr-only">Sort order</label>
                <select
                  id="history-order"
                  value={order}
                  onChange={(e) => setOrder(e.target.value as "desc" | "asc")}
                  className="h-10 rounded-lg border border-border-strong bg-bg-deep px-3 text-sm text-text focus:border-accent focus:outline-none"
                >
                  <option value="desc">Newest first</option>
                  <option value="asc">Oldest first</option>
                </select>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPage(0);
                  void load({ page: 0, search });
                }}
                className="h-10 rounded-lg bg-accent px-4 text-sm font-semibold text-bg hover:bg-accent/85"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6" aria-live="polite">
        {error && <ErrorPanel error={error} />}
        {loading && !data && (
          <div className="panel h-48 animate-pulse bg-surface-2/50" role="status" aria-label="Loading history" />
        )}
        {data && data.scans.length === 0 && !error && (
          <div className="panel flex flex-col items-center gap-3 px-6 py-14 text-center">
            <HistoryIcon size={32} className="text-text-faint" aria-hidden />
            <h2 className="text-base font-semibold text-text">No matching records</h2>
            <p className="max-w-sm text-sm text-text-dim">
              {data.history_mode === "disabled"
                ? "History storage is disabled in the current configuration. Scans work normally — nothing is stored."
                : "Scan a URL to see records here, or adjust the search and filters."}
            </p>
          </div>
        )}
        {data && data.scans.length > 0 && (
          <>
            <div className="panel overflow-hidden">
              <div className="slim-scroll overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="bg-surface-2/60">
                    <tr className="text-text-faint">
                      <th scope="col" className="px-4 py-3 font-medium">URL</th>
                      <th scope="col" className="px-3 py-3 font-medium">Classification</th>
                      <th scope="col" className="px-3 py-3 font-medium">Score</th>
                      <th scope="col" className="px-3 py-3 font-medium">Model</th>
                      <th scope="col" className="px-3 py-3 font-medium">Time</th>
                      <th scope="col" className="px-3 py-3 font-medium"><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.scans.map((s) => (
                      <tr key={s.id} className="transition-colors hover:bg-surface-2/50">
                        <td className="max-w-[320px] px-4 py-3">
                          <button
                            type="button"
                            onClick={() => navigate(`?scan=${s.id}`, { replace: true })}
                            className="block max-w-full truncate text-left font-mono text-[11px] text-info hover:underline"
                            title={s.url}
                          >
                            {s.url}
                          </button>
                        </td>
                        <td className="px-3 py-3"><StatusBadge classification={s.classification} size="sm" /></td>
                        <td className="px-3 py-3 font-mono text-text">{s.risk_score}</td>
                        <td className="px-3 py-3 font-mono text-[11px] text-text-dim">v{s.model_version}</td>
                        <td className="px-3 py-3 text-text-dim">{new Date(s.created_at).toLocaleString()}</td>
                        <td className="px-3 py-3 text-right">
                          <button
                            type="button"
                            aria-label={`Delete scan record ${s.id}`}
                            onClick={async () => {
                              await api.deleteScan(s.id);
                              void load();
                            }}
                            className="rounded p-1.5 text-text-faint transition-colors hover:bg-danger/10 hover:text-danger"
                          >
                            <Trash2 size={14} aria-hidden />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination */}
            <div className="mt-4 flex items-center justify-between text-xs text-text-dim">
              <p>
                Page {page + 1} of {totalPages} · {data.total} total
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 transition-colors hover:text-text disabled:opacity-40"
                >
                  <ChevronLeft size={13} aria-hidden /> Prev
                </button>
                <button
                  type="button"
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 transition-colors hover:text-text disabled:opacity-40"
                >
                  Next <ChevronRight size={13} aria-hidden />
                </button>
              </div>
            </div>
          </>
        )}

        {detail && <DetailDrawer item={detail} onClose={() => setDetail(null)} />}
      </div>
    </Layout>
  );
}

function DetailDrawer({ item, onClose }: { item: HistoryItem; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label="Stored scan details"
      onClick={onClose}
    >
      <div
        className="panel w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-sm font-semibold text-text">Stored scan</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-text-dim hover:text-text"
            aria-label="Close details"
          >
            ✕
          </button>
        </div>
        <p className="url-text mt-3 font-mono text-xs text-info">{item.url}</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <StatusBadge classification={item.classification} />
          <span className="font-mono text-sm text-text">{item.risk_score}/100</span>
        </div>
        <dl className="mt-4 space-y-1.5 text-xs">
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Recorded</dt>
            <dd className="text-text">{new Date(item.created_at).toLocaleString()}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Model version</dt>
            <dd className="font-mono text-text">v{item.model_version}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-text-faint">Model probability</dt>
            <dd className="font-mono text-text">{(item.probability * 100).toFixed(1)}%</dd>
          </div>
        </dl>
        <p className="mt-4 text-[11px] leading-relaxed text-text-faint">
          This record was stored under the configured history policy. Delete it
          from the table, or clear all history, at any time.
        </p>
      </div>
    </div>
  );
}
