// Types mirror DARWIN_core's real API responses exactly (darwin/app.py,
// darwin/research_store/repositories.py, darwin/core/health.py). ARENA
// never invents a field the backend doesn't actually return.

export type ComponentStatus = "OK" | "DEGRADED" | "DOWN";

export interface ComponentHealth {
  name: string;
  status: ComponentStatus;
  detail: string;
}

export interface ReadinessReport {
  ready: boolean;
  components: ComponentHealth[];
}

export interface BuildInfo {
  application_version: string;
  commit: string;
  build_time: string;
  environment: string;
}

export interface SystemSummary {
  build: BuildInfo;
  health: string;
  readiness: ReadinessReport;
  record_counts: {
    source_strategies: number;
    strategy_candidates: number;
    strategy_versions: number;
    market_datasets: number;
    research_runs: number;
  };
}

export type PipelineStage =
  | "DISCOVERED"
  | "SPECIFIED"
  | "ATHENA_TESTED"
  | "ATHENA_QUALIFIED"
  | "APOLLO_PROVEN"
  | "PROMISING";

export interface PipelineSummary {
  counts_by_stage: Record<string, number>;
}

export interface MarketDataset {
  id: string;
  instrument: string;
  instrument_definition_id: string;
  timeframe: string;
  requested_start_utc: string;
  requested_end_utc: string;
  actual_first_open_utc: string | null;
  actual_last_open_utc: string | null;
  record_count: number;
  fingerprint_sha256: string;
  hermes_contract_version: string;
  hermes_contract_commit: string;
  adapter_build_version: string;
  gap_summary: Record<string, unknown>;
  loaded_at_utc: string;
  created_at_utc: string;
}

export type EvidenceLevel =
  | "SOURCE_CLAIM"
  | "ATHENA_RESULT"
  | "APOLLO_PROOF"
  | "PLUTUS_RESULT"
  | "LIVE";

export type DikeState = "DIKE_DISABLED" | "DIKE_GUARDED";

export interface ResearchRun {
  id: string;
  result_kind: EvidenceLevel;
  engine: string;
  build_version: string;
  status: string;
  instrument: string;
  instrument_definition_id: string;
  timeframe: string;
  display_title: string;
  candidate_id: string | null;
  version_id: string | null;
  dataset_id: string | null;
  configuration_fingerprint: string | null;
  dike_state: DikeState;
  dike_policy_id: string | null;
  dike_policy_version: string | null;
  dike_policy_fingerprint: string | null;
  created_at_utc: string;
  updated_at_utc: string | null;
}

export interface InstrumentDefinition {
  instrument_id: string;
  base_asset: string;
  quote_asset: string;
  base_quantity_unit: string;
  price_unit: string;
  definition_version: string;
  fingerprint: string;
}

export interface MigrationState {
  total_migrations: number;
  applied: string[];
  pending: string[];
  up_to_date: boolean;
}
