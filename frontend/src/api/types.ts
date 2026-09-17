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

// --- PID-003 SCOUT (darwin/scout/domain.py, darwin/app.py scout endpoints) ---
// Mirrors the real API responses exactly, same discipline as the rest of
// this file — never a field ARENA invents that the backend doesn't return.

export type IntakeStatus = "NEW" | "SHORTLISTED" | "IN_WORKSHOP" | "READY_FOR_SPECIFICATION" | "REJECTED";

export type OriginKind = "ADAPTER_SOURCED" | "USER_DISCOVERED" | "MY_IDEA";

export type FamilyResolution = "UNRESOLVED" | "FORK_LINEAGE";

export type RuleAvailability = "AVAILABLE" | "PARTIAL" | "UNAVAILABLE" | "ACCESS_RESTRICTED" | "UNKNOWN";

export type DiscoveryRunStatus = "RUNNING" | "SUCCEEDED" | "PARTIAL" | "FAILED";

// The exact allowed literal values for GET /scout/discoveries?sort= and
// POST /scout/discover body.sort (darwin/research_store/repositories.py
// _DISCOVERY_SORTS / darwin/scout/trader_dev_adapter.py ALLOWED_SORTS).
// max_drawdown_percent sorts ASCENDING (lowest claimed drawdown first) —
// every other numeric sort is DESCENDING (highest first).
export type DiscoverySort =
  | "recent"
  | "net_pnl_percent"
  | "profit_factor"
  | "sharpe"
  | "sortino"
  | "max_drawdown_percent"
  | "trade_count";

export interface ScoutSource {
  id: string;
  source_key: string;
  origin_kind: OriginKind;
  adapter_name: string | null;
  adapter_version: string | null;
  base_url: string | null;
  description: string;
  created_at_utc: string;
}

export interface ScoutDiscoveryRun {
  id: string;
  source_id: string;
  requested_filter: Record<string, unknown>;
  adapter_name: string;
  adapter_version: string;
  status: DiscoveryRunStatus;
  started_at_utc: string;
  completed_at_utc: string | null;
  records_observed: number;
  records_accepted: number;
  records_unchanged: number;
  records_changed: number;
  records_rejected: number;
  error_summary: string | null;
}

export interface ScoutStatus {
  trader_dev_public: { reachable: boolean };
  last_discovery_run: ScoutDiscoveryRun | null;
  sources: ScoutSource[];
}

// Flattened SourceDiscovery + latest SourceClaim fields, exactly as
// GET /scout/discoveries and GET /scout/discoveries/{id} return them.
// Every metric is a decimal-string or null — never a fabricated number.
export interface ScoutDiscovery {
  id: string;
  source_id: string;
  origin_kind: OriginKind;
  source_strategy_id: string | null;
  forked_from_source_strategy_id: string | null;
  family_resolution: FamilyResolution;
  discovery_lifecycle_state: "DISCOVERED";
  intake_status: IntakeStatus;
  title: string;
  source_symbol: string | null;
  source_timeframe: string | null;
  origin_description: string | null;
  origin_url: string | null;
  original_description: string | null;
  pasted_rule_text: string | null;
  personal_notes: string | null;
  tags: string[];
  last_snapshot_id: string | null;
  latest_rule_availability: RuleAvailability | null;
  first_seen_utc: string;
  last_seen_utc: string;
  created_at_utc: string;
  updated_at_utc: string | null;
  net_pnl_percent: string | null;
  max_drawdown_percent: string | null;
  win_rate_percent: string | null;
  profit_factor: string | null;
  trade_count: number | null;
  sharpe: string | null;
  sortino: string | null;
}

export interface ScoutSnapshot {
  id: string;
  discovery_id: string;
  source_id: string;
  source_record_id: string | null;
  extraction_utc: string;
  source_updated_utc: string | null;
  adapter_name: string;
  adapter_version: string;
  source_url: string | null;
  source_symbol: string | null;
  source_timeframe: string | null;
  raw_metadata: Record<string, unknown>;
  rule_availability: RuleAvailability;
  fingerprint_sha256: string;
  created_at_utc: string;
}

export interface ScoutIntakeAuditEntry {
  id: string;
  discovery_id: string;
  from_status: IntakeStatus | null;
  to_status: IntakeStatus;
  changed_by: string;
  reason: string | null;
  changed_at_utc: string;
}

export interface ScoutDiscoveryDetail {
  discovery: ScoutDiscovery;
  snapshots: ScoutSnapshot[];
  intake_audit_history: ScoutIntakeAuditEntry[];
}

export interface ScoutDiscoveryListResponse {
  items: ScoutDiscovery[];
  counts_by_intake_status: Record<IntakeStatus, number>;
}

export interface ScoutManualDiscoveryRequest {
  origin_kind: "USER_DISCOVERED" | "MY_IDEA";
  title: string;
  origin_description?: string | null;
  origin_url?: string | null;
  source_symbol?: string | null;
  source_timeframe?: string | null;
  original_description?: string | null;
  pasted_rule_text?: string | null;
  personal_notes?: string | null;
  tags?: string[];
  claimed_metrics?: Record<string, string | number> | null;
}
