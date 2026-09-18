"""PID-004B Strategy Workshop FastAPI routes (`/api/v1/workshops/...`).

Wired into `darwin.app.create_app` (see `_mount_workshop_routes` there) --
kept in its own module purely to keep `darwin/app.py` from growing without
bound, not because these routes are a separate service (PID-004 sec53's
"No Workshop microservice" ruling still applies: this is the SAME FastAPI
process, mounted the same way SCOUT's routes are).

Deliberately narrow: every mutating endpoint below does exactly one
governed thing (open, raise a question, resolve one, propose/accept/
reject/supersede one decision, read/write the draft under optimistic
concurrency, validate, finalise). There is NO generic PATCH-anything route,
no route that accepts a caller-supplied filesystem path, and no route that
runs a command of any kind (PID-004 sec48) -- see
`darwin.workshop.workspace`'s own module docstring for the filesystem-side
half of that guarantee.

Every request model is module-level (not nested inside a function) for the
exact reason `darwin.app`'s own docstring gives: this file uses
`from __future__ import annotations` (PEP 563), and FastAPI resolves a
route's annotations via the endpoint function's `__globals__`, which never
sees a locally-scoped class.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from darwin.core.config import DarwinConfig
from darwin.core.health import ReadinessReport
from darwin.research_store.db import connection
from darwin.specification.provenance import RuleOrigin
from darwin.specification.serialization import serialize_specification_draft
from darwin.workshop import mendel_service, service
from darwin.workshop.claude_code_mendel_adapter import ClaudeCodeMendelAdapter
from darwin.workshop.domain import QuestionOrigin, QuestionStatus
from darwin.workshop.errors import WorkshopNotFoundError
from darwin.workshop.mendel_adapter import DeterministicTestMendelAdapter, MendelAdapter
from darwin.workshop.mendel_domain import (
    NO_DRAFT_YET,
    InvocationPurpose,
    ProposalStatus,
)
from darwin.workshop.mendel_errors import (
    MendelProposalNotFoundError,
    MendelRunNotFoundError,
)


class WorkshopOpenRequest(BaseModel):
    candidate_id: str = Field(min_length=1)
    discovery_ids: tuple[str, ...] = ()


class WorkshopQuestionCreateRequest(BaseModel):
    semantic_subject: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    rationale: str | None = None
    origin: QuestionOrigin = QuestionOrigin.HUMAN


class WorkshopQuestionResolveRequest(BaseModel):
    resolution: Literal["RESOLVED", "WITHDRAWN"]
    accepted_decision_id: str | None = None


class WorkshopDecisionCreateRequest(BaseModel):
    proposed_value: dict
    origin: RuleOrigin
    actor: str = Field(min_length=1)
    affected_semantic_paths: tuple[str, ...] = ()
    related_question_id: str | None = None
    rationale: str | None = None


class WorkshopDecisionRejectRequest(BaseModel):
    rationale: str | None = None


class WorkshopDecisionSupersedeRequest(BaseModel):
    proposed_value: dict
    actor: str = Field(min_length=1)
    affected_semantic_paths: tuple[str, ...] | None = None
    rationale: str | None = None


class WorkshopDraftUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    draft: dict
    schema_semantic_version: str | None = None


class WorkshopFinaliseRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    strategy_version_id: str | None = None
    version_label: str | None = None


class MendelInvokeRequest(BaseModel):
    """PID-004C sec11.1.1: `purpose` is validated by pydantic against the
    closed `InvocationPurpose` enum -- an out-of-vocabulary value is
    rejected with 422 before this request body is ever handed to
    `mendel_service.invoke_mendel`. There is deliberately no free-form
    `prompt` field anywhere on this model (PID-004C sec11.1.1/sec12: no
    generic invocation surface)."""

    purpose: InvocationPurpose
    focus_text: str | None = None


class MendelProposalAcceptRequest(BaseModel):
    actor: str = Field(min_length=1)


class MendelProposalRejectRequest(BaseModel):
    reason: str | None = None


def _workshop_dict(w) -> dict:
    return {
        "workshop_id": w.workshop_id,
        "candidate_id": w.candidate_id,
        "status": w.status.value,
        "discovery_ids": list(w.discovery_ids),
        "current_draft_id": w.current_draft_id,
        "finalised_strategy_version_id": w.finalised_strategy_version_id,
        "created_at_utc": w.created_at_utc,
        "updated_at_utc": w.updated_at_utc,
    }


def _question_dict(q) -> dict:
    return {
        "question_id": q.question_id, "workshop_id": q.workshop_id,
        "semantic_subject": q.semantic_subject, "question_text": q.question_text,
        "rationale": q.rationale, "status": q.status.value, "origin": q.origin.value,
        "accepted_decision_id": q.accepted_decision_id, "created_at_utc": q.created_at_utc,
        "resolved_at_utc": q.resolved_at_utc,
    }


def _decision_dict(d) -> dict:
    return {
        "decision_id": d.decision_id, "workshop_id": d.workshop_id,
        "proposed_value": d.proposed_value, "origin": d.origin.value, "actor": d.actor,
        "acceptance_state": d.acceptance_state.value,
        "affected_semantic_paths": list(d.affected_semantic_paths),
        "related_question_id": d.related_question_id, "rationale": d.rationale,
        "created_at_utc": d.created_at_utc, "superseded_by_decision_id": d.superseded_by_decision_id,
    }


def _validation_outcome_dict(outcome) -> dict:
    return {
        "status": outcome.status.value,
        "is_valid": outcome.is_valid,
        "findings": [
            {"stage": f.stage, "code": f.code, "message": f.message, "path": f.path} for f in outcome.findings
        ],
    }


def _mendel_run_dict(run) -> dict:
    return {
        "run_id": run.run_id, "workshop_id": run.workshop_id, "purpose": run.purpose.value,
        "focus_text": run.focus_text, "context_schema_version": run.context_schema_version,
        "context_fingerprint": run.context_fingerprint, "provider_identity": run.provider_identity,
        "status": run.status.value, "started_at_utc": run.started_at_utc,
        "completed_at_utc": run.completed_at_utc, "error_classification": run.error_classification,
    }


def _mendel_proposal_dict(proposal) -> dict:
    binding = proposal.generated_against_draft_revision
    return {
        "proposal_id": proposal.proposal_id, "run_id": proposal.run_id, "workshop_id": proposal.workshop_id,
        "proposal_class": proposal.proposal_class.value, "proposal_category": proposal.proposal_category.value,
        "proposal_schema_version": proposal.proposal_schema_version, "payload": proposal.payload,
        "rationale": proposal.rationale, "affected_semantic_paths": list(proposal.affected_semantic_paths),
        "generated_against_draft_revision": "NO_DRAFT_YET" if binding is NO_DRAFT_YET else binding,
        "status": proposal.status.value, "created_at_utc": proposal.created_at_utc,
        "resolved_at_utc": proposal.resolved_at_utc,
        "resulting_question_id": proposal.resulting_question_id,
        "resulting_decision_id": proposal.resulting_decision_id,
    }


def register_mendel_routes(
    app: FastAPI, cfg: DarwinConfig, *, adapter: MendelAdapter | None = None,
    ensure_ready_for_data: Callable[[ReadinessReport], None], readiness: Callable[[DarwinConfig], ReadinessReport],
) -> None:
    """PID-004C sec12 -- Workshop-scoped MENDEL endpoints, mounted the same
    way `register_workshop_routes` is (same FastAPI process -- PID-004C
    sec22: no standalone MENDEL microservice).

    `adapter` is a deliberate, narrow dependency-injection point (PID-004C
    sec11.4's own directive: "wire the real adapter selection as a
    config/DI point") -- an explicit caller-supplied adapter (tests, or a
    future deployment-specific override) always wins outright. Absent
    that, PID-004C WP2's own default selection is config-driven and safe:
    `ClaudeCodeMendelAdapter` (the real Claude Code CLI integration) is
    used ONLY when `cfg.mendel_provider_api_key` is actually configured
    (`darwin.core.config.resolve_mendel_provider_api_key` -- the
    `DARWIN_MENDEL_PROVIDER_API_KEY_FILE` secret-file slot); otherwise
    this falls back to `DeterministicTestMendelAdapter`, an HONEST interim
    state, not a hidden placeholder -- `darwin_core` must never fail to
    start, nor silently misbehave, just because MENDEL's real provider
    credential has not been provisioned yet. Constructing
    `ClaudeCodeMendelAdapter` itself calls the real `claude` CLI's own
    `--version` (see that class's docstring) -- if the `claude` binary is
    missing entirely despite a credential being configured, that failure
    surfaces here, at startup, not silently deferred to the first
    invocation.
    """
    if adapter is not None:
        resolved_adapter: MendelAdapter = adapter
    elif cfg.mendel_provider_api_key:
        resolved_adapter = ClaudeCodeMendelAdapter(api_key=cfg.mendel_provider_api_key)
    else:
        resolved_adapter = DeterministicTestMendelAdapter()

    def _run_not_found(exc: MendelRunNotFoundError) -> HTTPException:
        return HTTPException(status_code=404, detail=str(exc))

    def _proposal_not_found(exc: MendelProposalNotFoundError) -> HTTPException:
        return HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/v1/workshops/{workshop_id}/mendel/invoke")
    def invoke_mendel_endpoint(workshop_id: str, body: MendelInvokeRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                run = mendel_service.invoke_mendel(
                    conn, workshop_id, purpose=body.purpose, focus_text=body.focus_text,
                    adapter=resolved_adapter,
                )
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"run": _mendel_run_dict(run)}

    @app.get("/api/v1/workshops/{workshop_id}/mendel/runs")
    def list_mendel_runs_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                runs = mendel_service.list_runs(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"items": [_mendel_run_dict(r) for r in runs]}

    @app.get("/api/v1/workshops/{workshop_id}/mendel/runs/{run_id}")
    def get_mendel_run_endpoint(workshop_id: str, run_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                run = mendel_service.get_run(conn, workshop_id, run_id)
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except MendelRunNotFoundError as exc:
                raise _run_not_found(exc) from exc
        return {"run": _mendel_run_dict(run)}

    @app.get("/api/v1/workshops/{workshop_id}/mendel/proposals")
    def list_mendel_proposals_endpoint(workshop_id: str, status: str | None = None) -> dict:
        ensure_ready_for_data(readiness(cfg))
        parsed_status = ProposalStatus(status) if status is not None else None
        with connection(cfg.postgres) as conn:
            try:
                proposals = mendel_service.list_proposals(conn, workshop_id, status=parsed_status)
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"items": [_mendel_proposal_dict(p) for p in proposals]}

    @app.post("/api/v1/workshops/{workshop_id}/mendel/proposals/{proposal_id}/accept")
    def accept_mendel_proposal_endpoint(
        workshop_id: str, proposal_id: str, body: MendelProposalAcceptRequest
    ) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                proposal = mendel_service.accept_proposal(conn, workshop_id, proposal_id, actor=body.actor)
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except MendelProposalNotFoundError as exc:
                raise _proposal_not_found(exc) from exc
        return {"proposal": _mendel_proposal_dict(proposal)}

    @app.post("/api/v1/workshops/{workshop_id}/mendel/proposals/{proposal_id}/reject")
    def reject_mendel_proposal_endpoint(
        workshop_id: str, proposal_id: str, body: MendelProposalRejectRequest
    ) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                proposal = mendel_service.reject_proposal(conn, workshop_id, proposal_id, reason=body.reason)
            except WorkshopNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except MendelProposalNotFoundError as exc:
                raise _proposal_not_found(exc) from exc
        return {"proposal": _mendel_proposal_dict(proposal)}


def register_workshop_routes(
    app: FastAPI, cfg: DarwinConfig, *, ensure_ready_for_data: Callable[[ReadinessReport], None],
    readiness: Callable[[DarwinConfig], ReadinessReport],
) -> None:
    def _not_found(exc: WorkshopNotFoundError) -> HTTPException:
        return HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/v1/workshops")
    def open_workshop_endpoint(body: WorkshopOpenRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            workshop = service.open_workshop(
                conn, candidate_id=body.candidate_id, discovery_ids=body.discovery_ids
            )
        return {"workshop": _workshop_dict(workshop)}

    @app.get("/api/v1/workshops/{workshop_id}")
    def get_workshop_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                workshop = service.get_workshop(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"workshop": _workshop_dict(workshop)}

    @app.get("/api/v1/workshops/{workshop_id}/questions")
    def list_questions_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                questions = service.list_questions(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"items": [_question_dict(q) for q in questions]}

    @app.post("/api/v1/workshops/{workshop_id}/questions")
    def create_question_endpoint(workshop_id: str, body: WorkshopQuestionCreateRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                question = service.create_question(
                    conn, workshop_id, semantic_subject=body.semantic_subject,
                    question_text=body.question_text, rationale=body.rationale, origin=body.origin,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"question": _question_dict(question)}

    @app.post("/api/v1/workshops/{workshop_id}/questions/{question_id}/resolve")
    def resolve_question_endpoint(
        workshop_id: str, question_id: str, body: WorkshopQuestionResolveRequest
    ) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                question = service.resolve_question(
                    conn, workshop_id, question_id, resolution=QuestionStatus(body.resolution),
                    accepted_decision_id=body.accepted_decision_id,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"question": _question_dict(question)}

    @app.get("/api/v1/workshops/{workshop_id}/decisions")
    def list_decisions_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                decisions = service.list_decisions(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"items": [_decision_dict(d) for d in decisions]}

    @app.post("/api/v1/workshops/{workshop_id}/decisions")
    def create_decision_endpoint(workshop_id: str, body: WorkshopDecisionCreateRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                decision = service.create_decision(
                    conn, workshop_id, proposed_value=body.proposed_value, origin=body.origin,
                    actor=body.actor, affected_semantic_paths=body.affected_semantic_paths,
                    related_question_id=body.related_question_id, rationale=body.rationale,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"decision": _decision_dict(decision)}

    @app.post("/api/v1/workshops/{workshop_id}/decisions/{decision_id}/accept")
    def accept_decision_endpoint(workshop_id: str, decision_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                decision = service.accept_decision(conn, workshop_id, decision_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"decision": _decision_dict(decision)}

    @app.post("/api/v1/workshops/{workshop_id}/decisions/{decision_id}/reject")
    def reject_decision_endpoint(
        workshop_id: str, decision_id: str, body: WorkshopDecisionRejectRequest
    ) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                decision = service.reject_decision(conn, workshop_id, decision_id, rationale=body.rationale)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"decision": _decision_dict(decision)}

    @app.post("/api/v1/workshops/{workshop_id}/decisions/{decision_id}/supersede")
    def supersede_decision_endpoint(
        workshop_id: str, decision_id: str, body: WorkshopDecisionSupersedeRequest
    ) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                decision = service.supersede_decision(
                    conn, workshop_id, decision_id, proposed_value=body.proposed_value, actor=body.actor,
                    affected_semantic_paths=body.affected_semantic_paths, rationale=body.rationale,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"decision": _decision_dict(decision)}

    @app.get("/api/v1/workshops/{workshop_id}/draft")
    def get_draft_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                draft, revision = service.get_draft(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        if draft is None:
            return {"draft": None, "revision": None}
        return {"draft": serialize_specification_draft(draft), "revision": revision}

    @app.put("/api/v1/workshops/{workshop_id}/draft")
    def update_draft_endpoint(workshop_id: str, body: WorkshopDraftUpdateRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                draft, revision = service.update_draft(
                    conn, workshop_id, expected_revision=body.expected_revision, draft_document=body.draft,
                    schema_semantic_version=body.schema_semantic_version,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"draft": serialize_specification_draft(draft), "revision": revision}

    @app.post("/api/v1/workshops/{workshop_id}/validate")
    def validate_workshop_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                outcome = service.validate_workshop_draft(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"validation": _validation_outcome_dict(outcome)}

    @app.post("/api/v1/workshops/{workshop_id}/finalise")
    def finalise_workshop_endpoint(workshop_id: str, body: WorkshopFinaliseRequest) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                outcome = service.finalise_workshop(
                    conn, workshop_id, expected_revision=body.expected_revision,
                    strategy_version_id=body.strategy_version_id, version_label=body.version_label,
                )
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
            workshop = service.get_workshop(conn, workshop_id)
        return {
            "validation": _validation_outcome_dict(outcome.outcome),
            "strategy_version_id": (
                outcome.strategy_version.strategy_version_id if outcome.strategy_version else None
            ),
            "candidate_advanced": outcome.candidate_advanced,
            "workshop": _workshop_dict(workshop),
        }

    # --- readiness (Workshop UI enablement -- see darwin.workshop.service's
    # own module comment for why this exists: PID-004A's
    # DataReadinessAssessment/DataReadinessAssessmentRepository already
    # existed but had no HTTP surface at all before this) -------------------

    @app.get("/api/v1/workshops/{workshop_id}/readiness")
    def get_workshop_readiness_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                result = service.get_readiness(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"readiness": result}

    @app.post("/api/v1/workshops/{workshop_id}/readiness/assess")
    def assess_workshop_readiness_endpoint(workshop_id: str) -> dict:
        ensure_ready_for_data(readiness(cfg))
        with connection(cfg.postgres) as conn:
            try:
                result = service.assess_workshop_readiness(conn, workshop_id)
            except WorkshopNotFoundError as exc:
                raise _not_found(exc) from exc
        return {"readiness": result}
