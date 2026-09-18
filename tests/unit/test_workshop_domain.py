"""PID-004B Workshop domain-model unit tests -- pure construction-time
invariants, no database required. Mirrors
tests/unit/test_specification_domain_and_validation.py's style."""
from __future__ import annotations

import pytest

from darwin.specification.provenance import RuleOrigin
from darwin.workshop.domain import (
    DecisionAcceptanceState,
    QuestionOrigin,
    QuestionStatus,
    StrategyWorkshop,
    WorkshopDecision,
    WorkshopQuestion,
    WorkshopStatus,
)
from darwin.workshop.errors import WorkshopError


def test_active_workshop_requires_no_finalised_strategy_version_id():
    with pytest.raises(WorkshopError):
        StrategyWorkshop(
            workshop_id="w1", candidate_id="c1", status=WorkshopStatus.ACTIVE,
            finalised_strategy_version_id="sv1",
        )


def test_finalised_workshop_requires_finalised_strategy_version_id():
    with pytest.raises(WorkshopError):
        StrategyWorkshop(workshop_id="w1", candidate_id="c1", status=WorkshopStatus.FINALISED)


def test_finalised_workshop_with_version_id_is_valid():
    w = StrategyWorkshop(
        workshop_id="w1", candidate_id="c1", status=WorkshopStatus.FINALISED,
        finalised_strategy_version_id="sv1",
    )
    assert w.is_active is False


def test_active_workshop_is_active_property():
    w = StrategyWorkshop(workshop_id="w1", candidate_id="c1", status=WorkshopStatus.ACTIVE)
    assert w.is_active is True


def test_workshop_requires_non_empty_ids():
    with pytest.raises(WorkshopError):
        StrategyWorkshop(workshop_id="", candidate_id="c1", status=WorkshopStatus.ACTIVE)
    with pytest.raises(WorkshopError):
        StrategyWorkshop(workshop_id="w1", candidate_id="", status=WorkshopStatus.ACTIVE)


def test_open_question_must_not_carry_resolved_at():
    from datetime import UTC, datetime

    with pytest.raises(WorkshopError):
        WorkshopQuestion(
            question_id="q1", workshop_id="w1", semantic_subject="composition",
            question_text="what?", status=QuestionStatus.OPEN, resolved_at_utc=datetime.now(UTC),
        )


def test_resolved_question_requires_resolved_at():
    with pytest.raises(WorkshopError):
        WorkshopQuestion(
            question_id="q1", workshop_id="w1", semantic_subject="composition",
            question_text="what?", status=QuestionStatus.RESOLVED,
        )


def test_question_requires_non_empty_text_and_subject():
    with pytest.raises(WorkshopError):
        WorkshopQuestion(question_id="q1", workshop_id="w1", semantic_subject="", question_text="what?")
    with pytest.raises(WorkshopError):
        WorkshopQuestion(question_id="q1", workshop_id="w1", semantic_subject="x", question_text="")


def test_question_origin_default_is_human():
    q = WorkshopQuestion(question_id="q1", workshop_id="w1", semantic_subject="x", question_text="y")
    assert q.origin == QuestionOrigin.HUMAN


def test_decision_requires_non_empty_actor():
    with pytest.raises(WorkshopError):
        WorkshopDecision(
            decision_id="d1", workshop_id="w1", proposed_value={"x": 1}, origin=RuleOrigin.SOURCE_RULE,
            actor="",
        )


def test_decision_superseded_by_requires_superseded_state():
    with pytest.raises(WorkshopError):
        WorkshopDecision(
            decision_id="d1", workshop_id="w1", proposed_value={"x": 1}, origin=RuleOrigin.SOURCE_RULE,
            actor="matt", acceptance_state=DecisionAcceptanceState.ACCEPTED,
            superseded_by_decision_id="d2",
        )


def test_decision_default_acceptance_state_is_proposed():
    d = WorkshopDecision(
        decision_id="d1", workshop_id="w1", proposed_value={"x": 1}, origin=RuleOrigin.WORKSHOP_PROPOSAL,
        actor="matt",
    )
    assert d.acceptance_state == DecisionAcceptanceState.PROPOSED


def test_decision_origin_reuses_specification_provenance_rule_origin_vocabulary():
    """PID-004B directive: decision origin must reuse the EXACT same closed
    vocabulary PID-004A's provenance model defines, never a second one."""
    assert {o.value for o in RuleOrigin} == {"SOURCE_RULE", "USER_CLARIFICATION", "WORKSHOP_PROPOSAL"}
    d = WorkshopDecision(
        decision_id="d1", workshop_id="w1", proposed_value={"x": 1}, origin=RuleOrigin.USER_CLARIFICATION,
        actor="matt",
    )
    assert isinstance(d.origin, RuleOrigin)
