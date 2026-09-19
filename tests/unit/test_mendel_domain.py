"""PID-004C MENDEL Workshop Assistant domain-model unit tests -- pure
construction-time invariants + the context-fingerprint determinism proof,
no database required. Mirrors tests/unit/test_workshop_domain.py's style.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from darwin.workshop.mendel_context import compute_context_fingerprint
from darwin.workshop.mendel_domain import (
    NO_DRAFT_YET,
    PROPOSAL_CLASS_CATEGORY,
    MendelProposal,
    MendelRun,
    ProposalCategory,
    ProposalClass,
    ProposalStatus,
    RunStatus,
    category_for_class,
    is_stale_binding,
)
from darwin.workshop.mendel_errors import (
    MendelProposalClassCategoryMismatchError,
    MendelRunError,
)

# ============================================================================
# ProposalClass <-> ProposalCategory mapping agreement (PID-004C sec6.4).
# ============================================================================


def test_every_proposal_class_has_exactly_one_category_mapping():
    assert set(PROPOSAL_CLASS_CATEGORY) == set(ProposalClass)


def test_class_category_mapping_matches_the_pid_table_exactly():
    assert category_for_class(ProposalClass.ASK_QUESTION) == ProposalCategory.QUESTION
    assert category_for_class(ProposalClass.MATERIAL_CONCERN) == ProposalCategory.ADVISORY
    for draft_mutating_class in (
        ProposalClass.SEMANTIC_CHANGE, ProposalClass.PARAMETER_CHANGE, ProposalClass.DATA_REQUIREMENT,
        ProposalClass.THESIS_CHANGE, ProposalClass.POLICY_CLASSIFICATION,
        ProposalClass.INSTRUMENT_CLARIFICATION, ProposalClass.TIMEFRAME_CLARIFICATION,
    ):
        assert category_for_class(draft_mutating_class) == ProposalCategory.DRAFT_MUTATING


def _valid_proposal_kwargs(**overrides) -> dict:
    kwargs = {
        "proposal_id": "p1", "run_id": "r1", "workshop_id": "w1",
        "proposal_class": ProposalClass.ASK_QUESTION, "proposal_category": ProposalCategory.QUESTION,
        "proposal_schema_version": "MENDEL_PROPOSAL_V1",
        "payload": {"semantic_subject": "x", "question_text": "y?"}, "rationale": "because",
        "affected_semantic_paths": (), "generated_against_draft_revision": NO_DRAFT_YET,
    }
    kwargs.update(overrides)
    return kwargs


def test_mendel_proposal_rejects_mismatched_class_category_pair():
    with pytest.raises(MendelProposalClassCategoryMismatchError):
        MendelProposal(**_valid_proposal_kwargs(proposal_category=ProposalCategory.ADVISORY))


def test_mendel_proposal_accepts_agreeing_class_category_pair():
    proposal = MendelProposal(**_valid_proposal_kwargs())
    assert proposal.proposal_category == ProposalCategory.QUESTION


def test_mendel_proposal_proposed_must_not_carry_resolved_at_utc():
    with pytest.raises(MendelRunError):
        MendelProposal(**_valid_proposal_kwargs(resolved_at_utc=datetime.now(UTC)))


def test_mendel_proposal_terminal_status_requires_resolved_at_utc():
    with pytest.raises(MendelRunError):
        MendelProposal(**_valid_proposal_kwargs(status=ProposalStatus.REJECTED))


def test_mendel_proposal_terminal_status_with_resolved_at_utc_is_valid():
    proposal = MendelProposal(
        **_valid_proposal_kwargs(status=ProposalStatus.REJECTED, resolved_at_utc=datetime.now(UTC))
    )
    assert proposal.status == ProposalStatus.REJECTED


def test_resulting_question_id_only_allowed_for_question_category():
    with pytest.raises(MendelRunError):
        MendelProposal(
            **_valid_proposal_kwargs(
                proposal_class=ProposalClass.MATERIAL_CONCERN, proposal_category=ProposalCategory.ADVISORY,
                status=ProposalStatus.ACCEPTED, resolved_at_utc=datetime.now(UTC),
                resulting_question_id="q1",
            )
        )


def test_resulting_decision_id_never_allowed_for_question_category():
    with pytest.raises(MendelRunError):
        MendelProposal(
            **_valid_proposal_kwargs(
                status=ProposalStatus.ACCEPTED, resolved_at_utc=datetime.now(UTC),
                resulting_decision_id="d1",
            )
        )


# ============================================================================
# MendelRun invariants.
# ============================================================================


def test_running_mendel_run_must_not_carry_completed_at_utc():
    from darwin.workshop.mendel_domain import InvocationPurpose

    with pytest.raises(MendelRunError):
        MendelRun(
            run_id="r1", workshop_id="w1", purpose=InvocationPurpose.REVIEW_DRAFT,
            focus_text=None, context_schema_version="V1", context_fingerprint="abc",
            provider_identity="test/1.0", status=RunStatus.RUNNING, started_at_utc=datetime.now(UTC),
            completed_at_utc=datetime.now(UTC),
        )


def test_terminal_mendel_run_requires_completed_at_utc():
    from darwin.workshop.mendel_domain import InvocationPurpose

    with pytest.raises(MendelRunError):
        MendelRun(
            run_id="r1", workshop_id="w1", purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None,
            context_schema_version="V1", context_fingerprint="abc", provider_identity="test/1.0",
            status=RunStatus.SUCCEEDED, started_at_utc=datetime.now(UTC),
        )


def test_terminal_mendel_run_with_completed_at_utc_is_valid():
    from darwin.workshop.mendel_domain import InvocationPurpose

    run = MendelRun(
        run_id="r1", workshop_id="w1", purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None,
        context_schema_version="V1", context_fingerprint="abc", provider_identity="test/1.0",
        status=RunStatus.SUCCEEDED, started_at_utc=datetime.now(UTC), completed_at_utc=datetime.now(UTC),
    )
    assert run.is_terminal is True


# ============================================================================
# NO_DRAFT_YET sentinel + staleness binding rule (PID-004C sec7.5).
# ============================================================================


def test_no_draft_yet_is_never_equal_to_a_real_revision():
    assert NO_DRAFT_YET != 0
    assert NO_DRAFT_YET != 1
    assert 0 != NO_DRAFT_YET
    assert NO_DRAFT_YET is not None


def test_no_draft_yet_is_a_stable_singleton():
    from darwin.workshop.mendel_domain import _NoDraftYetType

    assert _NoDraftYetType() is NO_DRAFT_YET


def test_is_stale_binding_same_real_revision_is_not_stale():
    assert is_stale_binding(3, 3) is False


def test_is_stale_binding_different_real_revision_is_stale():
    assert is_stale_binding(3, 4) is True


def test_is_stale_binding_no_draft_yet_matching_is_not_stale():
    assert is_stale_binding(NO_DRAFT_YET, NO_DRAFT_YET) is False


def test_is_stale_binding_no_draft_yet_against_a_real_revision_is_stale():
    assert is_stale_binding(NO_DRAFT_YET, 1) is True
    assert is_stale_binding(1, NO_DRAFT_YET) is True


# ============================================================================
# Context fingerprint determinism (PID-004C sec10.5).
# ============================================================================


def test_context_fingerprint_is_order_independent():
    doc_a = {"b": 1, "a": {"y": 2, "x": 1}}
    doc_b = {"a": {"x": 1, "y": 2}, "b": 1}
    assert compute_context_fingerprint("V1", doc_a) == compute_context_fingerprint("V1", doc_b)


def test_context_fingerprint_changes_with_real_content_difference():
    doc_a = {"a": 1}
    doc_b = {"a": 2}
    assert compute_context_fingerprint("V1", doc_a) != compute_context_fingerprint("V1", doc_b)


def test_context_fingerprint_changes_with_schema_version():
    doc = {"a": 1}
    assert compute_context_fingerprint("V1", doc) != compute_context_fingerprint("V2", doc)
