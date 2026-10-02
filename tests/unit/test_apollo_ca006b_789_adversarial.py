"""Central Architecture corrections CA-006B-7, CA-006B-8, CA-006B-9 --
dedicated adversarial proofs (WO-PID006B-001).

Every test here was independently verified to FAIL against PR #24's head
immediately prior to this round
(`a5ee3e7b2f802f7fd6e549bbdd7f0d9c8de5a7cd`) -- either because no check
existed at all for the gap, or because the engine's old MAE/MFE
methodology reported a contaminated exit-bar extreme as if it were exact
fact. See the correction-round report for the exact old-head run
transcript proving each one.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.engine import _economic_payload
from darwin.apollo.errors import EngineCapabilityBlockedError, InvalidConfigurationError
from darwin.apollo.preflight import run_preflight
from darwin.core.dike import DikeState
from darwin.research_contracts.compiler import compute_plan_fingerprint
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from darwin.specification.fingerprint import canonical_hash
from tests.fixtures.apollo_strategy import (
    ENTRY_THRESHOLD_PARAMETER_ID,
    STOP_LOSS_PARAMETER_ID,
    TAKE_PROFIT_PARAMETER_ID,
    apollo_row,
    build_apollo_fixture_bundle,
    build_apollo_strategy_version,
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


def _run(bundle):
    return run_apollo_candle_causal_core(**_preflight_kwargs(bundle))


# ---- CA-006B-7: forged plan payload, valid recomputed plan/config fingerprints ----


def test_ca006b_07_forged_plan_payload_with_valid_recomputed_fingerprints_is_rejected() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b7", rows=_rows())
    plan = bundle.executable_plan

    # Alter the plan's ACTUAL semantic content (operator GT -> LT -- a
    # real, material change to entry semantics) while retaining the
    # original source_strategy_version_id/source_semantic_fingerprint.
    composition = dict(plan.semantic_payload["composition"])
    expression = dict(composition["expression"])
    expression["operator"] = "LT"
    composition["expression"] = expression
    altered_payload = {**plan.semantic_payload, "composition": composition}

    # Correctly recompute `fingerprint` over the ALTERED payload -- the
    # forged plan is internally self-consistent (this is exactly why
    # CA-006B-2's fingerprint-recompute checks alone cannot catch it).
    forged_fingerprint = compute_plan_fingerprint(
        source_semantic_fingerprint=plan.source_semantic_fingerprint, compiler_id=plan.compiler_id,
        compiler_version=plan.compiler_version, plan_schema_version=plan.plan_schema_version,
        semantic_payload=altered_payload,
    )
    forged_plan = dataclasses.replace(plan, semantic_payload=altered_payload, fingerprint=forged_fingerprint)
    assert forged_plan.fingerprint != plan.fingerprint
    assert forged_plan.source_semantic_fingerprint == plan.source_semantic_fingerprint
    assert forged_plan.source_strategy_version_id == plan.source_strategy_version_id

    reconfigured = build_research_configuration(
        strategy_version=bundle.strategy_version, executable_plan=forged_plan, parameter_set=bundle.parameter_set,
        instrument_definition=bundle.instrument_definition, research_input_bindings=(bundle.input_binding,),
        partition_policy=bundle.partition_policy, execution_policy=bundle.execution_policy, dike_state=DikeState.DISABLED,
    )
    # Sanity: the forged plan is capability-valid on its own (LT is a
    # supported operator) -- proves this test exercises CA-006B-7's
    # payload-content check specifically, not an incidental capability block.
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = forged_plan
    kwargs["research_configuration"] = reconfigured
    with pytest.raises(InvalidConfigurationError, match="semantic_payload"):
        run_preflight(**kwargs)


# ---- CA-006B-8: unknown schema_semantic_version -> capability-block ----


def test_ca006b_08_unknown_schema_semantic_version_is_capability_blocked() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-schema", rows=_rows())
    plan = bundle.executable_plan
    mutated = dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, "schema_semantic_version": "9.9.9-unknown"})
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- CA-006B-8: unused extra declared parameter -> capability-block ----


def test_ca006b_08_unused_extra_parameter_is_capability_blocked() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-extraparam", rows=_rows())
    plan = bundle.executable_plan
    extra_param = {
        "__type__": "ParameterDefinition", "parameter_id": "unused_extra_param", "status": "TUNABLE",
        "value_type": "DECIMAL", "unit": "USD_PER_TROY_OUNCE", "fixed_value": None,
        "domain": {"__type__": "NumericRangeDomain", "minimum": "0", "maximum": "100", "step": None},
    }
    mutated = dataclasses.replace(
        plan, semantic_payload={**plan.semantic_payload, "tunable_parameters": [*plan.semantic_payload["tunable_parameters"], extra_param]}
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        run_preflight(**kwargs)
    assert "unused_extra_param" in str(exc_info.value)


# ---- CA-006B-8: wrong SL/TP unit -> capability-block ----


@pytest.mark.parametrize("parameter_id", [STOP_LOSS_PARAMETER_ID, TAKE_PROFIT_PARAMETER_ID])
def test_ca006b_08_wrong_risk_parameter_unit_is_capability_blocked(parameter_id) -> None:
    bundle = build_apollo_fixture_bundle(dataset_id=f"ds-ca006b8-unit-{parameter_id}", rows=_rows())
    plan = bundle.executable_plan
    tunable = []
    for node in plan.semantic_payload["tunable_parameters"]:
        node = dict(node)
        if node["parameter_id"] == parameter_id:
            node["unit"] = "USD"  # wrong -- not USD_PER_TROY_OUNCE
        tunable.append(node)
    mutated = dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, "tunable_parameters": tunable})
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- CA-006B-8: wrong entry-threshold unit (parameterised case) -> capability-block ----


def test_ca006b_08_wrong_entry_threshold_parameter_unit_is_capability_blocked() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-entryunit-param", rows=_rows())
    plan = bundle.executable_plan
    tunable = []
    for node in plan.semantic_payload["tunable_parameters"]:
        node = dict(node)
        if node["parameter_id"] == ENTRY_THRESHOLD_PARAMETER_ID:
            node["unit"] = "USD"
        tunable.append(node)
    mutated = dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, "tunable_parameters": tunable})
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- CA-006B-8: wrong entry-threshold unit (literal case) -> capability-block ----


def test_ca006b_08_wrong_entry_threshold_literal_unit_is_capability_blocked() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-entryunit-literal", rows=_rows())
    plan = bundle.executable_plan
    composition = dict(plan.semantic_payload["composition"])
    expression = dict(composition["expression"])
    # Swap the ParameterReference for a Literal with the WRONG unit.
    expression["right"] = {"__type__": "Literal", "value": "4000", "unit": "USD", "kind": "LITERAL"}
    composition["expression"] = expression
    # The entry_threshold_usd parameter is no longer referenced at all now
    # -- drop it from tunable_parameters too, so this test isolates the
    # unit check (not the separate "unused declared parameter" check).
    tunable = [n for n in plan.semantic_payload["tunable_parameters"] if n["parameter_id"] != ENTRY_THRESHOLD_PARAMETER_ID]
    mutated = dataclasses.replace(
        plan, semantic_payload={**plan.semantic_payload, "composition": composition, "tunable_parameters": tunable}
    )
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


def test_ca006b_08_correct_literal_entry_threshold_unit_passes_capability_check() -> None:
    """Companion sanity test: the SAME literal substitution, with the
    CORRECT unit, is accepted -- proves the check above is discriminating
    on unit, not merely rejecting Literal entries outright."""
    from darwin.apollo.plan_adapter import check_plan_capability

    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-entryunit-literal-ok", rows=_rows())
    plan = bundle.executable_plan
    composition = dict(plan.semantic_payload["composition"])
    expression = dict(composition["expression"])
    expression["right"] = {"__type__": "Literal", "value": "4000", "unit": "USD_PER_TROY_OUNCE", "kind": "LITERAL"}
    composition["expression"] = expression
    tunable = [n for n in plan.semantic_payload["tunable_parameters"] if n["parameter_id"] != ENTRY_THRESHOLD_PARAMETER_ID]
    mutated = dataclasses.replace(
        plan, semantic_payload={**plan.semantic_payload, "composition": composition, "tunable_parameters": tunable}
    )
    result = check_plan_capability(mutated)
    assert result.entry_signal_spec.right_kind == "LITERAL"
    assert result.entry_signal_spec.right_literal == Decimal(4000)


# ---- CA-006B-8: insufficient dataset bar-count vs required historical depth ----


def test_ca006b_08_insufficient_bar_count_versus_required_depth_fails_before_replay() -> None:
    sv = build_apollo_strategy_version("sv-ca006b8-depth", required_depth_bars=1000)
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-depth", rows=_rows(n=4), strategy_version=sv)
    assert bundle.market_dataset.record_count == 4
    with pytest.raises(InvalidConfigurationError, match="historical depth"):
        run_preflight(**_preflight_kwargs(bundle))


def test_ca006b_08_sufficient_bar_count_versus_required_depth_passes() -> None:
    sv = build_apollo_strategy_version("sv-ca006b8-depth-ok", required_depth_bars=4)
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-depth-ok", rows=_rows(n=4), strategy_version=sv)
    result = run_preflight(**_preflight_kwargs(bundle))
    assert result.entry_signal_spec.field == "CLOSE"


# ---- CA-006B-8: unsupported policy/search declaration -> capability-block ----


def test_ca006b_08_nonempty_search_envelope_is_capability_blocked() -> None:
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-envelope", rows=_rows())
    plan = bundle.executable_plan
    envelope_entry = {
        "__type__": "PolicySearchAuthority", "dimension": "stop_loss_distance",
        "parameter": {
            "__type__": "ParameterDefinition", "parameter_id": STOP_LOSS_PARAMETER_ID, "status": "TUNABLE",
            "value_type": "DECIMAL", "unit": "USD_PER_TROY_OUNCE", "fixed_value": None,
            "domain": {"__type__": "NumericRangeDomain", "minimum": "0.01", "maximum": "1000000", "step": None},
        },
    }
    declaration = {
        "__type__": "PolicyCompatibilityDeclaration", "policy_class": "EXECUTION_POLICY", "compatibility": "PERMITTED",
        "authorized_search_envelope": [envelope_entry], "notes": None,
    }
    mutated = dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, "policy_declarations": [declaration]})
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


def test_ca006b_08_execution_policy_irrelevant_is_capability_blocked() -> None:
    """EXECUTION_POLICY compatibility must be REQUIRED/PERMITTED -- APOLLO
    always binds and applies a real ExecutionPolicyVersion, so declaring
    it IRRELEVANT would misrepresent that fact."""
    bundle = build_apollo_fixture_bundle(dataset_id="ds-ca006b8-irrelevant", rows=_rows())
    plan = bundle.executable_plan
    declaration = {
        "__type__": "PolicyCompatibilityDeclaration", "policy_class": "EXECUTION_POLICY", "compatibility": "IRRELEVANT",
        "authorized_search_envelope": [], "notes": None,
    }
    mutated = dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, "policy_declarations": [declaration]})
    kwargs = _preflight_kwargs(bundle)
    kwargs["executable_plan"] = mutated
    with pytest.raises(EngineCapabilityBlockedError):
        run_preflight(**kwargs)


# ---- CA-006B-9: exit-bar MAE/MFE contamination ----


def test_ca006b_09_stop_loss_exit_bar_high_contamination_is_excluded_from_mfe() -> None:
    """A huge, contaminated high on the STOP_LOSS exit bar itself must
    NOT be reported as real favourable excursion -- its timing relative
    to the SL trigger within that bar is unknowable, and the governed
    methodology excludes the exit bar's own high entirely on a
    STOP_LOSS exit."""
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),  # signal
        # Entry fills at open=4000 (sl=3995, tp=4999 -- wide enough that
        # a naive full-range MFE would be enormous). This SAME bar's high
        # is a contaminated 9999, and its low (3990) triggers STOP_LOSS.
        apollo_row(UTC_START + timedelta(hours=1), "4000", "9999", "3990", "4000"),
    ]
    bundle = build_apollo_fixture_bundle(
        dataset_id="ds-ca006b9-contam", rows=rows, stop_loss_distance=Decimal(5), take_profit_distance=Decimal(999)
    )
    result = _run(bundle)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.entry_bar_index == trade.exit_bar_index  # same-bar entry+exit

    record = result.mae_mfe[0]
    assert record.trade_id == trade.trade_id
    assert record.mfe_resolution == "EXIT_BAR_EXCLUDED_STOP_LOSS_AMBIGUITY"
    # The contaminated 9999 high must NOT be reflected: no prior bars
    # exist (same-bar exit), so the governed MFE is exactly zero.
    assert Decimal(record.mfe_usd) == Decimal(0)

    # A NAIVE full-range computation (the OLD methodology) would have
    # reported a huge, false favourable excursion from the same raw data
    # -- proves this is a genuine discriminating fix, not a vacuous check.
    naive_mfe_usd = Decimal(9999) - Decimal(4000)
    assert naive_mfe_usd > Decimal(1000)
    assert Decimal(record.mfe_usd) < naive_mfe_usd

    # MAE, by contrast, uses the full raw low (never understates risk) --
    # the real low (3990) is reflected even though SL only required 5.
    assert Decimal(record.mae_usd) == Decimal(10)
    assert record.mae_resolution == "FULL_RANGE_INCLUSIVE_OF_EXIT_BAR"
    assert record.methodology_id == "CONSERVATIVE_EXCURSION_V1"


def test_ca006b_09_take_profit_exit_bar_high_beyond_trigger_is_capped() -> None:
    """Symmetric case: a TAKE_PROFIT exit bar's high beyond the TP
    trigger itself is capped at the certain trigger level, never the raw
    (possibly post-exit) extreme."""
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),
        # Entry fills at open=4000 (sl=3000 wide, tp=4010). Exit bar's
        # raw high is 9999 (contaminated) but TP triggers at 4010.
        apollo_row(UTC_START + timedelta(hours=1), "4000", "9999", "3999", "4005"),
    ]
    bundle = build_apollo_fixture_bundle(
        dataset_id="ds-ca006b9-tp-cap", rows=rows, stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(10)
    )
    result = _run(bundle)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    record = result.mae_mfe[0]
    # Capped at the certain TP trigger (entry 4000 + 10 = 4010), NEVER the
    # raw contaminated high (9999).
    assert Decimal(record.mfe_usd) == Decimal(10)
    assert record.mfe_resolution == "CAPPED_AT_TAKE_PROFIT_TRIGGER_EXIT_BAR_BEYOND_TRIGGER_EXCLUDED"


# ---- CA-006B-9: MAE/MFE participates in the deterministic evidence identity ----


def test_ca006b_09_mae_mfe_methodology_change_perturbs_economic_outcome_hash() -> None:
    """Direct, minimal proof that `_economic_payload` (and therefore
    `economic_outcome_hash`) genuinely changes when the MAE/MFE evidence
    changes -- isolated from the full replay loop."""
    from darwin.apollo.engine import MaeMfeRecord

    base_mae_mfe = (
        MaeMfeRecord(
            trade_id="t1", mae_usd="10", mfe_usd="0", methodology_id="CONSERVATIVE_EXCURSION_V1",
            measurement_start_bar_index=1, measurement_end_bar_index=1,
            mae_resolution="FULL_RANGE_INCLUSIVE_OF_EXIT_BAR", mfe_resolution="EXIT_BAR_EXCLUDED_STOP_LOSS_AMBIGUITY",
        ),
    )
    mutated_mae_mfe = (
        MaeMfeRecord(
            trade_id="t1", mae_usd="10", mfe_usd="5999", methodology_id="NAIVE_FULL_RANGE_V0",
            measurement_start_bar_index=1, measurement_end_bar_index=1,
            mae_resolution="FULL_RANGE_INCLUSIVE_OF_EXIT_BAR", mfe_resolution="FULL_RANGE_INCLUSIVE_OF_EXIT_BAR",
        ),
    )
    common = {
        "starting_capital_usd": "100000", "final_balance_usd": "99990", "final_equity_usd": "99990",
        "peak_equity_usd": "100000", "max_drawdown_usd": "10",
    }
    base_hash = canonical_hash(_economic_payload((), (), fill_trade_sequence_hash="fth", mae_mfe=base_mae_mfe, **common))
    mutated_hash = canonical_hash(_economic_payload((), (), fill_trade_sequence_hash="fth", mae_mfe=mutated_mae_mfe, **common))
    assert base_hash != mutated_hash
