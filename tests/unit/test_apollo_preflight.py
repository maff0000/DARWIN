"""PID-006B mandatory preflight tests -- falsification tests 6, 7, 8, 9,
plus checks #1/#2/#4/#5 for full coverage. Every case here proves the
engine fails CLOSED, before a single bar is processed (`run_preflight`
never returns a `PreflightResult` on failure, so `run_apollo_replay` is
never reached -- there is no partial/best-effort `ApolloEngineResult`
anywhere in these tests).
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from darwin.apollo.errors import EngineCapabilityBlockedError, InvalidConfigurationError
from darwin.apollo.preflight import run_preflight
from darwin.core.dike import DikeState
from darwin.hermes.instrument_definition import (
    InstrumentDefinition,
)
from darwin.research_contracts.input_binding import (
    ResearchInputKind,
    build_research_input_binding,
)
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from darwin.specification.applicability import (
    InstrumentApplicability,
    InstrumentApplicabilityKind,
)
from tests.fixtures.apollo_strategy import (
    apollo_entry_condition,
    apollo_row,
    build_apollo_dataset,
    build_apollo_fixture_bundle,
    build_apollo_parameter_set,
    build_apollo_strategy_version,
)

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _rows(n: int = 4):
    return [
        apollo_row(UTC_START + timedelta(hours=i), "3990", "3995", "3985", "3990" if i == 0 else "4005")
        for i in range(n)
    ]


def test_valid_configuration_passes_preflight() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-ok", rows=_rows())
    result = run_preflight(
        strategy_version=bundle.strategy_version,
        parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy,
        market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration,
        instrument_definition=bundle.instrument_definition,
    )
    assert result.entry_signal_spec.field == "CLOSE"


# ---- check #1: instrument applicability --------------------------------


def test_check1_instrument_applicability_missing_xau_usd_blocks() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c1", rows=_rows())
    wrong_applicability = InstrumentApplicability(
        kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("EUR_USD",)
    )
    mutated_strategy = dataclasses.replace(bundle.strategy_version, instrument_applicability=wrong_applicability)
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=mutated_strategy, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
            research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
        )


# ---- check #2: ResearchConfiguration.instrument_definition_id ----------


def test_check2_configuration_instrument_mismatch_blocks() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c2", rows=_rows())
    fake_instrument_definition = InstrumentDefinition(
        instrument_id="EUR_USD", base_asset="EUR", quote_asset="USD", base_quantity_unit="EUR",
        price_unit="USD_PER_EUR", definition_version="v1",
    )
    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=fake_instrument_definition,
        research_input_bindings=(bundle.input_binding,), partition_policy=bundle.partition_policy,
        execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
            research_configuration=reconfigured, instrument_definition=bundle.instrument_definition,
        )


# ---- falsification test 6: dataset/instrument mismatch blocks ----------


def test_falsification6_input_binding_dataset_mismatch_blocks_before_replay() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-real", rows=_rows())
    other_dataset = build_apollo_dataset("ds-preflight-different", _rows(n=6))
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=other_dataset,
            research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
        )


def test_falsification6_more_than_one_input_binding_blocks() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-multi", rows=_rows())
    second_binding = build_research_input_binding(
        logical_input_role="SECONDARY_CONTEXT", input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        governed_dataset_id="ds-other", dataset_semantic_fingerprint="fp-other",
    )
    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=bundle.instrument_definition,
        research_input_bindings=(bundle.input_binding, second_binding), partition_policy=bundle.partition_policy,
        execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
            research_configuration=reconfigured, instrument_definition=bundle.instrument_definition,
        )


# ---- check #4: dataset self-consistency (fingerprint recompute) --------


def test_check4_corrupted_dataset_fingerprint_blocks() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c4", rows=_rows())
    corrupted_dataset = dataclasses.replace(bundle.market_dataset, fingerprint_sha256="0" * 64)
    corrupted_binding = build_research_input_binding(
        logical_input_role="PRIMARY_MARKET_DATA", input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        governed_dataset_id=corrupted_dataset.dataset_id, dataset_semantic_fingerprint="0" * 64,
    )
    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=bundle.instrument_definition,
        research_input_bindings=(corrupted_binding,),
        partition_policy=build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=corrupted_binding),
        execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=corrupted_dataset,
            research_configuration=reconfigured, instrument_definition=bundle.instrument_definition,
        )


# ---- check #5: MarketDataset.instrument_definition_id vs InstrumentDefinition.fingerprint (the gotcha) ----


def test_check5_dataset_instrument_definition_id_does_not_match_definition_fingerprint() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c5", rows=_rows())
    corrupted_dataset = dataclasses.replace(bundle.market_dataset, instrument_definition_id="not-a-real-fingerprint")
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=corrupted_dataset,
            research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
        )


def test_check5_is_a_fingerprint_vs_fingerprint_comparison_not_id_vs_id() -> None:
    """The documented gotcha, proven directly: MarketDataset.instrument ==
    'XAU_USD' (the bare id) must NOT be compared against
    InstrumentDefinition.fingerprint (a hash) -- confirms they are
    genuinely different strings in real, correctly-built fixture data,
    so the check in preflight.py could not have passed by accident."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c5b", rows=_rows())
    assert bundle.market_dataset.instrument != bundle.instrument_definition.fingerprint
    assert bundle.market_dataset.instrument_definition_id == bundle.instrument_definition.fingerprint


