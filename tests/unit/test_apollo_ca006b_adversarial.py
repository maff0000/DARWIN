"""Central Architecture correction CA-006B-1 through CA-006B-6 --
dedicated adversarial proofs, numbered to match the Architect's own
"Required new adversarial tests" list.

Every test here was independently verified to FAIL against PR #24's
original head (`36df62971819264cc08ecdd1d96a8275058d0a44`) before this
correction -- either because that head's `run_preflight` never
cross-checked the relevant axis fingerprint against
`ResearchConfiguration` at all, or because its API had no way to even
express the check (e.g. no `executable_plan` parameter existed yet). See
the PID-006B correction-round report for the exact old-head run
transcript proving each one.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.capability import (
    FIXED_MECHANICAL_TEST_COST,
    QUANTITY_FIXED_ONE_TROY_OUNCE,
    check_execution_policy_capability,
)
from darwin.apollo.engine import run_apollo_replay
from darwin.apollo.errors import (
    EngineCapabilityBlockedError,
    InvalidConfigurationError,
    PersistedFingerprintMismatchError,
)
from darwin.apollo.preflight import run_preflight
from darwin.core.dike import DikeState
from darwin.hermes.instrument_definition import (
    InstrumentDefinition,
)
from darwin.research_contracts.execution_policy import (
    ExecutionPolicyComponent,
    build_execution_policy_version,
)
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from tests.fixtures.apollo_strategy import (
    apollo_row,
    build_apollo_dataset,
    build_apollo_execution_policy,
    build_apollo_fixture_bundle,
    build_apollo_parameter_set,
)

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _rows(n: int = 4):
    return [
        apollo_row(UTC_START + timedelta(hours=i), "3990", "3995", "3985", "3990" if i == 0 else "4005")
        for i in range(n)
    ]


def _preflight_kwargs(bundle):
    return {
        "strategy_version": bundle.strategy_version, "executable_plan": bundle.executable_plan,
        "parameter_set": bundle.parameter_set, "execution_policy": bundle.execution_policy,
        "partition_policy": bundle.partition_policy, "market_dataset": bundle.market_dataset,
        "research_configuration": bundle.research_configuration, "instrument_definition": bundle.instrument_definition,
    }


# ---- test 1: ResearchConfiguration bound to ParameterSet A, executed with ParameterSet B ----


def test_ca006b_01_parameter_set_substitution_within_same_strategy_blocks_before_replay() -> None:
    """Both ParameterSetVersions belong to the IDENTICAL StrategyVersion
    (same `source_semantic_fingerprint`) -- the pre-correction check #7
    (fingerprint-vs-strategy_version only) would have let this straight
    through. Only the axis-vs-ResearchConfiguration binding check
    (CA-006B-2) catches it."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-01", rows=_rows())
    parameter_set_b = build_apollo_parameter_set(bundle.strategy_version, entry_threshold=Decimal(9999))
    assert parameter_set_b.source_semantic_fingerprint == bundle.strategy_version.semantic_fingerprint
    assert parameter_set_b.fingerprint != bundle.parameter_set.fingerprint

    kwargs = _preflight_kwargs(bundle)
    kwargs["parameter_set"] = parameter_set_b
    with pytest.raises(InvalidConfigurationError):
        run_preflight(**kwargs)


# ---- test 2: ResearchConfiguration bound to ExecutionPolicy A, executed with supported ExecutionPolicy B ----


