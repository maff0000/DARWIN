"""PID-004C sec11.4 -- the `MendelAdapter` boundary.

The ONLY seam `darwin.workshop.mendel_service`/`darwin.workshop.api`
depend on. Workshop/domain code never imports a Claude-specific SDK type
here -- the contract is exactly bounded-context-in, typed-proposal-set-out
(PID-004C sec11.3):

    bounded typed context (BoundedMendelContext) + bounded task
        -> MendelAdapter.invoke(...)
        -> a RawMendelProposal set + a bounded reasoning summary
           (or a MendelAdapterTimeoutError / any other exception, which
           `invoke_mendel` maps to MendelRun.status TIMEOUT/FAILED --
           never propagated into canonical Workshop state)

`RawMendelProposal` is deliberately the adapter's OWN raw, only
loosely-typed output shape (a plain string class name, a plain dict
payload) -- it is NOT `darwin.workshop.mendel_domain.MendelProposal`.
`darwin.workshop.mendel_service.invoke_mendel`'s output-validation
pipeline (PID-004C sec18) is what turns a `RawMendelProposal` into a real,
construction-validated `MendelProposal` (or refuses it) -- this module
never performs that validation itself, so there is exactly one place
(`invoke_mendel`) that decides whether adapter output is trustworthy.

# TODO(PID-004C WP2): real Claude Code MendelAdapter.
This work package (WP1) defines the interface and ships exactly one
concrete implementation, `DeterministicTestMendelAdapter` -- a
fixture-driven test double, never the real Claude Code subprocess
integration. Wiring the actual Claude Code CLI/SDK boundary (PID-004C
sec11.4's "Claude Code / future specialist implementation") -- including
which exact CLI flags/transport to use, how `provider_identity` is
derived from a real model/version string, and how the zero-tool
constraint (PID-004C sec11.3) is enforced against a real Claude Code
invocation -- is explicitly out of scope here and is a separate,
later work package's job. Do not guess at CLI flags.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from darwin.workshop.mendel_domain import InvocationPurpose
from darwin.workshop.mendel_errors import MendelAdapterTimeoutError

__all__ = [
    "BoundedMendelContext",
    "DeterministicTestMendelAdapter",
    "MendelAdapter",
    "MendelAdapterTimeoutError",
    "MendelInvocationResult",
    "RawMendelProposal",
]


@dataclass(frozen=True)
class BoundedMendelContext:
    """The finished, bounded context package DARWIN assembles and hands to
    MENDEL (PID-004C sec8.1) -- MENDEL is never given ambient database
    access. Built exclusively by `darwin.workshop.mendel_context.
    build_bounded_context`; this module only names the shape the adapter
    boundary accepts.

    `schema_version` is `context_schema_version` (PID-004C sec10.1/sec10.5)
    -- the version the context's own canonical-serialisation/fingerprint
    contract was assembled under. `document` is the complete, JSON-safe,
    canonically-serialisable bounded package (candidate identity, linked
    discovery, questions, decisions, draft-or-NO_DRAFT_YET, validation
    findings, data requirements, readiness, DraftCapabilityView) -- see
    `darwin.workshop.mendel_context` for exactly what it contains.
    """

    schema_version: str
    fingerprint: str
    document: Mapping[str, object]


@dataclass(frozen=True)
class RawMendelProposal:
    """One adapter-produced proposal, in the adapter's own raw output
    shape -- BEFORE `invoke_mendel`'s validation pipeline (PID-004C sec18)
    has run. `proposal_class` is a plain string here deliberately (not yet
    a validated `ProposalClass`) -- an out-of-vocabulary value is exactly
    what the malformed-output proof (PID-004C sec15, this WP's own test
    suite) exercises."""

    proposal_class: str
    proposal_schema_version: str
    payload: dict
    rationale: str
    affected_semantic_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class MendelInvocationResult:
    """MENDEL's complete output for one bounded invocation (PID-004C
    sec11.3): a typed proposal set + a bounded reasoning summary. Never
    anything else -- no tool-call log, no follow-up prompt, no
    conversational state to carry into a later invocation (PID-004C
    sec11.2: "no persistent conversational memory")."""

    proposals: tuple[RawMendelProposal, ...]
    reasoning_summary: str


class MendelAdapter(ABC):
    """The abstract boundary (PID-004C sec11.4). A concrete implementation
    (the real Claude Code integration, or a test double) knows nothing
    about `darwin.workshop`'s persistence/service layer -- it only ever
    receives a `BoundedMendelContext` + a purpose/focus and returns a
    `MendelInvocationResult`, or raises."""

    @property
    @abstractmethod
    def provider_identity(self) -> str:
        """A stable model/adapter identity + version string (PID-004C
        sec10.1) -- persisted on every `MendelRun`, never on
        `StrategyVersion` (PID-004C sec10.4)."""

    @abstractmethod
    def invoke(
        self, *, context: BoundedMendelContext, purpose: InvocationPurpose, focus_text: str | None
    ) -> MendelInvocationResult:
        """Raises `MendelAdapterTimeoutError` for a timeout specifically,
        or any other exception for any other invocation failure -- both
        are caught by `darwin.workshop.mendel_service.invoke_mendel`,
        never expected to be caught by the caller of `invoke_mendel`
        itself."""


class DeterministicTestMendelAdapter(MendelAdapter):
    """Fixture-driven test double (PID-004C WP1's ONLY concrete adapter).
    Never a real model call -- used for every non-provider test in this
    work package (unit/integration/API), and as the WIRED-IN default
    behind the `/mendel/invoke` endpoint until a later work package
    replaces it with the real Claude Code adapter (PID-004C sec11.4;
    darwin.workshop.api's own docstring/comment on that endpoint states
    this explicitly -- it is an honest interim default, not a hidden
    placeholder).

    Constructed with either:
    * `result` -- a single fixed `MendelInvocationResult` returned for
      every invocation, or
    * `results_by_purpose` -- a `{InvocationPurpose: MendelInvocationResult}`
      mapping, so a single test double can script different responses per
      bounded task, or
    * `raises` -- an exception instance raised on every `invoke()` call
      (used for the timeout/failure proofs).

    Also records every call it receives (`calls`), so a test can assert on
    exactly what bounded context/purpose/focus_text the caller assembled
    and handed over -- useful for proving prompt-injection containment
    (the hostile text arrives as inert `context.document` data, never as
    something that changes which branch of THIS test double's own
    programmed logic runs).
    """

    def __init__(
        self,
        *,
        result: MendelInvocationResult | None = None,
        results_by_purpose: Mapping[InvocationPurpose, MendelInvocationResult] | None = None,
        raises: Exception | None = None,
        provider_identity: str = "deterministic-test-adapter/1.0.0",
    ) -> None:
        self._result = result
        self._results_by_purpose = dict(results_by_purpose or {})
        self._raises = raises
        self._provider_identity = provider_identity
        self.calls: list[dict] = []

    @property
    def provider_identity(self) -> str:
        return self._provider_identity

    def invoke(
        self, *, context: BoundedMendelContext, purpose: InvocationPurpose, focus_text: str | None
    ) -> MendelInvocationResult:
        self.calls.append({"context": context, "purpose": purpose, "focus_text": focus_text})
        if self._raises is not None:
            raise self._raises
        if purpose in self._results_by_purpose:
            return self._results_by_purpose[purpose]
        if self._result is not None:
            return self._result
        return MendelInvocationResult(proposals=(), reasoning_summary="no proposals configured")
