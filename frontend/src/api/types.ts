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

// --- PID-004B Strategy Workshop (darwin/workshop/{domain,api,service}.py,
// darwin/specification/*.py) — mirrors the real API/serialization shapes
// exactly, same discipline as the rest of this file. A SpecificationDraft's
// governed sub-documents are typed as tagged unions on `__type__`, exactly
// as darwin.specification.serialization encodes/decodes them — ARENA never
// invents a shape the backend doesn't actually produce/accept. ---

export type WorkshopStatus = "ACTIVE" | "FINALISED" | "ABANDONED";
export type QuestionStatus = "OPEN" | "RESOLVED" | "WITHDRAWN";
export type QuestionOrigin = "HUMAN";
export type RuleOrigin = "SOURCE_RULE" | "USER_CLARIFICATION" | "WORKSHOP_PROPOSAL";
export type DecisionAcceptanceState = "PROPOSED" | "ACCEPTED" | "REJECTED" | "SUPERSEDED";
export type ValidationOutcomeStatus = "VALID" | "STRATEGY_NOT_SUFFICIENTLY_DEFINED";
export type ReadinessState = "UNASSESSED" | "TESTABLE" | "DATA_BLOCKED";
export type PerRequirementAvailability =
  | "AVAILABLE"
  | "UNAVAILABLE"
  | "INSUFFICIENT_HISTORY"
  | "INSUFFICIENT_RESOLUTION"
  | "AUTHORITY_NOT_ONBOARDED"
  | "CONTRACT_INCOMPATIBLE"
  | "UNKNOWN";

export interface Candidate {
  candidate_id: string;
  title: string;
  pipeline_stage: PipelineStage;
  source_strategy_id: string | null;
  origin_discovery_id: string | null;
  created_at_utc: string | null;
  updated_at_utc: string | null;
}

export interface Workshop {
  workshop_id: string;
  candidate_id: string;
  status: WorkshopStatus;
  discovery_ids: string[];
  current_draft_id: string | null;
  finalised_strategy_version_id: string | null;
  created_at_utc: string | null;
  updated_at_utc: string | null;
}

export interface WorkshopQuestion {
  question_id: string;
  workshop_id: string;
  semantic_subject: string;
  question_text: string;
  rationale: string | null;
  status: QuestionStatus;
  origin: QuestionOrigin;
  accepted_decision_id: string | null;
  created_at_utc: string | null;
  resolved_at_utc: string | null;
}

export interface WorkshopDecision {
  decision_id: string;
  workshop_id: string;
  proposed_value: unknown;
  origin: RuleOrigin;
  actor: string;
  acceptance_state: DecisionAcceptanceState;
  affected_semantic_paths: string[];
  related_question_id: string | null;
  rationale: string | null;
  created_at_utc: string | null;
  superseded_by_decision_id: string | null;
}

export interface ValidationFinding {
  stage: string;
  code: string;
  message: string;
  path: string | null;
}

export interface ValidationOutcome {
  status: ValidationOutcomeStatus;
  is_valid: boolean;
  findings: ValidationFinding[];
}

export interface ReadinessRequirement {
  requirement_id: string;
  availability: PerRequirementAvailability;
  reason: string | null;
}

export interface StrategyVersionSummary {
  strategy_version_id: string;
  candidate_id: string;
  title: string;
  thesis: string;
  semantic_fingerprint: string;
  artifact_record_fingerprint: string;
  finalised_at_utc: string;
  version_label: string | null;
}

export interface ReadinessResult {
  state: ReadinessState;
  assessed_at_utc: string | null;
  requirements: ReadinessRequirement[];
}

// --- Specification document node shapes (draft, tagged by __type__) -------

export type InstrumentApplicabilityKind = "EXPLICIT_SINGLE" | "EXPLICIT_SET" | "INSTRUMENT_GENERIC";

export interface InstrumentApplicabilityDoc {
  __type__: "InstrumentApplicability";
  kind: InstrumentApplicabilityKind;
  instrument_ids: string[];
  generic_criteria: string[];
}

export type ComparisonOperator = "EQ" | "NE" | "GT" | "GTE" | "LT" | "LTE" | "CROSSES_ABOVE" | "CROSSES_BELOW";
export type Direction = "LONG" | "SHORT" | "BOTH";
export type ComponentDirectionRelationship = "SAME" | "OPPOSITE" | "ANY";
export type FactClass =
  | "MARKET_OHLCV"
  | "OPTIONS_CHAIN"
  | "IMPLIED_VOLATILITY"
  | "OPEN_INTEREST"
  | "FUTURES_CURVE"
  | "NEWS_CONTEXT"
  | "ECONOMIC_SURPRISE"
  | "PREDICTION_MARKET";
export type DataAuthorityClass =
  | "HERMES_CANONICAL_MARKET"
  | "ARES_GOVERNED_CONTEXT"
  | "OPTIONS_AUTHORITY"
  | "FUTURES_AUTHORITY"
  | "OTHER_GOVERNED_AUTHORITY";

export interface LiteralDoc {
  __type__: "Literal";
  value: { __decimal__: string } | number | boolean | string | null;
  unit: string | null;
}

export interface CanonicalFactReferenceDoc {
  __type__: "CanonicalFactReference";
  fact_key: string;
  fact_class: FactClass;
  authority_class: DataAuthorityClass;
  unit: string;
  timeframe: string;
  requirement_id: string;
}

export interface ComparisonDoc {
  __type__: "Comparison";
  operator: ComparisonOperator;
  left: LiteralDoc | CanonicalFactReferenceDoc | Record<string, unknown>;
  right: LiteralDoc | CanonicalFactReferenceDoc | Record<string, unknown>;
}