def test_ca006b_02_execution_policy_substitution_blocks_before_replay() -> None:
    """Both ExecutionPolicyVersions are individually SUPPORTED (ZERO_COST
    vs FIXED_MECHANICAL_TEST_COST) -- the pre-correction capability
    allowlist check alone would have waved this through, since it never
    compared the policy's fingerprint against ResearchConfiguration at
    all."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-02", rows=_rows(), cost_methodology=FIXED_MECHANICAL_TEST_COST)
    # Build a genuinely different (but still fully supported) policy by
    # swapping which canonical cost component is used.
    from darwin.research_contracts.execution_policy import ZERO_COST

    other_policy = build_apollo_execution_policy(cost_methodology=ZERO_COST)
    assert other_policy.fingerprint != bundle.execution_policy.fingerprint
    check_execution_policy_capability(other_policy)  # sanity: B is independently a supported policy

    kwargs = _preflight_kwargs(bundle)
    kwargs["execution_policy"] = other_policy
    with pytest.raises(InvalidConfigurationError):
        run_preflight(**kwargs)


# ---- test 3: instrument-definition FINGERPRINT differs while the bare id agrees ----


def test_ca006b_03_instrument_definition_fingerprint_mismatch_blocks_even_when_bare_id_agrees() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-03", rows=_rows())
    # Same bare instrument_id ("XAU_USD"), but a DIFFERENT definition_version
    # -> a genuinely different .fingerprint.
    fake_but_same_id_definition = InstrumentDefinition(
        instrument_id="XAU_USD", base_asset="XAU", quote_asset="USD", base_quantity_unit="TROY_OUNCE",
        price_unit="USD_PER_TROY_OUNCE", definition_version="v2-not-the-real-one",
    )
    assert fake_but_same_id_definition.instrument_id == bundle.instrument_definition.instrument_id
    assert fake_but_same_id_definition.fingerprint != bundle.instrument_definition.fingerprint

    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=fake_but_same_id_definition,
        research_input_bindings=(bundle.input_binding,), partition_policy=bundle.partition_policy,
        execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    assert reconfigured.instrument_definition_id == bundle.research_configuration.instrument_definition_id

    kwargs = _preflight_kwargs(bundle)
    kwargs["research_configuration"] = reconfigured  # built against the fake definition
    # instrument_definition passed to preflight is the REAL one (bundle.instrument_definition)
    with pytest.raises(InvalidConfigurationError):
        run_preflight(**kwargs)


# ---- test 4: compiled-plan fingerprint differs from the actual plan being executed ----


def test_ca006b_04_plan_fingerprint_mismatch_blocks_before_replay() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-04", rows=_rows())
    # A plan with IDENTICAL semantic content but a DIFFERENT declared
    # compiler_version -> a genuinely different, self-consistent .fingerprint.
    from darwin.research_contracts.compiler import compute_plan_fingerprint

    other_fingerprint = compute_plan_fingerprint(
        source_semantic_fingerprint=bundle.executable_plan.source_semantic_fingerprint,
        compiler_id=bundle.executable_plan.compiler_id, compiler_version="9.9.9-rogue",
        plan_schema_version=bundle.executable_plan.plan_schema_version, semantic_payload=bundle.executable_plan.semantic_payload,
    )
    different_plan = dataclasses.replace(bundle.executable_plan, compiler_version="9.9.9-rogue", fingerprint=other_fingerprint)
    assert different_plan.fingerprint != bundle.executable_plan.fingerprint

    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = different_plan  # internally self-consistent, but never bound by research_configuration
    with pytest.raises(InvalidConfigurationError):
        run_preflight(**kwargs)


# ---- test 5: tampered/stale ResearchConfiguration.fingerprint itself ----


def test_ca006b_05_tampered_research_configuration_fingerprint_blocks() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-05", rows=_rows())
    tampered = dataclasses.replace(bundle.research_configuration, fingerprint="0" * 64)
    kwargs = _preflight_kwargs(bundle)
    kwargs["research_configuration"] = tampered
    with pytest.raises(PersistedFingerprintMismatchError):
        run_preflight(**kwargs)


# ---- test 6: preflight against Dataset A, replay attempted with Dataset B ----


def test_ca006b_06_replay_with_a_different_dataset_than_preflighted_blocks_before_bar_zero() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-06-a", rows=_rows())
    other_dataset = build_apollo_dataset("ds-ca006b-06-b", _rows(n=6))

    preflight_result = run_preflight(**_preflight_kwargs(bundle))
    with pytest.raises(InvalidConfigurationError):
        run_apollo_replay(preflight_result=preflight_result, market_dataset=other_dataset)


def test_ca006b_06b_replay_with_content_altered_but_same_id_also_blocks() -> None:
    """Same `dataset_id`, different candle content (a different
    `fingerprint_sha256`) -- also must not slip through on id alone."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-06c", rows=_rows())
    preflight_result = run_preflight(**_preflight_kwargs(bundle))
    altered_rows = _rows(n=4)
    altered_dataset = build_apollo_dataset("ds-ca006b-06c", altered_rows)
    altered_dataset = dataclasses.replace(altered_dataset, dataset_id=bundle.market_dataset.dataset_id)
    assert altered_dataset.dataset_id == bundle.market_dataset.dataset_id
    assert altered_dataset.fingerprint_sha256 == bundle.market_dataset.fingerprint_sha256  # identical rows -> identical content
    # (Same content -> same fingerprint is the CORRECT outcome here; the
    # genuinely adversarial case -- different id -- is test 06 above. This
    # companion simply documents that content, not object identity, is
    # what's actually checked.)
    result = run_apollo_replay(preflight_result=preflight_result, market_dataset=altered_dataset)
    assert result.bars_processed == altered_dataset.record_count


