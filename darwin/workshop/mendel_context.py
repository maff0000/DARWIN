"""PID-004C sec8 -- the bounded MENDEL context builder + `DraftCapabilityView`
(PID-004C sec8.3.1).

`build_bounded_context` is the ONE place that assembles what MENDEL is
allowed to see (PID-004C sec8.1: "A single bounded context builder/
service assembles this -- MENDEL is handed a finished, bounded package,
not given ambient database access."). It reuses `darwin.workshop.service`'s
EXISTING functions end to end (`get_workshop`, `get_draft`,
`validate_workshop_draft`, `list_questions`, `list_decisions`,
`get_readiness`, `evaluate_data_requirement_availability`) -- this module
never re-implements Workshop/readiness logic, and never queries
`scout_discoveries`/`market_datasets` with anything other than the
existing, already-governed repository calls those functions already use.

Source material (`SourceDiscovery.original_description`/`pasted_rule_text`/
`personal_notes`/etc, surfaced below under `discovery`) is untrusted DATA
(PID-004C sec8.2) -- this module carries it through completely inert,
inside a plain JSON document; nothing here ever executes, evaluates, or
treats it as an instruction.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

import psycopg

from darwin.research_store.repositories import MarketDatasetRepository
from darwin.research_store.workshop_repositories import discovery_row
from darwin.specification.data_requirements import DataRequirement
from darwin.specification.readiness import PerRequirementAvailability
from darwin.specification.serialization import serialize_specification_draft
from darwin.workshop import service
from darwin.workshop.mendel_adapter import BoundedMendelContext
from darwin.workshop.mendel_domain import NO_DRAFT_YET, DraftRevisionBinding

#: The context builder's own declared schema version (PID-004C
#: sec10.1/sec10.5) -- an addition/change to the document shape below is a
#: deliberate version bump, never a silent shape drift under the same
#: version string.
CONTEXT_SCHEMA_VERSION = "MENDEL_CONTEXT_V1"

_DISCOVERY_FIELDS = (
    "id",
    "title",
    "origin_kind",
    "source_symbol",
    "source_timeframe",
    "origin_url",
    "original_description",
    "pasted_rule_text",
    "personal_notes",
    "tags",
)


class DataNeedAvailability(StrEnum):
    """PID-004C sec8.3.1's four availability meanings, distinct from (but
    derived from, via `darwin.workshop.service.
    evaluate_data_requirement_availability`) `darwin.specification.
    readiness.PerRequirementAvailability` -- `DraftCapabilityView` is a
    pre-finalisation, draft-scoped concept and must never be confused with
    a persisted `DataReadinessAssessment` (PID-004C sec8.3.1)."""

    SUPPORTED_AND_AVAILABLE = "SUPPORTED_AND_AVAILABLE"
    SUPPORTED_BUT_NOT_AVAILABLE = "SUPPORTED_BUT_NOT_AVAILABLE"
    UNSUPPORTED_OR_AUTHORITY_MISSING = "UNSUPPORTED_OR_AUTHORITY_MISSING"
    UNKNOWN = "UNKNOWN"


_AVAILABILITY_MAP: dict[PerRequirementAvailability, DataNeedAvailability] = {
    PerRequirementAvailability.AVAILABLE: DataNeedAvailability.SUPPORTED_AND_AVAILABLE,
    PerRequirementAvailability.UNAVAILABLE: DataNeedAvailability.SUPPORTED_BUT_NOT_AVAILABLE,
    PerRequirementAvailability.INSUFFICIENT_HISTORY: DataNeedAvailability.SUPPORTED_BUT_NOT_AVAILABLE,
    PerRequirementAvailability.INSUFFICIENT_RESOLUTION: DataNeedAvailability.SUPPORTED_BUT_NOT_AVAILABLE,
    PerRequirementAvailability.CONTRACT_INCOMPATIBLE: DataNeedAvailability.SUPPORTED_BUT_NOT_AVAILABLE,
    PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED: DataNeedAvailability.UNSUPPORTED_OR_AUTHORITY_MISSING,
    PerRequirementAvailability.UNKNOWN: DataNeedAvailability.UNKNOWN,
}


@dataclass(frozen=True)
class DataRequirementCapability:
    requirement_id: str
    availability: DataNeedAvailability
    reason: str | None = None


@dataclass(frozen=True)
class DraftCapabilityView:
    """A bounded, DERIVED, non-semantic view (PID-004C sec8.3.1) -- never
    part of `StrategyVersion` identity/fingerprint, never a new
    independent capability registry, always safe to recompute. Built
    fresh on every `build_bounded_context` call; nothing here is ever
    persisted with its own identity."""

    per_requirement: tuple[DataRequirementCapability, ...] = ()

    def as_document(self) -> dict:
        return {
            "per_requirement": [
                {"requirement_id": r.requirement_id, "availability": r.availability.value, "reason": r.reason}
                for r in self.per_requirement
            ]
        }


def build_draft_capability_view(
    conn: psycopg.Connection, data_requirements: tuple[DataRequirement, ...]
) -> DraftCapabilityView:
    """Computed from the SAME logic `assess_workshop_readiness`/
    `get_readiness` already use (`darwin.workshop.service.
    evaluate_data_requirement_availability`) -- never a duplicated/
    reinvented HERMES-availability check (PID-004C sec8.3)."""
    if not data_requirements:
        return DraftCapabilityView()
    datasets = MarketDatasetRepository(conn).list(limit=500)
    records = tuple(
        DataRequirementCapability(
            requirement_id=requirement.requirement_id,
            availability=_AVAILABILITY_MAP.get(availability, DataNeedAvailability.UNKNOWN),
            reason=reason,
        )
        for requirement in data_requirements
        for availability, reason in (service.evaluate_data_requirement_availability(requirement, datasets),)
    )
    return DraftCapabilityView(per_requirement=records)


def _discovery_document(row: dict) -> dict:
    doc: dict = {}
    for field_name in _DISCOVERY_FIELDS:
        value = row.get(field_name)
        if field_name == "id" and value is not None:
            value = str(value)
        elif field_name == "tags" and value is not None:
            value = list(value)
        doc[field_name] = value
    return doc


def _validation_document(outcome) -> dict:
    return {
        "status": outcome.status.value,
        "is_valid": outcome.is_valid,
        "findings": [
            {"stage": f.stage, "code": f.code, "message": f.message, "path": f.path} for f in outcome.findings
        ],
    }


def _binding_document(binding: DraftRevisionBinding) -> str | int:
    return "NO_DRAFT_YET" if binding is NO_DRAFT_YET else binding


def compute_context_fingerprint(schema_version: str, document: dict) -> str:
    """A deterministic, canonical serialisation of `document` UNDER
    `schema_version` (PID-004C sec10.5), hashed with sha256. `sort_keys`
    makes key-insertion order irrelevant; there is no volatile/incidental
    field (a literal wall-clock timestamp, a UI-only value) anywhere in
    the document this function is handed -- callers must exclude any such
    field before calling this, never rely on this function to do so."""
    canonical = json.dumps({"schema_version": schema_version, "document": document}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_bounded_context(
    conn: psycopg.Connection, workshop_id: str, *, focus_text: str | None = None
) -> BoundedMendelContext:
    """The one bounded-context assembly seam (PID-004C sec8.1). Reuses
    `darwin.workshop.service` end to end -- never queries
    `strategy_workshops`/`workshop_questions`/`workshop_decisions`/
    `specification_drafts`/`market_datasets` directly."""
    workshop = service.get_workshop(conn, workshop_id)
    discoveries = [
        _discovery_document(row)
        for row in (discovery_row(conn, d) for d in workshop.discovery_ids)
        if row is not None
    ]
    questions = service.list_questions(conn, workshop_id)
    decisions = service.list_decisions(conn, workshop_id)
    draft, revision = service.get_draft(conn, workshop_id)
    binding: DraftRevisionBinding = revision if revision is not None else NO_DRAFT_YET

    validation_document = None
    if draft is not None:
        validation_document = _validation_document(service.validate_workshop_draft(conn, workshop_id))

    data_requirements = tuple(draft.data_requirements.values()) if draft is not None else ()
    capability_view = build_draft_capability_view(conn, data_requirements)
    readiness = service.get_readiness(conn, workshop_id)

    document = {
        "workshop_id": workshop.workshop_id,
        "candidate_id": workshop.candidate_id,
        "discovery": discoveries,
        "questions": [
            {
                "question_id": q.question_id,
                "semantic_subject": q.semantic_subject,
                "question_text": q.question_text,
                "status": q.status.value,
                "origin": q.origin.value,
                "rationale": q.rationale,
            }
            for q in questions
        ],
        "decisions": [
            {
                "decision_id": d.decision_id,
                "proposed_value": d.proposed_value,
                "origin": d.origin.value,
                "acceptance_state": d.acceptance_state.value,
                "affected_semantic_paths": list(d.affected_semantic_paths),
                "rationale": d.rationale,
            }
            for d in decisions
        ],
        "draft": serialize_specification_draft(draft) if draft is not None else None,
        "draft_revision_binding": _binding_document(binding),
        "validation": validation_document,
        "data_requirement_ids": sorted(r.requirement_id for r in data_requirements),
        "readiness": {"state": readiness["state"]},
        "draft_capability_view": capability_view.as_document(),
        "focus_text": focus_text,
    }
    fingerprint = compute_context_fingerprint(CONTEXT_SCHEMA_VERSION, document)
    return BoundedMendelContext(schema_version=CONTEXT_SCHEMA_VERSION, fingerprint=fingerprint, document=document)
