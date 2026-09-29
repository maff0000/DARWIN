"""Shared PID-006B APOLLO Candle Causal Core test fixtures.

Deliberately lives under tests/fixtures (mirrors tests/fixtures/
specification_drafts.py and tests/fixtures/hermes_rows.py) -- controlled
fixture data only, never presented as real discovered/proven strategy
evidence.

The fixture strategy is a single ATOMIC LONG entry: "XAU_USD H1 CLOSE >
entry_threshold_usd" (a TUNABLE Decimal parameter, not a hardcoded
Literal, so falsification test 12's "changing one parameter perturbs the
decision stream" can be exercised without rebuilding the whole
StrategyVersion). `stop_loss_distance_usd`/`take_profit_distance_usd` are
the two mandatory SL/TP risk parameters `darwin.apollo.economics`
requires.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from darwin.apollo.capability import (
    INTRABAR_CONSERVATIVE_SL_FIRST,
    PRICE_FILL_NEXT_BAR_OPEN,
    QUANTITY_FIXED_ONE_TROY_OUNCE,
    SESSION_NO_FORCE_FLAT,
    TIMING_CLOSE_TO_NEXT_BAR_OPEN,
)
from darwin.core.dike import DikeState
from darwin.hermes.contract import Timeframe as HermesTimeframe
from darwin.hermes.dataset import MarketDataset, build_market_dataset
from darwin.hermes.instrument_definition import (
    InstrumentDefinition,
    get_instrument_definition,
)
from darwin.hermes.validation import RawCanonicalRow
from darwin.research_contracts.compiler import (
    CanonicalStrategyCompiler,
    ExecutableStrategyPlan,
)
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyVersion,
    build_execution_policy_version,
)
from darwin.research_contracts.input_binding import (
    ResearchInputBinding,
    research_input_binding_from_market_dataset,
)
from darwin.research_contracts.parameter_set import (
    ParameterSetVersion,
    build_parameter_set_version,
)
from darwin.research_contracts.partition_policy import (
    ResearchPartitionPolicyVersion,
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from darwin.research_contracts.research_configuration import (
    ResearchConfiguration,
    build_research_configuration,
)
from darwin.specification.applicability import (
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    IntrabarAmbiguityPolicy,
)
from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import (
    AtomicCondition,
    Direction,
    ExpiryMode,
    ExpirySpec,
)
from darwin.specification.data_requirements import (
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft, StrategyVersion
from darwin.specification.expressions import (
    Comparison,
    ComparisonOperator,
    ParameterReference,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    DataAuthorityClass,
    FactReferenceKind,
)
from darwin.specification.parameters import (
    NumericRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.provenance import (
    ProvenanceRecord,
    RuleAcceptanceState,
    RuleOrigin,
)
from darwin.specification.timeframe import Timeframe as SpecTimeframe
from darwin.specification.validation import finalise

APOLLO_REQUIREMENT_ID = "hermes_xau_usd_h1_ohlcv"
ENTRY_THRESHOLD_PARAMETER_ID = "entry_threshold_usd"
STOP_LOSS_PARAMETER_ID = "stop_loss_distance_usd"
TAKE_PROFIT_PARAMETER_ID = "take_profit_distance_usd"

UTC_2026_01_05 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def apollo_h1_ohlcv_requirement() -> DataRequirement:
    return DataRequirement(
        requirement_id=APOLLO_REQUIREMENT_ID,
        display_name="XAU_USD H1 HERMES canonical OHLCV bars",
        fact_class=FactClass.MARKET_OHLCV,
        fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        instrument_applicability=("XAU_USD",),
        timeframe=SpecTimeframe("H1"),
        required_historical_depth=HistoricalDepthRequirement(count=1, unit=HistoricalDepthUnit.BARS),
        units="USD_PER_TROY_OUNCE",
        required_fields=("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )


def apollo_close_reference() -> CanonicalFactReference:
    return CanonicalFactReference(
        fact_key="OHLCV.CLOSE",
        fact_class=FactClass.MARKET_OHLCV,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE",
        timeframe=SpecTimeframe("H1"),
        requirement_id=APOLLO_REQUIREMENT_ID,
    )


def apollo_entry_condition(condition_id: str = "entry_long", *, direction: Direction = Direction.LONG) -> AtomicCondition:
    return AtomicCondition(
        condition_id=condition_id,
        semantic_role="TRIGGER",
        timeframe=SpecTimeframe("H1"),
        expression=Comparison(
            operator=ComparisonOperator.GT,
            left=apollo_close_reference(),
            right=ParameterReference(ENTRY_THRESHOLD_PARAMETER_ID),
        ),
        direction=direction,
    )


def apollo_risk_parameter_definitions() -> tuple[ParameterDefinition, ...]:
    bounds = {
        ENTRY_THRESHOLD_PARAMETER_ID: (Decimal(0), Decimal(1000000)),
        STOP_LOSS_PARAMETER_ID: (Decimal("0.01"), Decimal(1000000)),
        TAKE_PROFIT_PARAMETER_ID: (Decimal("0.01"), Decimal(1000000)),
    }
    return tuple(
        ParameterDefinition(
            parameter_id=parameter_id,
            status=ParameterStatus.TUNABLE,
            value_type=ParameterValueType.DECIMAL,
            unit="USD_PER_TROY_OUNCE",
            domain=NumericRangeDomain(minimum=lo, maximum=hi),
        )
        for parameter_id, (lo, hi) in bounds.items()
    )


def build_apollo_draft(*, draft_id: str, candidate_id: str, composition: AtomicCondition | None = None) -> SpecificationDraft:
    condition = composition or apollo_entry_condition()
    draft = SpecificationDraft(
        draft_id=draft_id,
        candidate_id=candidate_id,
        schema_semantic_version="1.0.0",
        title="PID-006B XAU_USD candle causal core fixture",
        thesis="A controlled test fixture, not a real trading hypothesis.",
        instrument_applicability=InstrumentApplicability(
            kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("XAU_USD",)
        ),
        composition=condition,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST,
        setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )
    for definition in apollo_risk_parameter_definitions():
        draft.set_parameter(definition)
    draft.set_data_requirement(apollo_h1_ohlcv_requirement())
    from darwin.specification.composition import all_leaf_conditions

    for leaf in all_leaf_conditions(condition):
        draft.set_provenance(
            ProvenanceRecord(
                provenance_id=f"prov-{leaf.condition_id}",
                subject_ref=leaf.condition_id,
                origin=RuleOrigin.SOURCE_RULE,
                acceptance_state=RuleAcceptanceState.ACCEPTED_SPECIFICATION_RULE,
            )
        )
    return draft


def build_apollo_strategy_version(strategy_version_id: str = "sv-apollo-1", **draft_kwargs) -> StrategyVersion:
    draft = build_apollo_draft(
        draft_id=draft_kwargs.pop("draft_id", strategy_version_id),
        candidate_id=draft_kwargs.pop("candidate_id", f"{strategy_version_id}-cand"),
        **draft_kwargs,
    )
    result = finalise(draft, strategy_version_id=strategy_version_id, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert result.strategy_version is not None, result.outcome
    return result.strategy_version


def build_apollo_parameter_set(
    strategy_version: StrategyVersion,
    *,
    entry_threshold: Decimal = Decimal(4000),
    stop_loss_distance: Decimal = Decimal(5),
    take_profit_distance: Decimal = Decimal(10),
) -> ParameterSetVersion:
    return build_parameter_set_version(
        strategy_version,
        [
            (ENTRY_THRESHOLD_PARAMETER_ID, entry_threshold),
            (STOP_LOSS_PARAMETER_ID, stop_loss_distance),
            (TAKE_PROFIT_PARAMETER_ID, take_profit_distance),
        ],
    )


def apollo_row(
    open_time: datetime, o: str, h: str, l: str, c: str, *, volume: int = 100
) -> RawCanonicalRow:
    return RawCanonicalRow(
        instrument="XAU_USD",
        timeframe="H1",
        open_time=open_time,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=volume,
        is_closed=1,
        status="OK",
        source_timeframe="H1",
        derivation_policy="NONE_DIRECT",
        source_policy_epoch="DIRECT_NATIVE_V1",
        source_count=1,
        expected_source_count=1,
        source_coverage=Decimal("1.0000"),
        gap_state="NONE",
        derivation_run_id=f"DIRECT_H1:{int(open_time.timestamp())}",
        derivation_generated_at_utc=None,
        created_at=open_time,
    )


def build_apollo_dataset(dataset_id: str, rows: list[RawCanonicalRow]) -> MarketDataset:
    from datetime import timedelta

    return build_market_dataset(
        dataset_id=dataset_id,
        instrument="XAU_USD",
        instrument_definition_id=get_instrument_definition("XAU_USD").fingerprint,
        timeframe=HermesTimeframe.H1,
        requested_start_utc=rows[0].open_time,
        requested_end_utc=rows[-1].open_time + timedelta(hours=1),
        rows=rows,
        adapter_build_version="test-fixture",
        loaded_at_utc=rows[0].open_time,
    )


def build_apollo_execution_policy(
    *, cost_methodology: ExecutionPolicyComponent = ZERO_COST
) -> ExecutionPolicyVersion:
    return build_execution_policy_version(
        timing_methodology=TIMING_CLOSE_TO_NEXT_BAR_OPEN,
        price_fill_methodology=PRICE_FILL_NEXT_BAR_OPEN,
        intrabar_resolution_methodology=INTRABAR_CONSERVATIVE_SL_FIRST,
        cost_methodology=cost_methodology,
        quantity_economic_methodology=QUANTITY_FIXED_ONE_TROY_OUNCE,
        session_force_flat_methodology=SESSION_NO_FORCE_FLAT,
    )


@dataclass(frozen=True)
class ApolloFixtureBundle:
    strategy_version: StrategyVersion
    executable_plan: ExecutableStrategyPlan
    parameter_set: ParameterSetVersion
    market_dataset: MarketDataset
    instrument_definition: InstrumentDefinition
    input_binding: ResearchInputBinding
    partition_policy: ResearchPartitionPolicyVersion
    execution_policy: ExecutionPolicyVersion
    research_configuration: ResearchConfiguration


def build_apollo_fixture_bundle(
    *,
    dataset_id: str,
    rows: list[RawCanonicalRow],
    strategy_version_id: str = "sv-apollo-1",
    entry_threshold: Decimal = Decimal(4000),
    stop_loss_distance: Decimal = Decimal(5),
    take_profit_distance: Decimal = Decimal(10),
    cost_methodology: ExecutionPolicyComponent = ZERO_COST,
    dike_state: DikeState = DikeState.DISABLED,
    strategy_version: StrategyVersion | None = None,
) -> ApolloFixtureBundle:
    """Builds every object `darwin.apollo.run_apollo_candle_causal_core`
    needs, all independently governed-constructed (never hand-assembled
    dataclasses) -- the one shared assembly path every APOLLO test in this
    suite uses, so a change to the fixture strategy shape only needs to be
    made in one place."""
    sv = strategy_version or build_apollo_strategy_version(strategy_version_id)
    plan = CanonicalStrategyCompiler().compile(sv)
    parameter_set = build_apollo_parameter_set(
        sv, entry_threshold=entry_threshold, stop_loss_distance=stop_loss_distance, take_profit_distance=take_profit_distance
    )
    dataset = build_apollo_dataset(dataset_id, rows)
    instrument_definition = get_instrument_definition("XAU_USD")
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=dataset)
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    execution_policy = build_apollo_execution_policy(cost_methodology=cost_methodology)
    research_configuration = build_research_configuration(
        strategy_version=sv,
        executable_plan=plan,
        parameter_set=parameter_set,
        instrument_definition=instrument_definition,
        research_input_bindings=(binding,),
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        dike_state=dike_state,
    )
    return ApolloFixtureBundle(
        strategy_version=sv,
        executable_plan=plan,
        parameter_set=parameter_set,
        market_dataset=dataset,
        instrument_definition=instrument_definition,
        input_binding=binding,
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        research_configuration=research_configuration,
    )
