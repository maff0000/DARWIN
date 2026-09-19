"""PID-004C CLOSURE HARDENING item 2 (Auditor Finding A fix) --
`darwin.workshop.mendel_service.PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS` /
`_validate_payload_shape`'s new closed-key-set enforcement, proven for
EVERY one of the nine `ProposalClass` members.

The Auditor's own reproduction: `RawMendelProposal(proposal_class=
"PARAMETER_CHANGE", payload={...known keys..., "__class__": "evil",
"unexpected_extra_field": {...}})` used to succeed and persist. This file
proves, for all nine classes: a valid payload for that class, PLUS one
extra `{"totally_unknown_field": "..."}` key -> `MendelOutputValidationError`
-> the owning `MendelRun` ends `FAILED` -> ZERO `MendelProposal` rows
persisted for that failed invocation (queried directly from the DB, never
trusted from the returned object) -> Workshop canonical state (draft
revision) unchanged. One parametrized test covers all nine; unknown keys
are never silently dropped, never preserved as inert JSON, never
heuristically repaired.
"""
from __future__ import annotations

import pytest
from psycopg.rows import dict_row

from darwin.research_store.db import connection
from darwin.workshop import mendel_service, service
from darwin.workshop.mendel_adapter import RawMendelProposal
from darwin.workshop.mendel_domain import InvocationPurpose, ProposalClass, RunStatus
from darwin.workshop.mendel_service import PROPOSAL_SCHEMA_VERSION
from tests.fixtures.mendel import (
    data_requirement_proposal,
    open_workshop_with_draft,
    parameter_change_proposal,
)
from tests.fixtures.specification_drafts import minimal_valid_draft

pytestmark = pytest.mark.integration


def _semantic_change_payload() -> dict:
    from darwin.specification.serialization import serialize_specification_draft

    document = serialize_specification_draft(minimal_valid_draft())
    return {"composition": document["composition"]}


#: One genuinely valid (per that class's own current handler contract)
#: payload for every ProposalClass -- reused as the "known-good" base that
#: a single extra unknown key is then added onto.
_VALID_PAYLOAD_BY_CLASS: dict[ProposalClass, dict] = {
    ProposalClass.ASK_QUESTION: {
        "semantic_subject": "breakout_confirmation", "question_text": "Wick or close?",
    },
    ProposalClass.MATERIAL_CONCERN: {"concern": "Source assumes 24h liquidity."},
    ProposalClass.SEMANTIC_CHANGE: _semantic_change_payload(),
    ProposalClass.PARAMETER_CHANGE: parameter_change_proposal().payload,
    ProposalClass.DATA_REQUIREMENT: data_requirement_proposal().payload,
    ProposalClass.THESIS_CHANGE: {"new_thesis": "A revised, still-controlled thesis statement."},
    ProposalClass.POLICY_CLASSIFICATION: {
        "policy_class": "EXECUTION_POLICY", "compatibility": "PERMITTED", "notes": "No search envelope needed.",
    },
    ProposalClass.INSTRUMENT_CLARIFICATION: {
        "kind": "EXPLICIT_SINGLE", "instrument_ids": ["XAU_USD"], "generic_criteria": [],
    },
    ProposalClass.TIMEFRAME_CLARIFICATION: {
        "iana_timezone": "America/New_York", "local_start": "08:00", "local_end": "17:00",
        "weekdays": [0, 1, 2, 3, 4], "cross_midnight": False,
    },
}

assert set(_VALID_PAYLOAD_BY_CLASS) == set(ProposalClass), (
    "this test file must cover every ProposalClass member, mirroring PROPOSAL_CLASS_CATEGORY's "
    "and PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS's own exhaustiveness discipline"
)


@pytest.mark.parametrize("proposal_class", sorted(ProposalClass, key=lambda c: c.value))
def test_unrecognised_payload_key_fails_closed_for_every_proposal_class(pg_config, proposal_class):
    with connection(pg_config) as conn:
        workshop, revision = open_workshop_with_draft(conn)

        valid_payload = _VALID_PAYLOAD_BY_CLASS[proposal_class]
        hostile_payload = {**valid_payload, "totally_unknown_field": "evil", "__class__": "evil"}
        malformed = RawMendelProposal(
            proposal_class=proposal_class.value, proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
            payload=hostile_payload, rationale=f"closure-hardening item2 negative proof for {proposal_class.value}",
        )
        run = mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None,
            adapter=_SingleProposalAdapter(malformed),
        )

        # --- The owning MendelRun ends FAILED. -----------------------------
        assert run.status == RunStatus.FAILED
        assert run.error_classification
        assert "unrecognised key" in run.error_classification.lower() or "unrecognised" in run.error_classification.lower()

        # --- ZERO MendelProposal rows persisted for this failed invocation
        # -- queried directly from the database, never trusted from the
        # returned object. --------------------------------------------------
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT COUNT(*) AS n FROM mendel_proposals WHERE run_id = %s", (run.run_id,))
            count = cur.fetchone()["n"]
        assert count == 0
        assert mendel_service.list_proposals(conn, workshop.workshop_id) == []

        # --- Workshop canonical state (draft revision) unchanged. ----------
        _, current_revision = service.get_draft(conn, workshop.workshop_id)
        assert current_revision == revision


class _SingleProposalAdapter:
    """A minimal, purpose-built test double (this file's own -- never
    reusing DeterministicTestMendelAdapter's richer surface for a single
    hard-coded raw proposal) that always returns exactly the one
    (possibly malformed) RawMendelProposal it was constructed with."""

    def __init__(self, proposal: RawMendelProposal) -> None:
        self._proposal = proposal
        self.provider_identity = "test-closure-hardening-item2"

    def invoke(self, *, context, purpose, focus_text):
        from darwin.workshop.mendel_adapter import MendelInvocationResult

        return MendelInvocationResult(proposals=(self._proposal,), reasoning_summary="closure hardening item2 probe")


def test_valid_payload_without_the_extra_key_is_not_rejected_for_its_shape(pg_config):
    """Companion sanity check: the SAME base payloads above, WITHOUT the
    extra key, are not rejected by the new closed-key-set check itself
    (they may still fail for other, pre-existing reasons unrelated to this
    closure -- e.g. QUESTION/ADVISORY categories are never dry-run against
    a handler at all, and DRAFT_MUTATING ones ARE dry-run, which is exactly
    the pre-existing behaviour this work package does not change)."""
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        for proposal_class, payload in _VALID_PAYLOAD_BY_CLASS.items():
            proposal = RawMendelProposal(
                proposal_class=proposal_class.value, proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
                payload=payload, rationale=f"closure-hardening item2 positive control for {proposal_class.value}",
            )
            run = mendel_service.invoke_mendel(
                conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None,
                adapter=_SingleProposalAdapter(proposal),
            )
            assert run.status == RunStatus.SUCCEEDED, (
                f"{proposal_class.value}: expected the KNOWN-GOOD payload (no extra key) to pass shape "
                f"validation, got {run.status.value}: {run.error_classification}"
            )
