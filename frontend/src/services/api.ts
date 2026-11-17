/* API client - relative paths only (same origin; vite dev proxies /api).

   Protected requests carry "Authorization: Bearer <access_token>" from the
   Supabase session (see auth/authToken.ts). A 401 triggers the registered
   unauthorized handler (silent session refresh); the failing request is
   retried once if a fresh token became available in the meantime. */

import type {
  ApiError,
  DashboardData,
  HistoryResponse,
  ModelInfo,
  FullMetrics,
  ProfileResponse,
  ReadyData,
  ScanResult,
} from "../types/api";
import { getAccessToken, notifyUnauthorized } from "../auth/authToken";

export class ApiRequestError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  path: string,
  init?: RequestInit & { _retried?: boolean },
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiRequestError(
      "Could not reach the ThreatLens backend. Check that the API server is running.",
      "network_error",
      0,
    );
  }

  // Expired/invalid session: give the auth provider one chance to refresh.
  if (
    response.status === 401 &&
    !init?._retried &&
    (init?.method ?? "GET") !== "GET"
  ) {
    notifyUnauthorized();
    await new Promise((r) => setTimeout(r, 700));
    if (getAccessToken()) {
      return request<T>(path, { ...init, _retried: true });
    }
  }

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    const err = (body as ApiError | null)?.error;
    if (response.status === 401) notifyUnauthorized();
    throw new ApiRequestError(
      err?.message ?? `Request failed (HTTP ${response.status}).`,
      err?.code ?? "http_error",
      response.status,
      err?.details,
    );
  }
  return body as T;
}

export const api = {
  ready: () => request<ReadyData>("/api/ready"),
  scan: (url: string) =>
    request<ScanResult>("/api/scan", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  modelInfo: () => request<ModelInfo>("/api/model-info"),
  modelMetrics: () => request<FullMetrics>("/api/model-info/metrics"),
  dashboard: () => request<DashboardData>("/api/dashboard"),
  profile: () => request<ProfileResponse>("/api/profile"),
  history: (params: {
    limit?: number;
    offset?: number;
    classification?: string;
    search?: string;
    order?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.limit != null) q.set("limit", String(params.limit));
    if (params.offset != null) q.set("offset", String(params.offset));
    if (params.classification) q.set("classification", params.classification);
    if (params.search) q.set("search", params.search);
    if (params.order) q.set("order", params.order);
    return request<HistoryResponse>(`/api/history?${q.toString()}`);
  },
  getScan: (id: string) => request<ScanResult & { created_at: string }>(`/api/history/${id}`),
  deleteScan: (id: string) =>
    request<{ deleted: boolean }>(`/api/history/${id}`, { method: "DELETE" }),
  clearHistory: () =>
    request<{ deleted: boolean; deleted_count: number | null }>("/api/history", {
      method: "DELETE",
    }),
};
