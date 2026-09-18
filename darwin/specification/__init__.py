"""DARWIN Specification module -- PID-004A Specification Contract
(docs/pids/PID-004-SPECIFICATION-WORKSHOP.md).

In-memory domain contract only: schema/domain-model/validator/fixtures.
No persistence (no Postgres tables, no migrations), no API routes, no
ARENA UI, no MENDEL/Claude Code integration, no Workshop filesystem, no
ATHENA/APOLLO, no HELIOS modification. PID-004B (Strategy Workshop) is a
separately gated increment and has not begun.

- `darwin.specification.errors` -- the domain error hierarchy.
- `darwin.specification.timeframe` -- closed, instrument-generic timeframe
  codes.
- `darwin.specification.expressions` -- the typed declarative strategy
  expression model (no eval/exec, closed governed operator vocabulary).
- `darwin.specification.facts` -- CANONICAL_FACT_REFERENCE vs
  SPECIFICATION_DERIVED_FACT, kept as two genuinely distinct types.
- `darwin.specification.causal` -- causal external/context fact timing
  (event/published/observed/effective/revision) and the "no hindsight
  leakage" selection function.
- `darwin.specification.composition` -- ATOMIC/ALL/ANY/SEQUENCE/
  CONTEXT_TRIGGER as five distinct types, plus governed expiry and the
  (documentation-only) normalized HELIOS state vocabulary.
- `darwin.specification.parameters` -- FIXED/TUNABLE parameters with
  bounded domains.
- `darwin.specification.policy` -- ExecutionPolicy/DIKEPolicy/
  SizingPolicy/NewsContextPolicy compatibility declarations, kept
  separate from any frozen policy version identity.
- `darwin.specification.provenance` -- rule origin vs rule acceptance.
- `darwin.specification.data_requirements` -- first-class DataRequirement
  model.
- `darwin.specification.readiness` -- DataReadinessAssessment, kept
  structurally invisible to fingerprinting.
- `darwin.specification.applicability` -- instrument applicability,
  session/timezone/DST, intrabar-ambiguity policy.
- `darwin.specification.fingerprint` -- generic deterministic
  canonicalisation + SHA-256 hashing.
- `darwin.specification.domain` -- StrategyCandidate, SpecificationDraft
  (mutable), StrategyVersion (immutable).
- `darwin.specification.validation` -- the deterministic validation
  pipeline, `STRATEGY_NOT_SUFFICIENTLY_DEFINED` outcome, and `finalise`.
"""
