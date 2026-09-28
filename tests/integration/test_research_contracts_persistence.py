"""PID-006A Shared Research/Proof Contracts persistence integration tests,
against a real, disposable PostgreSQL (same pattern as
tests/integration/test_specification_persistence.py). Skipped
automatically unless DARWIN_TEST_PG_DSN is set.

Every artifact persisted here is synthetic test fixture data built for
this file alone -- never presented as real research evidence.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from darwin.core.dike import DikeState
from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import build_market_dataset
from darwin.hermes.instrument_definition import get_instrument_definition
from darwin.research_contracts.compiler import CanonicalStrategyCompiler
from darwin.research_contracts.errors import PersistedFingerprintMismatchError
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    build_execution_policy_version,
)
from darwin.research_contracts.input_binding import (
    research_input_binding_from_market_dataset,
)
from darwin.research_contracts.parameter_set import build_parameter_set_version
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from darwin.research_store.db import connection
from darwin.research_store.migrations import migration_state
from darwin.research_store.research_contracts_repositories import (
    CompiledStrategyPlanRepository,
    ExecutionPolicyVersionRepository,
    ParameterSetVersionRepository,
    ResearchConfigurationRepository,
    ResearchPartitionPolicyVersionRepository,
)
from darwin.specification.parameters import (
    IntegerRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.validation import finalise
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, hourly_series
from tests.fixtures.specification_drafts import (
    minimal_valid_draft,
    simple_atomic_condition,
)

pytestmark = pytest.mark.integration


def _strategy_version(strategy_version_id: str, *, threshold: str = "4000"):
    draft = minimal_valid_draft(
        draft_id=strategy_version_id,
        candidate_id=f"{strategy_version_id}-cand",
        composition=simple_atomic_condition(threshold=threshold),
    )
    result = finalise(draft, strategy_version_id=strategy_version_id, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert result.strategy_version is not None, result.outcome
    return result.strategy_version


def _dataset(dataset_id: str):
    rows = hourly_series(UTC_2026_09_16_15, 5)
    return build_market_dataset(
        dataset_id=dataset_id,
        instrument="XAU_USD",
        instrument_definition_id="def-v1",
        timeframe=Timeframe.H1,
        requested_start_utc=rows[0].open_time,
        requested_end_utc=rows[-1].open_time + timedelta(hours=1),
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )


def _execution_policy(cid_suffix: str = "v1"):
    def comp(kind, cid):
        return ExecutionPolicyComponent(kind=kind, component_id=cid, component_version=cid_suffix)

    return build_execution_policy_version(
        timing_methodology=comp(ExecutionPolicyComponentKind.TIMING_METHODOLOGY, "NEXT_BAR_OPEN"),
        price_fill_methodology=comp(ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY, "TOUCH_PRICE"),
        intrabar_resolution_methodology=comp(
            ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY, "CONSERVATIVE_SL_FIRST"
        ),
        cost_methodology=ZERO_COST,
        quantity_economic_methodology=comp(
            ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY, "FIXED_UNIT_QUANTITY"
        ),
        session_force_flat_methodology=comp(
            ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY, "NO_FORCE_FLAT"
        ),
    )


def test_migration_0012_tables_exist_and_are_up_to_date(pg_config) -> None:
    from pathlib import Path

    import darwin.research_store as _research_store

    migrations_dir = Path(_research_store.__file__).resolve().parent / "migrations_sql"
    state = migration_state(pg_config, migrations_dir)
    assert "0012_research_contracts" in state["applied"]

    with connection(pg_config) as conn, conn.cursor() as cur:
        for table in (
            "compiled_strategy_plans",
            "parameter_set_versions",
            "execution_policy_versions",
            "research_partition_policy_versions",
            "research_configurations",
        ):
            cur.execute("SELECT to_regclass(%s) AS reg", (f"public.{table}",))
            assert cur.fetchone()["reg"] is not None, f"table {table} does not exist"


def test_compiled_strategy_plan_round_trips_without_identity_drift(pg_config) -> None:
    version = _strategy_version("sv-persist-plan-1")
    plan = CanonicalStrategyCompiler().compile(version)
    with connection(pg_config) as conn:
        repo = CompiledStrategyPlanRepository(conn)
        record, created = repo.create(plan)
        assert created is True
        assert record.fingerprint == plan.fingerprint

        fetched = repo.get_by_fingerprint(plan.fingerprint)
        assert fetched is not None
        assert fetched.fingerprint == plan.fingerprint
        assert fetched.semantic_payload == plan.semantic_payload
        assert fetched.source_semantic_fingerprint == plan.source_semantic_fingerprint


def test_compiled_strategy_plan_duplicate_create_is_idempotent(pg_config) -> None:
    version = _strategy_version("sv-persist-plan-dup", threshold="4001")
    plan = CanonicalStrategyCompiler().compile(version)
    with connection(pg_config) as conn:
        repo = CompiledStrategyPlanRepository(conn)
        record_1, created_1 = repo.create(plan)
        record_2, created_2 = repo.create(plan)
        assert created_1 is True
        assert created_2 is False
        assert record_1.id == record_2.id  # same row, never a duplicate


def test_compiled_strategy_plan_tamper_detected_on_reconstruction(pg_config) -> None:
    """Defence-in-depth proof (PID-006A sec15): even if the immutability
    trigger were bypassed (simulated here by disabling it directly --
    something no `darwin_app`-privileged code path can do), a payload
    edited without updating its own fingerprint column is caught on
    read, never silently trusted."""
    version = _strategy_version("sv-persist-plan-tamper", threshold="4002")
    plan = CanonicalStrategyCompiler().compile(version)
    with connection(pg_config) as conn:
        repo = CompiledStrategyPlanRepository(conn)
        repo.create(plan)
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE compiled_strategy_plans DISABLE TRIGGER trg_compiled_strategy_plans_immutable")
            cur.execute(
                "UPDATE compiled_strategy_plans SET semantic_payload = semantic_payload || '{\"tampered\": true}'::jsonb "
                "WHERE fingerprint = %s",
                (plan.fingerprint,),
            )
            cur.execute("ALTER TABLE compiled_strategy_plans ENABLE TRIGGER trg_compiled_strategy_plans_immutable")
        conn.commit()
        with pytest.raises(PersistedFingerprintMismatchError):
            repo.get_by_fingerprint(plan.fingerprint)


def test_immutability_trigger_rejects_ordinary_update(pg_config) -> None:
    version = _strategy_version("sv-persist-plan-trigger", threshold="4003")
    plan = CanonicalStrategyCompiler().compile(version)
    with connection(pg_config) as conn:
        repo = CompiledStrategyPlanRepository(conn)
        repo.create(plan)
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute(
                "UPDATE compiled_strategy_plans SET compiler_version = 'tampered' WHERE fingerprint = %s",
                (plan.fingerprint,),
            )
        conn.rollback()


def test_immutability_trigger_rejects_delete(pg_config) -> None:
    version = _strategy_version("sv-persist-plan-delete", threshold="4004")
    plan = CanonicalStrategyCompiler().compile(version)
    with connection(pg_config) as conn:
        repo = CompiledStrategyPlanRepository(conn)
        repo.create(plan)
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute("DELETE FROM compiled_strategy_plans WHERE fingerprint = %s", (plan.fingerprint,))
        conn.rollback()


def test_parameter_set_version_round_trips(pg_config) -> None:
    # A dedicated draft carrying one TUNABLE parameter -- minimal_valid_draft
    # itself declares none, so build one directly here rather than through
    # `_strategy_version` (which only varies the composition threshold).
    draft = minimal_valid_draft(draft_id="sv-persist-params-1", candidate_id="cand-params-1")
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="ema_period",
            status=ParameterStatus.TUNABLE,
            value_type=ParameterValueType.INTEGER,
            domain=IntegerRangeDomain(minimum=5, maximum=50),
        )
    )
    result = finalise(draft, strategy_version_id="sv-persist-params-1", now=datetime(2026, 1, 1, tzinfo=UTC))
    version = result.strategy_version
    assert version is not None

    parameter_set = build_parameter_set_version(version, (("ema_period", 21),))
    with connection(pg_config) as conn:
        repo = ParameterSetVersionRepository(conn)
        _record, created = repo.create(parameter_set)
        assert created is True
        fetched = repo.get_by_fingerprint(parameter_set.fingerprint)
        assert fetched is not None
        assert fetched.assignments == [["ema_period", 21]]


def test_execution_policy_version_round_trips(pg_config) -> None:
    policy = _execution_policy("round-trip-v1")
    with connection(pg_config) as conn:
        repo = ExecutionPolicyVersionRepository(conn)
        _record, created = repo.create(policy)
        assert created is True
        fetched = repo.get_by_fingerprint(policy.fingerprint)
        assert fetched is not None
        assert fetched.cost_methodology["component_id"] == "ZERO_COST"


def test_research_partition_policy_version_round_trips(pg_config) -> None:
    dataset = _dataset("ds-persist-1")
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=dataset)
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding)
    with connection(pg_config) as conn:
        repo = ResearchPartitionPolicyVersionRepository(conn)
        _record, created = repo.create(partition_policy)
        assert created is True
        fetched = repo.get_by_fingerprint(partition_policy.fingerprint)
        assert fetched is not None
        assert fetched.role == "PROTECTED_HOLDOUT"
        assert fetched.input_binding["governed_dataset_id"] == dataset.dataset_id


def test_research_configuration_round_trips(pg_config) -> None:
    version = _strategy_version("sv-persist-config-1")
    plan = CanonicalStrategyCompiler().compile(version)
    parameter_set = build_parameter_set_version(version, ())
    dataset = _dataset("ds-persist-config-1")
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=dataset)
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    execution_policy = _execution_policy("config-round-trip")

    configuration = build_research_configuration(
        strategy_version=version,
        executable_plan=plan,
        parameter_set=parameter_set,
        instrument_definition=get_instrument_definition("XAU_USD"),
        research_input_bindings=(binding,),
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        dike_state=DikeState.DISABLED,
    )
    with connection(pg_config) as conn:
        repo = ResearchConfigurationRepository(conn)
        _record, created = repo.create(configuration)
        assert created is True
        fetched = repo.get_by_fingerprint(configuration.fingerprint)
        assert fetched is not None
        assert fetched.strategy_semantic_fingerprint == version.semantic_fingerprint
        assert fetched.dike_state == "DIKE_DISABLED"
        assert fetched.dike_policy_fingerprint is None


def test_research_configuration_tamper_detected_on_reconstruction(pg_config) -> None:
    version = _strategy_version("sv-persist-config-tamper")
    plan = CanonicalStrategyCompiler().compile(version)
    parameter_set = build_parameter_set_version(version, ())
    dataset = _dataset("ds-persist-config-tamper")
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=dataset)
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.VALIDATION, input_binding=binding)
    execution_policy = _execution_policy("config-tamper")
    configuration = build_research_configuration(
        strategy_version=version,
        executable_plan=plan,
        parameter_set=parameter_set,
        instrument_definition=get_instrument_definition("XAU_USD"),
        research_input_bindings=(binding,),
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        dike_state=DikeState.DISABLED,
    )
    with connection(pg_config) as conn:
        repo = ResearchConfigurationRepository(conn)
        repo.create(configuration)
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE research_configurations DISABLE TRIGGER trg_research_configurations_immutable")
            cur.execute(
                "UPDATE research_configurations SET instrument_definition_id = 'TAMPERED' WHERE fingerprint = %s",
                (configuration.fingerprint,),
            )
            cur.execute("ALTER TABLE research_configurations ENABLE TRIGGER trg_research_configurations_immutable")
        conn.commit()
        with pytest.raises(PersistedFingerprintMismatchError):
            repo.get_by_fingerprint(configuration.fingerprint)
