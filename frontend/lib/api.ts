import type {
  Answer,
  ChunkRow,
  Community,
  DocumentRow,
  EntityDetail,
  EntitySearchResult,
  EvalReport,
  GraphPath,
  GraphStats,
  Health,
  QueryRequest,
} from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const TENANT = process.env.NEXT_PUBLIC_TENANT ?? "demo";

export class ApiError extends Error {
  readonly status: number;

  // status 0 means the request never got a response (backend down, CORS, DNS).
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const apiMessage = (error: unknown) =>
  error instanceof ApiError ? (error.status ? `${error.status} · ${error.message}` : "Could not reach the API.") : "Unexpected error.";

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Non-JSON error bodies fall back to the status text.
  }
  return response.statusText || `HTTP ${response.status}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Tenant", TENANT);
  if (init.body) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network error");
  }
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response));
  return (await response.json()) as T;
}

const segment = encodeURIComponent;

export const api = {
  query: (body: QueryRequest, signal?: AbortSignal) =>
    request<Answer>("/query", { method: "POST", body: JSON.stringify(body), signal }),
  document: (docId: string, signal?: AbortSignal) =>
    request<DocumentRow>(`/documents/${segment(docId)}`, { signal }),
  chunk: (chunkId: string, signal?: AbortSignal) =>
    request<ChunkRow>(`/chunks/${segment(chunkId)}`, { signal }),
  entity: (entityId: string, signal?: AbortSignal) =>
    request<EntityDetail>(`/graph/entity/${segment(entityId)}`, { signal }),
  path: (from: string, to: string, signal?: AbortSignal) =>
    request<GraphPath | null>(`/graph/path?${new URLSearchParams({ from, to })}`, { signal }),
  search: (q: string, limit = 10, signal?: AbortSignal) =>
    request<EntitySearchResult[]>(
      `/graph/search?${new URLSearchParams({ q, limit: String(limit) })}`,
      { signal },
    ),
  graphStats: (signal?: AbortSignal) => request<GraphStats>("/graph/stats", { signal }),
  communities: (level: 0 | 1 = 0, signal?: AbortSignal) =>
    request<Community[]>(`/communities?level=${level}`, { signal }),
  evalReport: (signal?: AbortSignal) => request<EvalReport>("/eval/report", { signal }),
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
};