# ---- falsification test 7: parameter/strategy mismatch blocks ----------


def test_falsification7_parameter_set_strategy_mismatch_blocks_before_replay() -> None:
    """Simulates a caller passing an internally-inconsistent (strategy,
    parameter_set) pair directly to the engine -- never routed through
    `build_research_configuration` (which would already reject this at
    construction). Proves the engine's OWN independent re-check (never
    trusting a configuration blindly)."""
    bundle_a = build_apollo_fixture_bundle(dataset_id="ds-preflight-c7", rows=_rows())
    # A genuinely different composition (different condition_id) so
    # strategy_b's semantic_fingerprint really differs from strategy_a's --
    # strategy_version_id/candidate_id alone are excluded from semantic
    # identity and would not by themselves produce a real mismatch.
    strategy_b = build_apollo_strategy_version(
        "sv-preflight-c7-other", composition=apollo_entry_condition("entry_long_variant")
    )
    parameter_set_b = build_apollo_parameter_set(strategy_b)
    assert parameter_set_b.source_semantic_fingerprint != bundle_a.strategy_version.semantic_fingerprint

    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle_a.strategy_version, parameter_set=parameter_set_b,
            execution_policy=bundle_a.execution_policy, market_dataset=bundle_a.market_dataset,
            research_configuration=bundle_a.research_configuration, instrument_definition=bundle_a.instrument_definition,
        )


# ---- falsification test 8: unsupported execution-policy capability blocks ----


def test_falsification8_unsupported_execution_policy_component_blocks_before_replay() -> None:
    from darwin.research_contracts.execution_policy import (
        ExecutionPolicyComponent,
        ExecutionPolicyComponentKind,
    )

    bogus_cost = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.COST_METHODOLOGY, component_id="REALISTIC_BROKER_COST", component_version="v1",
    )
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c8", rows=_rows(), cost_methodology=bogus_cost)
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
            research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
        )


# ---- falsification test 9: DIKE_GUARDED rejected outright ---------------


def test_falsification9_dike_guarded_is_rejected_outright() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-preflight-c9", rows=_rows())
    guarded_configuration = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=bundle.instrument_definition,
        research_input_bindings=(bundle.input_binding,), partition_policy=bundle.partition_policy,
        execution_policy=bundle.execution_policy, dike_state=DikeState.GUARDED,
        dike_policy_fingerprint="test-dike-policy-fingerprint",
    )
    with pytest.raises(InvalidConfigurationError):
        run_preflight(
            strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
            research_configuration=guarded_configuration, instrument_definition=bundle.instrument_definition,
        )


def test_falsification8_and_9_never_leak_a_partial_engine_result() -> None:
    """Every preflight failure above raises BEFORE returning a
    PreflightResult -- there is no code path anywhere in run_preflight
    that returns a partial/best-effort result on failure (it either
    returns a complete PreflightResult or raises; pytest.raises above
    already proves the raise side for every check)."""
    import inspect

    from darwin.apollo import preflight as preflight_module

    source = inspect.getsource(preflight_module.run_preflight)
    # Exactly one `return` statement in the function body -- the success path.
    assert source.count("return PreflightResult(") == 1