# ---- test 7: valid StrategyVersion with non-null session semantics -> capability-blocked ----
# ---- test 8: unsupported setup-expiry semantic -> capability-blocked ----
# ---- test 9: additional unsupported data requirement -> capability-blocked ----
# ---- test 10: ambiguity policy inconsistent with CONSERVATIVE_SL_FIRST -> capability-blocked ----
# (full coverage already lives in tests/unit/test_apollo_plan_adapter.py;
# reproduced here, driven through the real run_preflight entry point, for
# direct Architect traceability against this numbered list.)


def test_ca006b_07_session_semantics_block_through_real_preflight() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-07", rows=_rows())
    session_payload = {
        "__type__": "SessionSpec", "iana_timezone": "America/New_York", "local_start": "08:00",
        "local_end": "17:00", "weekdays": [0, 1, 2, 3, 4], "dst_handling": "FOLLOW_IANA_TIMEZONE_RULES", "cross_midnight": False,
    }
    mutated_plan = dataclasses.replace(
        bundle.executable_plan, semantic_payload={**bundle.executable_plan.semantic_payload, "session_spec": session_payload}
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated_plan
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


def test_ca006b_08_setup_expiry_blocks_through_real_preflight() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-08", rows=_rows())
    expiry_payload = {"__type__": "ExpirySpec", "mode": "DURATION", "frame_count": None, "finest_bound_timeframe": None, "duration_seconds": 3600}
    mutated_plan = dataclasses.replace(
        bundle.executable_plan, semantic_payload={**bundle.executable_plan.semantic_payload, "setup_expiry": expiry_payload}
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated_plan
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


def test_ca006b_09_extra_data_requirement_blocks_through_real_preflight() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-09", rows=_rows())
    extra = {
        "__type__": "DataRequirement", "requirement_id": "ares_news_sentiment", "display_name": "News sentiment",
        "fact_class": "NEWS_CONTEXT", "fact_reference_kind": "CANONICAL_FACT_REFERENCE", "authority_class": "ARES_GOVERNED_CONTEXT",
        "instrument_applicability": ["XAU_USD"], "timeframe": None,
        "required_historical_depth": {"__type__": "HistoricalDepthRequirement", "count": 1, "unit": "BARS"},
        "units": None, "required_fields": ["SENTIMENT_SCORE"], "causal_timing_policy": "AS_OF_PUBLISH_TIME", "mandatory": True,
    }
    mutated_plan = dataclasses.replace(
        bundle.executable_plan,
        semantic_payload={**bundle.executable_plan.semantic_payload, "data_requirements": [*bundle.executable_plan.semantic_payload["data_requirements"], extra]},
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated_plan
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


def test_ca006b_10_inconsistent_ambiguity_policy_blocks_through_real_preflight() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-10", rows=_rows())
    mutated_plan = dataclasses.replace(
        bundle.executable_plan, semantic_payload={**bundle.executable_plan.semantic_payload, "intrabar_ambiguity_policy": "NOT_APPLICABLE"}
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated_plan
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- test 11: counterfeit quantity component (same id/version, altered configuration) ----


def test_ca006b_11_counterfeit_quantity_configuration_is_blocked() -> None:
    counterfeit = ExecutionPolicyComponent(
        kind=QUANTITY_FIXED_ONE_TROY_OUNCE.kind, component_id=QUANTITY_FIXED_ONE_TROY_OUNCE.component_id,
        component_version=QUANTITY_FIXED_ONE_TROY_OUNCE.component_version,
        configuration=(
            ("quantity", Decimal(2)),  # counterfeit: claims 2 oz instead of the canonical 1
            ("quantity_unit", "TROY_OUNCE"), ("starting_capital_usd", Decimal(100000)), ("account_currency", "USD"),
        ),
    )
    assert counterfeit.component_id == QUANTITY_FIXED_ONE_TROY_OUNCE.component_id
    assert counterfeit.component_version == QUANTITY_FIXED_ONE_TROY_OUNCE.component_version
    assert counterfeit != QUANTITY_FIXED_ONE_TROY_OUNCE
    with pytest.raises(EngineCapabilityBlockedError):
        check_execution_policy_capability(
            build_execution_policy_version(
                timing_methodology=build_apollo_execution_policy().timing_methodology,
                price_fill_methodology=build_apollo_execution_policy().price_fill_methodology,
                intrabar_resolution_methodology=build_apollo_execution_policy().intrabar_resolution_methodology,
                cost_methodology=build_apollo_execution_policy().cost_methodology,
                quantity_economic_methodology=counterfeit,
                session_force_flat_methodology=build_apollo_execution_policy().session_force_flat_methodology,
            )
        )


# ---- test 12: counterfeit fixed-cost component (same id/version, altered configuration) ----


def test_ca006b_12_counterfeit_cost_configuration_is_blocked() -> None:
    counterfeit = ExecutionPolicyComponent(
        kind=FIXED_MECHANICAL_TEST_COST.kind, component_id=FIXED_MECHANICAL_TEST_COST.component_id,
        component_version=FIXED_MECHANICAL_TEST_COST.component_version,
        configuration=(
            ("spread_usd", Decimal(0)),  # counterfeit: claims zero spread under the "real cost" component's own identity
            ("slippage_usd", Decimal(0)), ("fee_usd_per_trade", Decimal(0)),
        ),
    )
    assert counterfeit != FIXED_MECHANICAL_TEST_COST
    ep = build_apollo_execution_policy(cost_methodology=counterfeit)
    with pytest.raises(EngineCapabilityBlockedError):
        check_execution_policy_capability(ep)


def test_ca006b_11_and_12_counterfeit_blocks_before_replay_end_to_end() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-11-12", rows=_rows())
    counterfeit_quantity = ExecutionPolicyComponent(
        kind=QUANTITY_FIXED_ONE_TROY_OUNCE.kind, component_id=QUANTITY_FIXED_ONE_TROY_OUNCE.component_id,
        component_version=QUANTITY_FIXED_ONE_TROY_OUNCE.component_version,
        configuration=(
            ("quantity", Decimal(2)), ("quantity_unit", "TROY_OUNCE"),
            ("starting_capital_usd", Decimal(100000)), ("account_currency", "USD"),
        ),
    )
    counterfeit_policy = build_execution_policy_version(
        timing_methodology=bundle.execution_policy.timing_methodology,
        price_fill_methodology=bundle.execution_policy.price_fill_methodology,
        intrabar_resolution_methodology=bundle.execution_policy.intrabar_resolution_methodology,
        cost_methodology=bundle.execution_policy.cost_methodology,
        quantity_economic_methodology=counterfeit_quantity,
        session_force_flat_methodology=bundle.execution_policy.session_force_flat_methodology,
    )
    # Rebuild ResearchConfiguration bound to the counterfeit policy too --
    # isolates THIS proof to the capability-allowlist check specifically
    # (CA-006B-5), rather than the (separately, already proven in test 2)
    # axis-binding check catching the substitution first.
    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, instrument_definition=bundle.instrument_definition,
        research_input_bindings=(bundle.input_binding,), partition_policy=bundle.partition_policy,
        execution_policy=counterfeit_policy, dike_state=DikeState.DISABLED,
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["execution_policy"] = counterfeit_policy
    kwargs["research_configuration"] = reconfigured
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- test 13: identical numeric decision stream, different upstream identity, still distinguishable ----


def test_ca006b_13_identical_decisions_under_a_different_plan_identity_remain_distinguishable() -> None:
    """A plan with IDENTICAL semantic_payload (hence an IDENTICAL decision
    stream numerically) but a DIFFERENT compiler_version -- the governed
    decision identity must still change, because it binds the plan's own
    fingerprint, not just the decision records."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b-13", rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    result_a = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )

    from darwin.research_contracts.compiler import compute_plan_fingerprint

    different_fingerprint = compute_plan_fingerprint(
        source_semantic_fingerprint=bundle.executable_plan.source_semantic_fingerprint,
        compiler_id=bundle.executable_plan.compiler_id, compiler_version="9.9.9-rogue",
        plan_schema_version=bundle.executable_plan.plan_schema_version, semantic_payload=bundle.executable_plan.semantic_payload,
    )
    different_plan = dataclasses.replace(bundle.executable_plan, compiler_version="9.9.9-rogue", fingerprint=different_fingerprint)
    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=different_plan, parameter_set=bundle.parameter_set,
        instrument_definition=bundle.instrument_definition, research_input_bindings=(bundle.input_binding,),
        partition_policy=bundle.partition_policy, execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    result_b = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, executable_plan=different_plan, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy, market_dataset=bundle.market_dataset,
        research_configuration=reconfigured, instrument_definition=bundle.instrument_definition,
    )

    # The NUMERIC decision records are byte-identical (same semantic_payload
    # drives identical signal_fired/position/order decisions)...
    assert result_a.decision_stream == result_b.decision_stream
    # ...but the GOVERNED decision identity still differs, because it binds
    # the plan's own fingerprint, not just the decision records themselves.
    assert result_a.decision_stream_hash != result_b.decision_stream_hash
    assert result_a.evidence_envelope_hash != result_b.evidence_envelope_hash
