"""PID-004C MENDEL Workshop Assistant -- error hierarchy.

Mirrors `darwin.workshop.errors`'s discipline: every domain-invariant
violation is a typed, code-bearing `DarwinError` subclass, never a silent
no-op and never a bare exception leaking implementation detail. Kept in
its own module (rather than extending `darwin.workshop.errors` in place)
because PID-004C's error vocabulary is genuinely new domain territory
(runs/proposals/adapter output) layered on top of, not a variant of, the
existing PID-004B Workshop errors -- `darwin.workshop.errors.WorkshopError`
subclasses (`WorkshopNotFoundError`, `WorkshopNotActiveError`, ...) are
still raised unchanged wherever a MENDEL operation first checks ordinary
Workshop state.
"""
from __future__ import annotations

from darwin.core.errors import DarwinError


class MendelError(DarwinError):
    """Base class for all PID-004C MENDEL domain errors."""

    code = "MENDEL_ERROR"


class MendelRunError(MendelError):
    """A `MendelRun`/`MendelProposal` construction-time invariant was
    violated (e.g. a terminal status missing `completed_at_utc`)."""

    code = "MENDEL_RUN_ERROR"


class MendelRunNotFoundError(MendelError):
    code = "MENDEL_RUN_NOT_FOUND"


class MendelProposalNotFoundError(MendelError):
    code = "MENDEL_PROPOSAL_NOT_FOUND"


class MendelProposalClassCategoryMismatchError(MendelError):
    """A `MendelProposal` was constructed (or a raw adapter proposal was
    validated) with a `proposal_class`/`proposal_category` pair that
    disagrees with the fixed, closed `PROPOSAL_CLASS_CATEGORY` mapping
    (PID-004C sec6.4) -- never inferred/coerced, always refused."""

    code = "MENDEL_PROPOSAL_CLASS_CATEGORY_MISMATCH"


class MendelProposalStaleError(MendelError):
    """Acceptance was attempted against a `MendelProposal` that is (or has
    just been discovered to be) bound to a `SpecificationDraft` revision
    binding that is no longer current (PID-004C sec7.5). Acceptance is
    refused; the proposal is marked `STALE`; no mutation occurs."""

    code = "MENDEL_PROPOSAL_STALE"


class MendelProposalNotApplicableError(MendelError):
    """An operation was attempted against a `MendelProposal` in the wrong
    state or category for that operation -- e.g. accepting a proposal that
    is already `ACCEPTED`/`REJECTED`, or a category-dispatch path being
    asked to handle a proposal outside the category it governs."""

    code = "MENDEL_PROPOSAL_NOT_APPLICABLE"


class MendelOutputValidationError(MendelError):
    """A `MendelAdapter`'s raw output failed the PID-004C sec18 validation
    pipeline (unrecognised `proposal_schema_version`, a class/category
    mismatch, a payload that does not match its class's closed typed
    shape, or an out-of-vocabulary value). Raised internally by
    `darwin.workshop.mendel_service.invoke_mendel`'s own pipeline, which
    catches it, marks the `MendelRun` `FAILED` with this error's message as
    the classification, and persists ZERO proposals -- never propagated
    out of `invoke_mendel` as an unhandled exception."""

    code = "MENDEL_OUTPUT_VALIDATION_ERROR"


class MendelAdapterTimeoutError(MendelError):
    """Raised BY a `MendelAdapter` implementation (never by Workshop/
    domain code) to signal a timeout specifically, distinct from any other
    adapter failure -- `invoke_mendel` maps this to `MendelRun.status =
    TIMEOUT` rather than the generic `FAILED`."""

    code = "MENDEL_ADAPTER_TIMEOUT"