export interface AtomicConditionDoc {
  __type__: "AtomicCondition";
  condition_id: string;
  semantic_role: string;
  timeframe: string;
  expression: ComparisonDoc | Record<string, unknown>;
  direction: Direction;
}

export interface AllCompositionDoc {
  __type__: "AllComposition";
  composition_id: string;
  components: AtomicConditionDoc[];
  direction_relationship: ComponentDirectionRelationship | null;
}

export interface AnyCompositionDoc {
  __type__: "AnyComposition";
  composition_id: string;
  components: AtomicConditionDoc[];
  direction_relationship: ComponentDirectionRelationship | null;
}

export type SequenceTieSemantics = "TIES_PERMITTED" | "TIES_BREAK_ORDER";

export interface SequenceCompositionDoc {
  __type__: "SequenceComposition";
  composition_id: string;
  components: Array<{ sequence_index: number; component: AtomicConditionDoc }>;
  ordering_window_seconds: number;
  tie_semantics: SequenceTieSemantics;
  direction_relationship: ComponentDirectionRelationship | null;
}

export type ExpiryMode = "NOT_APPLICABLE" | "NEVER" | "FRAMES" | "DURATION";

export interface ExpirySpecDoc {
  __type__: "ExpirySpec";
  mode: ExpiryMode;
  frame_count: number | null;
  finest_bound_timeframe: string | null;
  duration_seconds: number | null;
}

export interface ContextTriggerCompositionDoc {
  __type__: "ContextTriggerComposition";
  composition_id: string;
  context: AtomicConditionDoc;
  trigger: AtomicConditionDoc;
  context_validity: ExpirySpecDoc;
  direction_relationship: ComponentDirectionRelationship | null;
}

export type CompositionDoc =
  | AtomicConditionDoc
  | AllCompositionDoc
  | AnyCompositionDoc
  | SequenceCompositionDoc
  | ContextTriggerCompositionDoc;

export type IntrabarAmbiguityPolicy = "NOT_APPLICABLE" | "CONSERVATIVE_SL_FIRST";

export type ParameterStatus = "FIXED" | "TUNABLE";
export type ParameterValueType = "DECIMAL" | "INTEGER" | "BOOLEAN" | "STRING" | "DURATION_SECONDS";

export interface NumericRangeDomainDoc {
  __type__: "NumericRangeDomain";
  minimum: { __decimal__: string };
  maximum: { __decimal__: string };
  step: { __decimal__: string } | null;
}

export interface ParameterDefinitionDoc {
  __type__: "ParameterDefinition";
  parameter_id: string;
  status: ParameterStatus;
  value_type: ParameterValueType;
  unit: string | null;
  fixed_value: { __decimal__: string } | number | boolean | string | null;
  domain: NumericRangeDomainDoc | Record<string, unknown> | null;
}

export type HistoricalDepthUnit = "BARS" | "DAYS" | "YEARS";
export type FactReferenceKind = "CANONICAL_FACT_REFERENCE" | "SPECIFICATION_DERIVED_FACT";
export type CausalTimingPolicy =
  | "NOT_APPLICABLE"
  | "ORIGINAL_PUBLISHED_VALUE_ONLY"
  | "LATEST_CAUSALLY_AVAILABLE_REVISION";

export interface DataRequirementDoc {
  __type__: "DataRequirement";
  requirement_id: string;
  display_name: string;
  fact_class: FactClass;
  fact_reference_kind: FactReferenceKind;
  authority_class: DataAuthorityClass;
  instrument_applicability: string[];
  timeframe: string | null;
  required_historical_depth: { __type__: "HistoricalDepthRequirement"; count: number; unit: HistoricalDepthUnit };
  units: string | null;
  required_fields: string[];
  causal_timing_policy: CausalTimingPolicy;
  mandatory: boolean;
}

export type PolicyClass = "EXECUTION_POLICY" | "DIKE_POLICY" | "SIZING_POLICY" | "NEWS_CONTEXT_POLICY";
export type PolicyCompatibility = "REQUIRED" | "PERMITTED" | "DISABLED" | "IRRELEVANT";

export interface PolicyCompatibilityDeclarationDoc {
  __type__: "PolicyCompatibilityDeclaration";
  policy_class: PolicyClass;
  compatibility: PolicyCompatibility;
  authorized_search_envelope: unknown[];
  notes: string | null;
}

export interface SessionSpecDoc {
  __type__: "SessionSpec";
  iana_timezone: string;
  local_start: string;
  local_end: string;
  weekdays: number[];
  dst_handling: "FOLLOW_IANA_TIMEZONE_RULES";
  cross_midnight: boolean;
}

export interface SpecificationDraftDoc {
  serialization_schema_version?: string;
  __type__?: "SpecificationDraft";
  draft_id: string;
  candidate_id: string;
  schema_semantic_version: string;
  title: string;
  thesis: string;
  instrument_applicability: InstrumentApplicabilityDoc | null;
  composition: CompositionDoc | null;
  fixed_parameters: Record<string, ParameterDefinitionDoc>;
  tunable_parameters: Record<string, ParameterDefinitionDoc>;
  policy_declarations: PolicyCompatibilityDeclarationDoc[];
  data_requirements: Record<string, DataRequirementDoc>;
  session_spec: SessionSpecDoc | null;
  intrabar_ambiguity_policy: IntrabarAmbiguityPolicy | null;
  setup_expiry: ExpirySpecDoc | null;
  exit_rules: AtomicConditionDoc[];
  provenance: Record<string, unknown>;
  created_at_utc: string | null;
}
