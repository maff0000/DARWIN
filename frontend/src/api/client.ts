import type {
  BuildInfo,
  InstrumentDefinition,
  MarketDataset,
  MigrationState,
  PipelineSummary,
  ReadinessReport,
  ResearchRun,
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
};
