"""Rule origin vs rule acceptance (PID-004 sec14/sec22/sec23).

Origin (`SOURCE_RULE` / `USER_CLARIFICATION` / `WORKSHOP_PROPOSAL`) is
tracked SEPARATELY from acceptance (`PROPOSED` / `ACCEPTED_SPECIFICATION_
RULE` / `REJECTED` / `SUPERSEDED`) -- `ACCEPTED_SPECIFICATION_RULE` is
never pretended to be an origin (PID-004 sec22: "This avoids pretending
ACCEPTED_SPECIFICATION_RULE is an origin."). A rule whose origin is
WORKSHOP_PROPOSAL and gets accepted into a final spec keeps
`origin = WORKSHOP_PROPOSAL` forever -- `accept_rule` below only ever
returns a NEW record with acceptance_state changed; it never has a code
path that could rewrite `origin`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from darwin.specification.errors import ProvenanceError


class RuleOrigin(StrEnum):
    SOURCE_RULE = "SOURCE_RULE"
    USER_CLARIFICATION = "USER_CLARIFICATION"
    WORKSHOP_PROPOSAL = "WORKSHOP_PROPOSAL"


class RuleAcceptanceState(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED_SPECIFICATION_RULE = "ACCEPTED_SPECIFICATION_RULE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class ProvenanceRecord:
    """Tracks how one material specification rule entered the draft, and
    where it currently stands. `subject_ref` names the specification
    element this record explains (e.g. an AtomicCondition.condition_id or
    a ParameterDefinition.parameter_id) -- deliberately a plain string
    reference rather than an embedded object, so provenance never gates
    what the rule/parameter itself is allowed to be.
    """

    provenance_id: str
    subject_ref: str
    origin: RuleOrigin
    acceptance_state: RuleAcceptanceState
    material_decision_ref: str | None = None
    notes: str | None = None
    recorded_at_utc: datetime | None = None


def accept_rule(record: ProvenanceRecord, *, material_decision_ref: str | None = None) -> ProvenanceRecord:
    """Returns a NEW ProvenanceRecord with
    `acceptance_state = ACCEPTED_SPECIFICATION_RULE`. `origin` is always
    copied over unchanged -- there is no parameter here that could set it,
    so a Workshop proposal accepted by Matt keeps
    `origin = WORKSHOP_PROPOSAL` forever (PID-004 sec22)."""
    if record.acceptance_state == RuleAcceptanceState.SUPERSEDED:
        raise ProvenanceError(
            f"ProvenanceRecord {record.provenance_id!r} is SUPERSEDED and cannot be (re)accepted"
        )
    return replace(
        record,
        acceptance_state=RuleAcceptanceState.ACCEPTED_SPECIFICATION_RULE,
        material_decision_ref=material_decision_ref or record.material_decision_ref,
    )


def reject_rule(record: ProvenanceRecord, *, notes: str | None = None) -> ProvenanceRecord:
    """Returns a NEW ProvenanceRecord with `acceptance_state = REJECTED`.
    `origin` is unchanged for the same reason as `accept_rule`."""
    return replace(record, acceptance_state=RuleAcceptanceState.REJECTED, notes=notes or record.notes)


def supersede_rule(record: ProvenanceRecord) -> ProvenanceRecord:
    """Returns a NEW ProvenanceRecord with `acceptance_state = SUPERSEDED`.
    `origin` is unchanged."""
    return replace(record, acceptance_state=RuleAcceptanceState.SUPERSEDED)


def claim_source_rule(*, provenance_id: str, subject_ref: str, notes: str | None = None) -> ProvenanceRecord:
    """The only supported way to record a rule as `SOURCE_RULE`. Callers
    (e.g. a future MENDEL integration) must never construct a
    `ProvenanceRecord(origin=RuleOrigin.SOURCE_RULE, ...)` for a rule THEY
    invented -- this contract phase has no automated intake, so this
    helper exists mainly to give tests and fixtures one obvious,
    documented seam to reason about should PID-004B ever add one. It
    performs no authentication of "did the source actually say this" --
    that judgement belongs to whatever calls it, which must be a human or
    an explicitly-governed adapter, never an LLM proposing its own rule
    and labelling it SOURCE_RULE (PID-004 sec22)."""
    return ProvenanceRecord(
        provenance_id=provenance_id,
        subject_ref=subject_ref,
        origin=RuleOrigin.SOURCE_RULE,
        acceptance_state=RuleAcceptanceState.PROPOSED,
        notes=notes,
    )
