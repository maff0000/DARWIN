import type {
  BuildInfo,
  DiscoverySort,
  InstrumentDefinition,
  IntakeStatus,
  MarketDataset,
  MigrationState,
  PipelineSummary,
  ReadinessReport,
  ResearchRun,
  ScoutDiscovery,
  ScoutDiscoveryDetail,
  ScoutDiscoveryListResponse,
  ScoutDiscoveryRun,
  ScoutManualDiscoveryRequest,
  ScoutSource,
  ScoutStatus,
  SystemSummary,
} from "./types";

// Every call here hits a real DARWIN_core /api/v1/... endpoint. ARENA never
// talks to Postgres or HERMES directly, and never fabricates a response
// (PID-002 §12/§13). A non-2xx response is surfaced as ApiError so pages can
// render a controlled degraded state instead of a raw exception.

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    let message = `Request to ${path} failed (${res.status})`;
    let code: string | undefined;
    try {
      const body = await res.json();
      if (body?.error?.message) message = body.error.message;
      if (body?.error?.code) code = body.error.code;
      else if (body?.ready === false) {
        // /ready returns its own shape (no {error:...} envelope) on 503
        message = "DARWIN is not ready";
      }
    } catch {
      /* body wasn't JSON — keep the generic message */
    }
    throw new ApiError(res.status, message, code);
  }
  return (await res.json()) as T;
}

// POST counterpart to `get` above — same non-2xx -> ApiError discipline,
// plus FastAPI's plain `{"detail": "..."}` 404 shape (scout intake-status
// on an unknown id) alongside the `{"error": {"code","message"}}` shape
// scout's own domain validation errors use (e.g. SCOUT_INVALID_ORIGIN).
async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let message = `Request to ${path} failed (${res.status})`;
    let code: string | undefined;
    try {
      const responseBody = await res.json();
      if (responseBody?.error?.message) {
        message = responseBody.error.message;
        code = responseBody.error.code;
      } else if (typeof responseBody?.detail === "string") {
        message = responseBody.detail;
      }
    } catch {
      /* body wasn't JSON — keep the generic message */
    }
    throw new ApiError(res.status, message, code);
  }
  return (await res.json()) as T;
}

function scoutDiscoveriesQuery(params: {
  symbol?: string;
  intakeStatus?: string;
  originKind?: string;
  sort?: DiscoverySort;
  limit?: number;
  offset?: number;
}): string {
  const q = new URLSearchParams();
  if (params.symbol) q.set("symbol", params.symbol);
  if (params.intakeStatus) q.set("intake_status", params.intakeStatus);
  if (params.originKind) q.set("origin_kind", params.originKind);
  if (params.sort) q.set("sort", params.sort);
  q.set("limit", String(params.limit ?? 100));
  if (params.offset) q.set("offset", String(params.offset));
  return q.toString();
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  ready: () => get<ReadinessReport>("/ready"),
  buildinfo: () => get<BuildInfo>("/buildinfo"),
  systemSummary: () => get<SystemSummary>("/system/summary"),
  pipelineSummary: () => get<PipelineSummary>("/pipeline/summary"),
  listDatasets: (limit = 50) =>
    get<{ items: MarketDataset[] }>(`/datasets?limit=${limit}`),
  getDataset: (id: string) => get<MarketDataset>(`/datasets/${id}`),
  listRuns: (limit = 50) => get<{ items: ResearchRun[] }>(`/runs?limit=${limit}`),
  getRun: (id: string) => get<ResearchRun>(`/runs/${id}`),
  listInstrumentDefinitions: () =>
    get<{ items: InstrumentDefinition[] }>("/instrument-definitions"),
  getInstrumentDefinition: (instrumentId: string) =>
    get<InstrumentDefinition>(`/instrument-definitions/${instrumentId}`),
  migrations: () => get<MigrationState>("/migrations"),

  // --- PID-003 SCOUT ---
  scoutStatus: () => get<ScoutStatus>("/scout/status"),
  scoutSources: () => get<{ items: ScoutSource[] }>("/scout/sources"),
  scoutDiscoveryRuns: (limit = 50) =>
    get<{ items: ScoutDiscoveryRun[] }>(`/scout/discovery-runs?limit=${limit}`),
  scoutDiscoveryRun: (id: string) => get<ScoutDiscoveryRun>(`/scout/discovery-runs/${id}`),
  scoutDiscoveries: (params: {
    symbol?: string;
    intakeStatus?: string;
    originKind?: string;
    sort?: DiscoverySort;
    limit?: number;
    offset?: number;
  } = {}) => get<ScoutDiscoveryListResponse>(`/scout/discoveries?${scoutDiscoveriesQuery(params)}`),
  scoutDiscovery: (id: string) => get<ScoutDiscoveryDetail>(`/scout/discoveries/${id}`),
  // Bounded, deliberate on-demand run — never fired automatically on page
  // load (PID-003 sec6/sec10). Always resolves 200 with a durable
  // DiscoveryRun even on total source failure (status FAILED) — this is
  // not an ApiError path in the ordinary case.
  scoutDiscover: (body: { symbol?: string; max_records?: number; sort?: DiscoverySort }) =>
    post<{ discovery_run: ScoutDiscoveryRun }>("/scout/discover", body),
  scoutCreateDiscovery: (body: ScoutManualDiscoveryRequest) =>
    post<{ discovery: ScoutDiscovery }>("/scout/discoveries", body),
  scoutSetIntakeStatus: (id: string, body: { target_status: IntakeStatus; changed_by: string; reason?: string }) =>
    post<{ discovery: ScoutDiscovery }>(`/scout/discoveries/${id}/intake-status`, body),
};
