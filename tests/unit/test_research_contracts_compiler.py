"""PID-006A CanonicalStrategyCompiler / ExecutableStrategyPlan tests
(docs/pids/PID-006-APOLLO.md sec2/sec3/sec4/sec5).
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from darwin.research_contracts.compiler import CanonicalStrategyCompiler
from darwin.research_contracts.errors import (
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
)
from darwin.specification.applicability import (
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    IntrabarAmbiguityPolicy,
)
from darwin.specification.composition import (
    ContextTriggerComposition,
    ExpiryMode,
    ExpirySpec,
    SequenceComponent,
    SequenceComposition,
    SequenceTieSemantics,
)
from darwin.specification.domain import SEMANTIC_FIELD_NAMES, StrategyVersion
from darwin.specification.fingerprint import canonical_hash
from darwin.specification.parameters import (
    IntegerRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.policy import (
    PolicyClass,
    PolicyCompatibility,
    PolicyCompatibilityDeclaration,
)
from darwin.specification.validation import finalise
from tests.fixtures.specification_drafts import (
    minimal_valid_draft,
    new_york_session,
    simple_atomic_condition,
)


def _finalised(*, strategy_version_id: str = "sv-base", **draft_kwargs) -> StrategyVersion:
    draft = minimal_valid_draft(**draft_kwargs)
    result = finalise(draft, strategy_version_id=strategy_version_id, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert result.strategy_version is not None, result.outcome
    return result.strategy_version


def _recomputed(version: StrategyVersion) -> StrategyVersion:
    """Rebuild `semantic_fingerprint` from `version`'s own current field
    values -- used to construct deliberately-mutated fixtures directly
    (bypassing `finalise`/`validate_draft`, which the compiler itself
    never re-runs -- it trusts an already-finalised StrategyVersion, per
    PID-006A sec2)."""
    payload = {name: getattr(version, name) for name in SEMANTIC_FIELD_NAMES}
    return dataclasses.replace(version, semantic_fingerprint=canonical_hash(payload))


def test_same_strategy_version_compiles_to_identical_fingerprint_across_runs() -> None:
    version = _finalised()
    compiler = CanonicalStrategyCompiler()
    plan_a = compiler.compile(version)
    plan_b = compiler.compile(version)
    assert plan_a.fingerprint == plan_b.fingerprint
    assert plan_a.semantic_payload == plan_b.semantic_payload
    assert plan_a.plan_id != plan_b.plan_id  # opaque identity, never bound into fingerprint


def test_non_semantic_metadata_changes_never_change_plan_fingerprint() -> None:
    version_a = _finalised(strategy_version_id="sv-a", draft_id="draft-a", candidate_id="candidate-a")
    version_b = _finalised(strategy_version_id="sv-b", draft_id="draft-b", candidate_id="candidate-b")
    assert version_a.semantic_fingerprint == version_b.semantic_fingerprint  # sanity: specification's own guarantee

    compiler = CanonicalStrategyCompiler()
    plan_a = compiler.compile(version_a)
    plan_b = compiler.compile(version_b)
    assert plan_a.fingerprint == plan_b.fingerprint
    assert plan_a.source_strategy_version_id != plan_b.source_strategy_version_id


@pytest.mark.parametrize(
    "field_name,mutate",
    [
        ("schema_semantic_version", lambda v: dataclasses.replace(v, schema_semantic_version="9.9.9")),
        (
            "instrument_applicability",
            lambda v: dataclasses.replace(
                v,
                instrument_applicability=InstrumentApplicability(
                    kind=InstrumentApplicabilityKind.EXPLICIT_SET, instrument_ids=("XAU_USD", "EUR_USD")
                ),
            ),
        ),
        ("composition", lambda v: dataclasses.replace(v, composition=simple_atomic_condition(threshold="5000"))),
        (
            "fixed_parameters",
            lambda v: dataclasses.replace(
                v,
                fixed_parameters=(
                    ParameterDefinition(
                        parameter_id="lookback",
                        status=ParameterStatus.FIXED,
                        value_type=ParameterValueType.INTEGER,
                        fixed_value=20,
                    ),
                ),
            ),
        ),
        (
            "tunable_parameters",
            lambda v: dataclasses.replace(
                v,
                tunable_parameters=(
                    ParameterDefinition(
                        parameter_id="ema_period",
                        status=ParameterStatus.TUNABLE,
                        value_type=ParameterValueType.INTEGER,
                        domain=IntegerRangeDomain(minimum=5, maximum=50),
                    ),
                ),
            ),
        ),
        (
            "policy_declarations",
            lambda v: dataclasses.replace(
                v,
                policy_declarations=(
                    PolicyCompatibilityDeclaration(
                        policy_class=PolicyClass.DIKE_POLICY, compatibility=PolicyCompatibility.PERMITTED
                    ),
                ),
            ),
        ),
        (
            "data_requirements",
            lambda v: dataclasses.replace(
                v, data_requirements=tuple(dataclasses.replace(r, mandatory=False) for r in v.data_requirements)
            ),
        ),
        ("session_spec", lambda v: dataclasses.replace(v, session_spec=new_york_session())),
        (
            "intrabar_ambiguity_policy",
            lambda v: dataclasses.replace(
                v, intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST
            ),
        ),
        (
            "setup_expiry",
            lambda v: dataclasses.replace(v, setup_expiry=ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=3600)),
        ),
        (
            "exit_rules",
            lambda v: dataclasses.replace(v, exit_rules=(simple_atomic_condition(condition_id="exit_1"),)),
        ),
    ],
)
def test_every_semantic_field_mutation_changes_plan_fingerprint(field_name, mutate) -> None:
    """PID-006A sec4 coverage invariant, SUPPORTED half: a material mutation
    of `field_name` changes the compiled plan's fingerprint -- proving it
    is genuinely represented in the payload, never silently dropped."""
    base = _finalised()
    mutated = _recomputed(mutate(base))
    assert mutated.semantic_fingerprint != base.semantic_fingerprint  # the mutation really is material

    compiler = CanonicalStrategyCompiler()
    base_plan = compiler.compile(base)
    mutated_plan = compiler.compile(mutated)
    assert base_plan.fingerprint != mutated_plan.fingerprint
    assert base_plan.semantic_payload[field_name] != mutated_plan.semantic_payload[field_name]


def test_semantic_field_names_coverage_is_exhaustive() -> None:
    """No SEMANTIC_FIELD_NAMES entry is silently missing from the coverage
    proof above -- if a future specification change adds a new semantic
    field, this test fails until PID-006A's own coverage table (and, if
    necessary, the compiler itself) is updated for it."""
    covered = {
        "schema_semantic_version",
        "instrument_applicability",
        "composition",
        "fixed_parameters",
        "tunable_parameters",
        "policy_declarations",
        "data_requirements",
        "session_spec",
        "intrabar_ambiguity_policy",
        "setup_expiry",
        "exit_rules",
    }
    assert covered == set(SEMANTIC_FIELD_NAMES)


@pytest.mark.parametrize(
    "build_composition",
    [
        lambda: SequenceComposition(
            composition_id="seq-1",
            components=(
                SequenceComponent(sequence_index=0, component=simple_atomic_condition("leg_0")),
                SequenceComponent(sequence_index=1, component=simple_atomic_condition("leg_1", threshold="4100")),
            ),
            ordering_window_seconds=3600,
            tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
        ),
        lambda: ContextTriggerComposition(
            composition_id="ctx-1",
            context=simple_atomic_condition("context_leg", semantic_role="CONTEXT"),
            trigger=simple_atomic_condition("trigger_leg", semantic_role="TRIGGER", threshold="4100"),
            context_validity=ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=7200),
        ),
    ],
    ids=["SEQUENCE", "CONTEXT_TRIGGER"],
)
def test_sequence_and_context_trigger_composition_are_capability_blocked(build_composition) -> None:
    """PID-006A sec2/sec13 deliberate v1 judgment call: SEQUENCE/
    CONTEXT_TRIGGER composition roots fail closed with
    ENGINE_CAPABILITY_BLOCKED rather than being silently carried over as
    inert data with no corresponding temporal-evaluation contract."""
    base = _finalised()
    mutated = _recomputed(dataclasses.replace(base, composition=build_composition()))

    compiler = CanonicalStrategyCompiler()
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        compiler.compile(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_COMPOSITION_PRIMITIVE


def test_capability_blocked_is_not_invalid_configuration() -> None:
    """PID-006A sec13: a capability-blocked StrategyVersion is not
    invalid -- `EngineCapabilityBlockedError` must never be raised, and
    never be catchable as, an `InvalidConfigurationError`."""
    from darwin.research_contracts.errors import InvalidConfigurationError

    assert not issubclass(EngineCapabilityBlockedError, InvalidConfigurationError)
    assert not issubclass(InvalidConfigurationError, EngineCapabilityBlockedError)


def test_no_binary_float_in_plan_payload() -> None:
    """PID-006A sec5: no Python binary float may enter any semantic-
    identity path -- Decimal values in the compiled composition tree are
    canonicalised to their exact text representation, never a float."""
    version = _finalised()
    plan = CanonicalStrategyCompiler().compile(version)

    def _walk(node: object) -> None:
        assert not isinstance(node, float)
        if isinstance(node, dict):
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(plan.semantic_payload)


def test_plan_is_not_a_backtest() -> None:
    """PID-006A sec3: no mutable market state, no order/position/P&L
    object appears anywhere on ExecutableStrategyPlan."""
    from darwin.research_contracts.compiler import ExecutableStrategyPlan

    forbidden_substrings = ("order", "position", "fill", "pnl", "ledger", "equity")
    for f in dataclasses.fields(ExecutableStrategyPlan):
        lowered = f.name.lower()
        assert not any(token in lowered for token in forbidden_substrings), f.name
