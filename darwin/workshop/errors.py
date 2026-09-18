"""PID-004B Strategy Workshop -- error hierarchy.

Mirrors `darwin.specification.errors`/`darwin.scout.domain`'s discipline:
every domain-invariant violation is a typed, code-bearing `DarwinError`
subclass, never a silent no-op and never a bare exception leaking
implementation detail.
"""
from __future__ import annotations

from darwin.core.errors import DarwinError


class WorkshopError(DarwinError):
    """Base class for all PID-004B Workshop domain errors."""

    code = "WORKSHOP_ERROR"


class WorkshopNotFoundError(WorkshopError):
    code = "WORKSHOP_NOT_FOUND"


class InvalidWorkshopReferenceError(WorkshopError):
    """A Workshop was asked to open/link against a `candidate_id` or
    `discovery_id` that does not resolve to a real, existing row. A
    Workshop must never be created as an orphan pointing at nothing
    (PID-004B: "refuse an invalid candidate_id/discovery_id at
    Workshop-open time, don't silently create an orphaned Workshop")."""

    code = "WORKSHOP_INVALID_REFERENCE"


class CrossWorkshopReferenceError(WorkshopError):
    """A caller referenced a question/decision/draft ID that exists, but
    does not belong to the Workshop named in the request. Never resolved
    by ID alone -- every lookup in this package is scoped to
    `(workshop_id, resource_id)` together, so an ID-substitution attack
    across two Workshops is structurally refused, not merely
    conventionally avoided."""

    code = "WORKSHOP_CROSS_REFERENCE_DENIED"


class WorkshopNotActiveError(WorkshopError):
    """An operation that only makes sense against an ACTIVE Workshop (e.g.
    authoring a draft, raising a question) was attempted against a
    FINALISED/ABANDONED one."""

    code = "WORKSHOP_NOT_ACTIVE"


class WorkshopHasNoDraftError(WorkshopError):
    """An operation that requires an existing SpecificationDraft (validate,
    finalise, read) was attempted before any draft has ever been created
    for this Workshop."""

    code = "WORKSHOP_HAS_NO_DRAFT"


class WorkspacePathViolationError(WorkshopError):
    """A filesystem operation inside a Workshop's bounded authoring
    workspace attempted to escape the Workshop's own directory -- via `..`
    traversal, an absolute path, an invalid Workshop id, or a symlink
    resolving outside the Workshop's own tree (PID-004 sec47/sec55).
    Refused explicitly; never silently clamped or partially honoured."""

    code = "WORKSHOP_WORKSPACE_PATH_VIOLATION"
