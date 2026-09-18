"""Shared PID-004C MENDEL test helpers -- mirrors tests/fixtures/workshops.py's
"TEST-controlled fixture data" discipline. Lives under tests/fixtures
because it is test-only scaffolding, never presented as real MENDEL
output.
"""
from __future__ import annotations

import psycopg

from darwin.specification.serialization import serialize_specification_draft
from darwin.workshop import service
from darwin.workshop.domain import StrategyWorkshop
from darwin.workshop.mendel_adapter import RawMendelProposal
from darwin.workshop.mendel_service import PROPOSAL_SCHEMA_VERSION
from tests.fixtures.specification_drafts import minimal_valid_draft
from tests.fixtures.workshops import new_candidate


def open_workshop_with_draft(conn: psycopg.Connection) -> tuple[StrategyWorkshop, int]:
    """An ACTIVE Workshop with a real, validation-clean SpecificationDraft
    already at revision 1 -- the common starting point for every
    DRAFT_MUTATING acceptance proof."""
    candidate_id = new_candidate(conn)
    workshop = service.open_workshop(conn, candidate_id=candidate_id)
    draft = minimal_valid_draft(candidate_id=candidate_id)
    document = serialize_specification_draft(draft)
    _, revision = service.update_draft(conn, workshop.workshop_id, expected_revision=0, draft_document=document)
    return workshop, revision


def ask_question_proposal() -> RawMendelProposal:
    return RawMendelProposal(
        proposal_class="ASK_QUESTION", proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
        payload={"semantic_subject": "breakout_confirmation", "question_text": "Wick or close?"},
        rationale="Source text does not specify intrabar sensitivity.",
        affected_semantic_paths=("entry.conditions.breakout_confirmation",),
    )


def material_concern_proposal() -> RawMendelProposal:
    return RawMendelProposal(
        proposal_class="MATERIAL_CONCERN", proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
        payload={"concern": "Source assumes 24h liquidity; XAU_USD has a weekend gap risk."},
        rationale="Flagging a material assumption gap for human review.",
        affected_semantic_paths=("entry.conditions",),
    )


def parameter_change_proposal(
    *, parameter_id: str = "max_daily_trades", fixed_value: int = 3
) -> RawMendelProposal:
    return RawMendelProposal(
        proposal_class="PARAMETER_CHANGE", proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
        payload={"parameter_id": parameter_id, "value_type": "INTEGER", "unit": None, "fixed_value": fixed_value},
        rationale="Bounding daily trade count per the source's own stated cadence.",
        affected_semantic_paths=(f"parameters.{parameter_id}",),
    )


def data_requirement_proposal(*, requirement_id: str = "iv_percentile_d1") -> RawMendelProposal:
    return RawMendelProposal(
        proposal_class="DATA_REQUIREMENT", proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
        payload={
            "requirement_id": requirement_id, "display_name": "XAU_USD D1 implied volatility percentile",
            "fact_class": "IMPLIED_VOLATILITY", "fact_reference_kind": "CANONICAL_FACT_REFERENCE",
            "authority_class": "OPTIONS_AUTHORITY", "instrument_applicability": ["XAU_USD"], "timeframe": "D1",
            "required_historical_depth": {"count": 252, "unit": "BARS"}, "units": None,
            "required_fields": ["value"], "causal_timing_policy": "NOT_APPLICABLE", "mandatory": True,
        },
        rationale="The strategy conditions entry on IV percentile.",
        affected_semantic_paths=("data_requirements",),
    )
