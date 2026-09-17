"""PID-004A provenance unit tests (PID-004 sec14/sec22/sec23)."""
from __future__ import annotations

import pytest

from darwin.specification.errors import ProvenanceError
from darwin.specification.provenance import (
    ProvenanceRecord,
    RuleAcceptanceState,
    RuleOrigin,
    accept_rule,
    claim_source_rule,
    reject_rule,
    supersede_rule,
)


def test_workshop_proposal_accepted_keeps_workshop_proposal_origin_forever():
    """PID-004 sec22: 'A Workshop proposal accepted by Matt remains
    origin = WORKSHOP_PROPOSAL and acceptance = ACCEPTED_SPECIFICATION_
    RULE.' This is the single most important provenance invariant in the
    whole contract -- acceptance must never rewrite origin."""
    record = ProvenanceRecord(
        provenance_id="p1",
        subject_ref="atomic.close_above_level",
        origin=RuleOrigin.WORKSHOP_PROPOSAL,
        acceptance_state=RuleAcceptanceState.PROPOSED,
    )
    accepted = accept_rule(record, material_decision_ref="decision-42")
    assert accepted.origin == RuleOrigin.WORKSHOP_PROPOSAL
    assert accepted.acceptance_state == RuleAcceptanceState.ACCEPTED_SPECIFICATION_RULE
    assert accepted.material_decision_ref == "decision-42"
    # the original record is untouched -- accept_rule never mutates in place
    assert record.acceptance_state == RuleAcceptanceState.PROPOSED


def test_accept_rule_returns_a_new_object_not_the_same_record():
    record = ProvenanceRecord(
        provenance_id="p1", subject_ref="x", origin=RuleOrigin.SOURCE_RULE, acceptance_state=RuleAcceptanceState.PROPOSED
    )
    accepted = accept_rule(record)
    assert accepted is not record


def test_reject_and_supersede_also_never_touch_origin():
    record = ProvenanceRecord(
        provenance_id="p1", subject_ref="x", origin=RuleOrigin.USER_CLARIFICATION, acceptance_state=RuleAcceptanceState.PROPOSED
    )
    rejected = reject_rule(record, notes="not pursued")
    assert rejected.origin == RuleOrigin.USER_CLARIFICATION
    assert rejected.acceptance_state == RuleAcceptanceState.REJECTED

    superseded = supersede_rule(accept_rule(record))
    assert superseded.origin == RuleOrigin.USER_CLARIFICATION
    assert superseded.acceptance_state == RuleAcceptanceState.SUPERSEDED


def test_superseded_record_cannot_be_reaccepted():
    record = ProvenanceRecord(
        provenance_id="p1", subject_ref="x", origin=RuleOrigin.SOURCE_RULE, acceptance_state=RuleAcceptanceState.PROPOSED
    )
    superseded = supersede_rule(record)
    with pytest.raises(ProvenanceError):
        accept_rule(superseded)


def test_claim_source_rule_helper_produces_source_rule_origin():
    """This helper exists as the one obvious, documented seam for
    recording SOURCE_RULE -- it never accepts an origin argument, so a
    caller cannot use it to mislabel a Workshop proposal as a source
    rule."""
    record = claim_source_rule(provenance_id="p1", subject_ref="atomic.rsi_below_30")
    assert record.origin == RuleOrigin.SOURCE_RULE
    assert record.acceptance_state == RuleAcceptanceState.PROPOSED


def test_origin_and_acceptance_are_tracked_as_two_separate_closed_enums():
    """PID-004 sec22: ACCEPTED_SPECIFICATION_RULE is never pretended to be
    an origin -- it does not even appear in the RuleOrigin enum."""
    assert "ACCEPTED_SPECIFICATION_RULE" not in {o.value for o in RuleOrigin}
    assert {o.value for o in RuleOrigin} == {"SOURCE_RULE", "USER_CLARIFICATION", "WORKSHOP_PROPOSAL"}
    assert {a.value for a in RuleAcceptanceState} == {
        "PROPOSED", "ACCEPTED_SPECIFICATION_RULE", "REJECTED", "SUPERSEDED",
    }
