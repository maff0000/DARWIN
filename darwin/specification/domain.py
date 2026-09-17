"""Core specification identity types (PID-004 sec4/sec33/sec38).

Four genuinely distinct types, never one status-flagged object (the
mistake the HSA archaeology flags explicitly --
`docs/archaeology/HSA-PID004A-REUSE-ASSESSMENT.md` #1/#2/"Gaps DARWIN must
solve itself": "HSA uses one schema plus a status enum across the whole
lifecycle... If DARWIN genuinely wants two separate typed objects, that
split has to be designed from scratch"):

- `StrategyCandidate` -- the durable research identity (PID-004 sec4.2).
- `SpecificationDraft` -- MUTABLE authoring object (PID-004 sec4.3).
- `StrategyVersion` -- IMMUTABLE, created only via
  `darwin.specification.validation.finalise` (PID-004 sec4.4).
- `SemanticFingerprint` / `ArtifactRecordFingerprint` -- the two
  independent fingerprints (PID-004 sec38), modelled as plain hex strings
  on `StrategyVersion` rather than wrapper types, since nothing in this
  contract phase needs a richer fingerprint object.

`StrategyVersion` is a frozen dataclass. Attempting to set any field on an
already-constructed instance raises `dataclasses.FrozenInstanceError`
(proved in tests/unit/test_specification_domain.py) -- there is no
`draft.freeze()` method anywhere that flips a flag on the same object.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime

from darwin.specification.applicability import (
    InstrumentApplicability,
    IntrabarAmbiguityPolicy,
    SessionSpec,
)
from darwin.specification.composition import (
    AtomicCondition,
    CompositionRoot,
    ExpirySpec,
)
from darwin.specification.data_requirements import DataRequirement
from darwin.specification.errors import SpecificationError
from darwin.specification.parameters import ParameterDefinition, ParameterStatus
from darwin.specification.policy import PolicyClass, PolicyCompatibilityDeclaration
from darwin.specification.provenance import ProvenanceRecord


@dataclass(frozen=True)
class StrategyCandidate:
    """The durable DARWIN research identity around which one or more
    StrategyVersions may be created (PID-004 sec4.2). Not itself evidence.
    `origin_discovery_ids` traces back to SCOUT `SourceDiscovery.id`
    value(s) -- this module never imports `darwin.scout.domain` to avoid a
    layering dependency; the ids are carried as plain strings.
    `parent_candidate_ids` supports PID-004 sec36's future composition
    lineage (`Candidate C derived from Candidate A + Candidate B`) without
    this contract phase implementing composition itself.
    """

    candidate_id: str
    title: str
    origin_discovery_ids: tuple[str, ...] = ()
    parent_candidate_ids: tuple[str, ...] = ()
    created_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.candidate_id.strip():
            raise SpecificationError("StrategyCandidate requires a non-empty candidate_id")
        if not self.title or not self.title.strip():
            raise SpecificationError("StrategyCandidate requires a non-empty title")


@dataclass
class SpecificationDraft:
    """MUTABLE authoring object (PID-004 sec4.3). May be incomplete at any
    point -- unresolved semantics, missing parameters, no composition yet.
    Never eligible for ATHENA; the only way out of draft form is
    `darwin.specification.validation.finalise`, which never mutates this
    object -- it only ever reads it.

    Deliberately NOT frozen: every field below is a plain mutable
    attribute a Workshop-style authoring loop would update incrementally.
    There is no `status`/`is_finalised` field anywhere on this class --
    finalisation state lives only in whether a *separate*
    `StrategyVersion` object exists, never as a flag flipped on this one
    (PID-004 sec19: "never mutate a draft in place into a frozen
    version").
    """

    draft_id: str
    candidate_id: str
    schema_semantic_version: str
    title: str = ""
    thesis: str = ""
    instrument_applicability: InstrumentApplicability | None = None
    composition: CompositionRoot | None = None
    fixed_parameters: dict[str, ParameterDefinition] = field(default_factory=dict)
    tunable_parameters: dict[str, ParameterDefinition] = field(default_factory=dict)
    policy_declarations: dict[PolicyClass, PolicyCompatibilityDeclaration] = field(default_factory=dict)
    data_requirements: dict[str, DataRequirement] = field(default_factory=dict)
    session_spec: SessionSpec | None = None
    intrabar_ambiguity_policy: IntrabarAmbiguityPolicy | None = None
    setup_expiry: ExpirySpec | None = None
    exit_rules: tuple[AtomicCondition, ...] = ()
    provenance: dict[str, ProvenanceRecord] = field(default_factory=dict)
    created_at_utc: datetime | None = None

    def set_parameter(self, definition: ParameterDefinition) -> None:
        """The only supported way to add/replace a parameter -- routes to
        `fixed_parameters` or `tunable_parameters` by the definition's own
        `status`, so a parameter can never be filed under both buckets at
        once."""
        if definition.status == ParameterStatus.FIXED:
            self.tunable_parameters.pop(definition.parameter_id, None)
            self.fixed_parameters[definition.parameter_id] = definition
        else:
            self.fixed_parameters.pop(definition.parameter_id, None)
            self.tunable_parameters[definition.parameter_id] = definition

    def set_policy_declaration(self, declaration: PolicyCompatibilityDeclaration) -> None:
        self.policy_declarations[declaration.policy_class] = declaration

    def set_data_requirement(self, requirement: DataRequirement) -> None:
        self.data_requirements[requirement.requirement_id] = requirement

    def set_provenance(self, record: ProvenanceRecord) -> None:
        self.provenance[record.subject_ref] = record


# The exact, ordered set of StrategyVersion fields that participate in
# `semantic_fingerprint` (PID-004 sec38). Kept as one explicit tuple, not
# scattered inline logic, so a reviewer/test can see at a glance exactly
# what is -- and, by omission, is NOT -- bound into semantic identity.
SEMANTIC_FIELD_NAMES: tuple[str, ...] = (
    "schema_semantic_version",
    "instrument_applicability",
    "composition",
    "fixed_parameters",
    "tunable_parameters",
    "policy_declarations",
    "data_requirements",
    "session_spec",
    "intrabar_ambiguity_policy",
    "setup_expiry",
    "exit_rules",
)

# Fields deliberately EXCLUDED from semantic_fingerprint (PID-004 sec38):
# strategy_version_id, candidate_id, title, thesis, provenance,
# finalised_at_utc. Recorded here so the exclusion is a visible, positive
# assertion rather than something only provable by reading _SEMANTIC_
# FIELD_NAMES and noticing what is missing.
_EXCLUDED_FROM_SEMANTIC_FINGERPRINT: tuple[str, ...] = (
    "strategy_version_id",
    "candidate_id",
    "title",
    "thesis",
    "provenance",
    "finalised_at_utc",
)


@dataclass(frozen=True)
class StrategyVersion:
    """Immutable, machine-readable, provenance-linked, deterministically
    validated StrategyVersion (PID-004 sec4.4). Created ONLY by
    `darwin.specification.validation.finalise` -- there is no public
    constructor helper in this module that builds one directly from a
    draft; `finalise` is the single seam.

    Never carries a field for a frozen `ExecutionPolicyVersion`/
    `DIKEPolicyVersion`/`SizingPolicyVersion`/`NewsContextPolicyVersion`
    id (PID-004 sec5B/sec12) -- only compatibility DECLARATIONS
    (`policy_declarations`). Never carries a `DataReadinessAssessment`
    (PID-004 sec26) -- readiness is assessed and stored entirely
    elsewhere, against this object's `strategy_version_id`, never inside
    it.
    """

    strategy_version_id: str
    candidate_id: str
    schema_semantic_version: str
    title: str
    thesis: str
    instrument_applicability: InstrumentApplicability
    composition: CompositionRoot
    fixed_parameters: tuple[ParameterDefinition, ...]
    tunable_parameters: tuple[ParameterDefinition, ...]
    policy_declarations: tuple[PolicyCompatibilityDeclaration, ...]
    data_requirements: tuple[DataRequirement, ...]
    session_spec: SessionSpec | None
    intrabar_ambiguity_policy: IntrabarAmbiguityPolicy
    setup_expiry: ExpirySpec
    exit_rules: tuple[AtomicCondition, ...]
    provenance: tuple[ProvenanceRecord, ...]
    finalised_at_utc: datetime
    semantic_fingerprint: str
    artifact_record_fingerprint: str

    def semantic_payload(self) -> dict:
        """Reconstructs the exact payload `semantic_fingerprint` was
        computed from, using ONLY `SEMANTIC_FIELD_NAMES`. Recomputing
        `darwin.specification.fingerprint.canonical_hash(version.
        semantic_payload())` and comparing it against `self.
        semantic_fingerprint` is the round-trip proof used in
        tests/unit/test_specification_fingerprint.py.
        """
        return {name: getattr(self, name) for name in SEMANTIC_FIELD_NAMES}

    def artifact_payload(self) -> dict:
        """Everything `artifact_record_fingerprint` binds beyond semantic
        identity: the record's own identity, provenance, and finalisation
        timestamp (PID-004 sec38)."""
        return {
            "semantic_fingerprint": self.semantic_fingerprint,
            "strategy_version_id": self.strategy_version_id,
            "candidate_id": self.candidate_id,
            "title": self.title,
            "provenance": self.provenance,
            "finalised_at_utc": self.finalised_at_utc,
        }


def strategy_version_field_names() -> frozenset[str]:
    """Introspection helper used by tests proving there is no frozen-policy-
    version field anywhere on StrategyVersion (PID-004 sec12 test)."""
    return frozenset(f.name for f in fields(StrategyVersion))
