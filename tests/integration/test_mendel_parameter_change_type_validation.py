"""PID-004C closure-hardening (Architect-directed real-defect fix,
2026-09-19): `PARAMETER_CHANGE`'s declared `value_type` must agree
EXACTLY with `fixed_value`'s actual shape, or the whole proposal must be
refused BEFORE persistence.

The Auditor's own reproduction: `RawMendelProposal(proposal_class=
"PARAMETER_CHANGE", payload={"parameter_id":"max_daily_trades",
"value_type":"INTEGER","unit":None,"fixed_value":{}})` used to pass
`invoke_mendel`'s validation pipeline (`MendelRun.status = SUCCEEDED`, one
`MendelProposal` row persisted as `PROPOSED`), because nothing in the
dry-run handler check cross-checked `value_type` against `fixed_value`'s
actual Python type -- the mismatch was only discovered LATER, at accept
time, when `serialize_specification_draft` tried to encode the mutated
draft and raised an uncaught `SerializationError`.

This file proves, for the required negative matrix (every case ends
`MendelRun.status = FAILED`, ZERO `MendelProposal` rows persisted --
queried directly from the DB, never trusted from the returned object --
and Workshop canonical draft revision unchanged), for the exact original
Auditor reproduction, and for positive controls (every supported
value_type is still accepted, persists, and -- for DECIMAL -- accepted
all the way through to a real draft mutation, proving the whole pipeline
still works end to end for legitimate values).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from psycopg.rows import dict_row

from darwin.research_store.db import connection
from darwin.specification.provenance import RuleOrigin
from darwin.workshop import mendel_service, service
from darwin.workshop.mendel_adapter import (
    DeterministicTestMendelAdapter,
    MendelInvocationResult,
    RawMendelProposal,
)
from darwin.workshop.mendel_domain import InvocationPurpose, ProposalStatus, RunStatus
from darwin.workshop.mendel_service import PROPOSAL_SCHEMA_VERSION
from tests.fixtures.mendel import open_workshop_with_draft

pytestmark = pytest.mark.integration


def _parameter_change_proposal(payload: dict, *, rationale: str) -> RawMendelProposal:
    return RawMendelProposal(
        proposal_class="PARAMETER_CHANGE", proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
        payload=payload, rationale=rationale,
    )


def _invoke_single(conn, workshop_id, payload: dict, *, rationale: str):
    proposal = _parameter_change_proposal(payload, rationale=rationale)
    adapter = DeterministicTestMendelAdapter(
        result=MendelInvocationResult(proposals=(proposal,), reasoning_summary="type-validation probe")
    )
    return mendel_service.invoke_mendel(
        conn, workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter
    )


def _assert_failed_closed(conn, workshop_id: str, run, revision_before: int) -> None:
    assert run.status == RunStatus.FAILED
    assert run.error_classification
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM mendel_proposals WHERE run_id = %s", (run.run_id,))
        assert cur.fetchone()["n"] == 0
    assert mendel_service.list_proposals(conn, workshop_id) == []
    _, current_revision = service.get_draft(conn, workshop_id)
    assert current_revision == revision_before


# ============================================================================
# The exact original Auditor reproduction.
# ============================================================================


def test_auditor_original_reproduction_integer_value_type_empty_dict_fixed_value_fails_closed(pg_config):
    with connection(pg_config) as conn:
        workshop, revision = open_workshop_with_draft(conn)
        run = _invoke_single(
            conn, workshop.workshop_id,
            {"parameter_id": "max_daily_trades", "value_type": "INTEGER", "unit": None, "fixed_value": {}},
            rationale="Auditor's exact original reproduction: INTEGER + {}",
        )
        _assert_failed_closed(conn, workshop.workshop_id, run, revision)


# ============================================================================
# Required negative matrix.
# ============================================================================

NEGATIVE_MATRIX: list[tuple[str, dict]] = [
    (
        "integer_plus_dict",
        {"parameter_id": "p", "value_type": "INTEGER", "unit": None, "fixed_value": {"nested": "object"}},
    ),
    (
        "integer_plus_bool_true",
        {"parameter_id": "p", "value_type": "INTEGER", "unit": None, "fixed_value": True},
    ),
    (
        "integer_plus_bool_false",
        {"parameter_id": "p", "value_type": "INTEGER", "unit": None, "fixed_value": False},
    ),
    (
        "integer_plus_string",
        {"parameter_id": "p", "value_type": "INTEGER", "unit": None, "fixed_value": "5"},
    ),
    (
        "boolean_plus_integer_one",
        {"parameter_id": "p", "value_type": "BOOLEAN", "unit": None, "fixed_value": 1},
    ),
    (
        "boolean_plus_integer_zero",
        {"parameter_id": "p", "value_type": "BOOLEAN", "unit": None, "fixed_value": 0},
    ),
    (
        "boolean_plus_string",
        {"parameter_id": "p", "value_type": "BOOLEAN", "unit": None, "fixed_value": "true"},
    ),
    (
        "string_plus_dict",
        {"parameter_id": "p", "value_type": "STRING", "unit": None, "fixed_value": {"a": 1}},
    ),
    (
        "string_plus_list",
        {"parameter_id": "p", "value_type": "STRING", "unit": None, "fixed_value": ["a", "b"]},
    ),
    (
        "duration_seconds_plus_bool",
        {"parameter_id": "p", "value_type": "DURATION_SECONDS", "unit": None, "fixed_value": True},
    ),
    (
        "duration_seconds_plus_float",
        {"parameter_id": "p", "value_type": "DURATION_SECONDS", "unit": None, "fixed_value": 3.5},
    ),
    (
        "duration_seconds_plus_string",
        {"parameter_id": "p", "value_type": "DURATION_SECONDS", "unit": None, "fixed_value": "5"},
    ),
    (
        "decimal_plus_raw_json_float",
        {"parameter_id": "p", "value_type": "DECIMAL", "unit": None, "fixed_value": 3.14},
    ),
    (
        "decimal_plus_raw_json_int_no_wrapper",
        {"parameter_id": "p", "value_type": "DECIMAL", "unit": None, "fixed_value": 3},
    ),
    (
        "decimal_plus_non_numeric_wrapped_string",
        {"parameter_id": "p", "value_type": "DECIMAL", "unit": None, "fixed_value": {"__decimal__": "not-a-number"}},
    ),
    (
        "decimal_plus_wrapped_binary_float",
        {"parameter_id": "p", "value_type": "DECIMAL", "unit": None, "fixed_value": {"__decimal__": 3.14}},
    ),
]

assert {case_id for case_id, _ in NEGATIVE_MATRIX} == {c for c, _ in NEGATIVE_MATRIX}, "case ids must be unique"


@pytest.mark.parametrize("case_id,payload", NEGATIVE_MATRIX, ids=[c for c, _ in NEGATIVE_MATRIX])
def test_parameter_change_negative_matrix_fails_closed(pg_config, case_id, payload):
    with connection(pg_config) as conn:
        workshop, revision = open_workshop_with_draft(conn)
        run = _invoke_single(conn, workshop.workshop_id, payload, rationale=f"negative matrix case: {case_id}")
        _assert_failed_closed(conn, workshop.workshop_id, run, revision)


# ============================================================================
# Positive controls -- every supported value_type is still accepted and
# persists.
# ============================================================================

POSITIVE_MATRIX: list[tuple[str, dict]] = [
    ("integer", {"parameter_id": "p", "value_type": "INTEGER", "unit": None, "fixed_value": 3}),
    ("boolean", {"parameter_id": "p", "value_type": "BOOLEAN", "unit": None, "fixed_value": True}),
    ("string", {"parameter_id": "p", "value_type": "STRING", "unit": None, "fixed_value": "EXPLICIT_SINGLE"}),
    (
        "duration_seconds",
        {"parameter_id": "p", "value_type": "DURATION_SECONDS", "unit": "seconds", "fixed_value": 900},
    ),
    (
        "decimal",
        {"parameter_id": "p", "value_type": "DECIMAL", "unit": "USD", "fixed_value": {"__decimal__": "3.14"}},
    ),
]


@pytest.mark.parametrize("case_id,payload", POSITIVE_MATRIX, ids=[c for c, _ in POSITIVE_MATRIX])
def test_parameter_change_positive_controls_persist_as_proposed(pg_config, case_id, payload):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        run = _invoke_single(conn, workshop.workshop_id, payload, rationale=f"positive control: {case_id}")
        assert run.status == RunStatus.SUCCEEDED, (
            f"{case_id}: expected a genuinely well-typed payload to pass validation, got "
            f"{run.status.value}: {run.error_classification}"
        )
        proposals = mendel_service.list_proposals(conn, workshop.workshop_id)
        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.PROPOSED


def test_decimal_positive_control_accepts_full_round_trip_through_to_real_draft_mutation(pg_config):
    """The DECIMAL case, taken all the way through acceptance, proving the
    whole pipeline still works end to end for a legitimate value -- not
    merely that invoke_mendel's dry-run accepts the shape."""
    with connection(pg_config) as conn:
        workshop, revision = open_workshop_with_draft(conn)
        payload = {
            "parameter_id": "risk_multiplier", "value_type": "DECIMAL", "unit": "ratio",
            "fixed_value": {"__decimal__": "1.75"},
        }
        run = _invoke_single(conn, workshop.workshop_id, payload, rationale="DECIMAL full round trip")
        assert run.status == RunStatus.SUCCEEDED

        proposal = mendel_service.list_proposals(conn, workshop.workshop_id)[0]
        accepted = mendel_service.accept_proposal(conn, workshop.workshop_id, proposal.proposal_id, actor="matt")
        assert accepted.status == ProposalStatus.ACCEPTED
        assert accepted.resulting_decision_id is not None

        draft, current_revision = service.get_draft(conn, workshop.workshop_id)
        assert current_revision == revision + 1
        stored = draft.fixed_parameters["risk_multiplier"]
        assert isinstance(stored.fixed_value, Decimal)
        assert stored.fixed_value == Decimal("1.75")

        decisions = service.list_decisions(conn, workshop.workshop_id)
        matching = [d for d in decisions if d.decision_id == accepted.resulting_decision_id]
        assert len(matching) == 1
        assert matching[0].origin == RuleOrigin.WORKSHOP_PROPOSAL

        # Round-trips through the real serializer without error -- the
        # exact operation that used to raise an uncaught SerializationError
        # for a mismatched DECIMAL payload.
        from darwin.specification.serialization import serialize_specification_draft

        document = serialize_specification_draft(draft)
        assert document["fixed_parameters"]["risk_multiplier"]["fixed_value"] == {"__decimal__": "1.75"}
