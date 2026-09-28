"""PID-006A Shared Research/Proof Contracts persistence (DARWIN_sql /
migration 0012_research_contracts.sql).

Plain parameterised SQL, no ORM -- same discipline as
`darwin.research_store.repositories`/`.specification_repositories`. This
module is the ONLY place that translates between
`darwin.research_contracts`'s DB-agnostic domain objects
(`ExecutableStrategyPlan`, `ParameterSetVersion`, `ExecutionPolicyVersion`,
`ResearchPartitionPolicyVersion`, `ResearchConfiguration`) and Postgres
rows -- `darwin.research_contracts` itself never imports psycopg or
anything SQL-specific (tested in
tests/architecture/test_research_contracts_layering.py).

Every `create()` below is idempotent on the artifact's own content-
addressed `fingerprint` column: `INSERT ... ON CONFLICT (fingerprint) DO
NOTHING RETURNING *`, falling back to a plain `SELECT ... WHERE
fingerprint = %s` when the row already existed -- the exact idiom
`darwin.research_store.repositories.StrategyCandidateRepository.
get_or_create_for_discovery` already established for migration 0010.
Returns `(record, created)`, mirroring that same method's own return
shape.

Every `get_by_fingerprint()` below recomputes the artifact's fingerprint
from the reconstructed stored payload and compares it against the stored
`fingerprint` column before returning anything (PID-006A sec15) -- a
tampered row (payload edited, fingerprint left alone, e.g. by a manual
`UPDATE ... ` run directly against Postgres bypassing both the
`darwin_app` grant and the immutability trigger) is detected here and
raises `darwin.research_contracts.errors.PersistedFingerprintMismatchError`
rather than silently returning the tampered payload as if it were trusted.
"""
from __future__ import annotations

import json

import psycopg

from darwin.core.dike import DikeState
from darwin.research_contracts.compiler import compute_plan_fingerprint
from darwin.research_contracts.errors import PersistedFingerprintMismatchError
from darwin.research_contracts.execution_policy import (
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    compute_execution_policy_fingerprint,
)
from darwin.research_contracts.input_binding import (
    ResearchInputBinding,
    ResearchInputKind,
)
from darwin.research_contracts.parameter_set import compute_parameter_set_fingerprint
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    compute_research_partition_policy_fingerprint,
)
from darwin.research_contracts.research_configuration import (
    compute_research_configuration_fingerprint,
)
from darwin.research_store.research_contracts_models import (
    CompiledStrategyPlanRecord,
    ExecutionPolicyVersionRecord,
    ParameterSetVersionRecord,
    ResearchConfigurationRecord,
    ResearchPartitionPolicyVersionRecord,
)
from darwin.specification.fingerprint import canonicalize


def _mismatch(table: str, row_id: str, expected: str, recomputed: str) -> PersistedFingerprintMismatchError:
    return PersistedFingerprintMismatchError(
        f"{table} row id={row_id!r}: stored fingerprint {expected!r} does not match recomputed "
        f"fingerprint {recomputed!r} -- the payload and/or fingerprint column has drifted apart "
        f"since it was written"
    )


class CompiledStrategyPlanRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, plan) -> tuple[CompiledStrategyPlanRecord, bool]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO compiled_strategy_plans
                    (id, source_strategy_version_id, source_semantic_fingerprint, compiler_id,
                     compiler_version, plan_schema_version, semantic_payload, fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    plan.plan_id,
                    plan.source_strategy_version_id,
                    plan.source_semantic_fingerprint,
                    plan.compiler_id,
                    plan.compiler_version,
                    plan.plan_schema_version,
                    json.dumps(plan.semantic_payload),
                    plan.fingerprint,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return self._to_record(row), True
        return self.get_by_fingerprint(plan.fingerprint), False  # type: ignore[return-value]

    def get_by_fingerprint(self, fingerprint: str) -> CompiledStrategyPlanRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM compiled_strategy_plans WHERE fingerprint = %s", (fingerprint,))
            row = cur.fetchone()
        if row is None:
            return None
        record = self._to_record(row)
        recomputed = compute_plan_fingerprint(
            source_semantic_fingerprint=record.source_semantic_fingerprint,
            compiler_id=record.compiler_id,
            compiler_version=record.compiler_version,
            plan_schema_version=record.plan_schema_version,
            semantic_payload=record.semantic_payload,
        )
        if recomputed != record.fingerprint:
            raise _mismatch("compiled_strategy_plans", record.id, record.fingerprint, recomputed)
        return record

    def get_row(self, plan_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM compiled_strategy_plans WHERE id = %s", (plan_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _to_record(row) -> CompiledStrategyPlanRecord:
        return CompiledStrategyPlanRecord(
            id=str(row["id"]),
            source_strategy_version_id=row["source_strategy_version_id"],
            source_semantic_fingerprint=row["source_semantic_fingerprint"],
            compiler_id=row["compiler_id"],
            compiler_version=row["compiler_version"],
            plan_schema_version=row["plan_schema_version"],
            semantic_payload=row["semantic_payload"],
            fingerprint=row["fingerprint"],
            created_at_utc=row["created_at_utc"],
        )


class ParameterSetVersionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, parameter_set) -> tuple[ParameterSetVersionRecord, bool]:
        # Stored via canonicalize() -- the exact same conversion
        # compute_parameter_set_fingerprint uses internally -- so a Decimal
        # value's stored JSON text is byte-identical to what the original
        # fingerprint was computed over (never a second, hand-rolled
        # str()-based conversion that could silently drift from it).
        assignments_payload = canonicalize(list(parameter_set.assignments))
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parameter_set_versions
                    (id, source_strategy_version_id, source_semantic_fingerprint, assignments, fingerprint)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    parameter_set.parameter_set_id,
                    parameter_set.source_strategy_version_id,
                    parameter_set.source_semantic_fingerprint,
                    json.dumps(assignments_payload),
                    parameter_set.fingerprint,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return self._to_record(row), True
        return self.get_by_fingerprint(parameter_set.fingerprint), False  # type: ignore[return-value]

    def get_by_fingerprint(self, fingerprint: str) -> ParameterSetVersionRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM parameter_set_versions WHERE fingerprint = %s", (fingerprint,))
            row = cur.fetchone()
        if row is None:
            return None
        record = self._to_record(row)
        recomputed = compute_parameter_set_fingerprint(
            source_semantic_fingerprint=record.source_semantic_fingerprint,
            assignments=tuple(tuple(pair) for pair in record.assignments),
        )
        if recomputed != record.fingerprint:
            raise _mismatch("parameter_set_versions", record.id, record.fingerprint, recomputed)
        return record

    def get_row(self, parameter_set_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM parameter_set_versions WHERE id = %s", (parameter_set_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _to_record(row) -> ParameterSetVersionRecord:
        return ParameterSetVersionRecord(
            id=str(row["id"]),
            source_strategy_version_id=row["source_strategy_version_id"],
            source_semantic_fingerprint=row["source_semantic_fingerprint"],
            assignments=row["assignments"],
            fingerprint=row["fingerprint"],
            created_at_utc=row["created_at_utc"],
        )


_EXECUTION_POLICY_AXES: tuple[str, ...] = (
    "timing_methodology",
    "price_fill_methodology",
    "intrabar_resolution_methodology",
    "cost_methodology",
    "quantity_economic_methodology",
    "session_force_flat_methodology",
)


class ExecutionPolicyVersionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, execution_policy) -> tuple[ExecutionPolicyVersionRecord, bool]:
        # Stored payload is exactly `canonicalize(component)` for each axis
        # -- the SAME function `compute_execution_policy_fingerprint` uses
        # internally (via `_fingerprint_payload`) -- never a hand-rolled
        # second serialisation. This matters: `canonicalize()` on a
        # dataclass instance tags it `{"__type__": "ExecutionPolicyComponent",
        # ...}`; a hand-written dict without that tag would silently
        # produce a DIFFERENT canonical form on reconstruction and make
        # every legitimate round-trip look like tampering.
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO execution_policy_versions
                    (id, timing_methodology, price_fill_methodology, intrabar_resolution_methodology,
                     cost_methodology, quantity_economic_methodology, session_force_flat_methodology,
                     fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    execution_policy.execution_policy_id,
                    json.dumps(canonicalize(execution_policy.timing_methodology)),
                    json.dumps(canonicalize(execution_policy.price_fill_methodology)),
                    json.dumps(canonicalize(execution_policy.intrabar_resolution_methodology)),
                    json.dumps(canonicalize(execution_policy.cost_methodology)),
                    json.dumps(canonicalize(execution_policy.quantity_economic_methodology)),
                    json.dumps(canonicalize(execution_policy.session_force_flat_methodology)),
                    execution_policy.fingerprint,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return self._to_record(row), True
        return self.get_by_fingerprint(execution_policy.fingerprint), False  # type: ignore[return-value]

    def get_by_fingerprint(self, fingerprint: str) -> ExecutionPolicyVersionRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM execution_policy_versions WHERE fingerprint = %s", (fingerprint,))
            row = cur.fetchone()
        if row is None:
            return None
        record = self._to_record(row)
        # Rebuild real ExecutionPolicyComponent instances (not plain dicts)
        # before recomputing -- compute_execution_policy_fingerprint calls
        # canonicalize() on each axis expecting a dataclass, exactly as
        # `create()` above did when it first computed this fingerprint.
        rebuilt = {
            axis: ExecutionPolicyComponent(
                kind=ExecutionPolicyComponentKind(getattr(record, axis)["kind"]),
                component_id=getattr(record, axis)["component_id"],
                component_version=getattr(record, axis)["component_version"],
                configuration=tuple(tuple(pair) for pair in getattr(record, axis)["configuration"]),
            )
            for axis in _EXECUTION_POLICY_AXES
        }
        recomputed = compute_execution_policy_fingerprint(**rebuilt)
        if recomputed != record.fingerprint:
            raise _mismatch("execution_policy_versions", record.id, record.fingerprint, recomputed)
        return record

    def get_row(self, execution_policy_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM execution_policy_versions WHERE id = %s", (execution_policy_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _to_record(row) -> ExecutionPolicyVersionRecord:
        return ExecutionPolicyVersionRecord(
            id=str(row["id"]),
            timing_methodology=row["timing_methodology"],
            price_fill_methodology=row["price_fill_methodology"],
            intrabar_resolution_methodology=row["intrabar_resolution_methodology"],
            cost_methodology=row["cost_methodology"],
            quantity_economic_methodology=row["quantity_economic_methodology"],
            session_force_flat_methodology=row["session_force_flat_methodology"],
            fingerprint=row["fingerprint"],
            created_at_utc=row["created_at_utc"],
        )


class ResearchPartitionPolicyVersionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, partition_policy) -> tuple[ResearchPartitionPolicyVersionRecord, bool]:
        binding = partition_policy.input_binding
        binding_payload = {
            "input_binding_id": binding.input_binding_id,
            "logical_input_role": binding.logical_input_role,
            "input_kind": binding.input_kind.value,
            "governed_dataset_id": binding.governed_dataset_id,
            "dataset_semantic_fingerprint": binding.dataset_semantic_fingerprint,
            "fingerprint": binding.fingerprint,
        }
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_partition_policy_versions (id, role, input_binding, fingerprint)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    partition_policy.partition_policy_id,
                    partition_policy.role.value,
                    json.dumps(binding_payload),
                    partition_policy.fingerprint,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return self._to_record(row), True
        return self.get_by_fingerprint(partition_policy.fingerprint), False  # type: ignore[return-value]

    def get_by_fingerprint(self, fingerprint: str) -> ResearchPartitionPolicyVersionRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_partition_policy_versions WHERE fingerprint = %s", (fingerprint,))
            row = cur.fetchone()
        if row is None:
            return None
        record = self._to_record(row)
        rebuilt_binding = ResearchInputBinding(
            input_binding_id=record.input_binding["input_binding_id"],
            logical_input_role=record.input_binding["logical_input_role"],
            input_kind=ResearchInputKind(record.input_binding["input_kind"]),
            governed_dataset_id=record.input_binding["governed_dataset_id"],
            dataset_semantic_fingerprint=record.input_binding["dataset_semantic_fingerprint"],
            fingerprint=record.input_binding["fingerprint"],
        )
        recomputed = compute_research_partition_policy_fingerprint(
            role=ResearchPartitionRole(record.role), input_binding=rebuilt_binding
        )
        if recomputed != record.fingerprint:
            raise _mismatch("research_partition_policy_versions", record.id, record.fingerprint, recomputed)
        return record

    def get_row(self, partition_policy_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_partition_policy_versions WHERE id = %s", (partition_policy_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _to_record(row) -> ResearchPartitionPolicyVersionRecord:
        return ResearchPartitionPolicyVersionRecord(
            id=str(row["id"]),
            role=row["role"],
            input_binding=row["input_binding"],
            fingerprint=row["fingerprint"],
            created_at_utc=row["created_at_utc"],
        )


class ResearchConfigurationRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, configuration) -> tuple[ResearchConfigurationRecord, bool]:
        bindings_payload = [
            {
                "input_binding_id": b.input_binding_id,
                "logical_input_role": b.logical_input_role,
                "input_kind": b.input_kind.value,
                "governed_dataset_id": b.governed_dataset_id,
                "dataset_semantic_fingerprint": b.dataset_semantic_fingerprint,
                "fingerprint": b.fingerprint,
            }
            for b in configuration.research_input_bindings
        ]
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_configurations
                    (id, configuration_schema_version, strategy_semantic_fingerprint,
                     executable_strategy_plan_fingerprint, parameter_set_fingerprint,
                     instrument_definition_id, instrument_definition_fingerprint,
                     research_input_bindings, research_partition_policy_fingerprint,
                     execution_policy_fingerprint, dike_state, dike_policy_fingerprint,
                     required_derived_algorithm_identities, fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    configuration.research_configuration_id,
                    configuration.configuration_schema_version,
                    configuration.strategy_semantic_fingerprint,
                    configuration.executable_strategy_plan_fingerprint,
                    configuration.parameter_set_fingerprint,
                    configuration.instrument_definition_id,
                    configuration.instrument_definition_fingerprint,
                    json.dumps(bindings_payload),
                    configuration.research_partition_policy_fingerprint,
                    configuration.execution_policy_fingerprint,
                    configuration.dike_state.value,
                    configuration.dike_policy_fingerprint,
                    json.dumps([list(pair) for pair in configuration.required_derived_algorithm_identities]),
                    configuration.fingerprint,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return self._to_record(row), True
        return self.get_by_fingerprint(configuration.fingerprint), False  # type: ignore[return-value]

    def get_by_fingerprint(self, fingerprint: str) -> ResearchConfigurationRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_configurations WHERE fingerprint = %s", (fingerprint,))
            row = cur.fetchone()
        if row is None:
            return None
        record = self._to_record(row)
        rebuilt_bindings = tuple(
            ResearchInputBinding(
                input_binding_id=b["input_binding_id"],
                logical_input_role=b["logical_input_role"],
                input_kind=ResearchInputKind(b["input_kind"]),
                governed_dataset_id=b["governed_dataset_id"],
                dataset_semantic_fingerprint=b["dataset_semantic_fingerprint"],
                fingerprint=b["fingerprint"],
            )
            for b in record.research_input_bindings
        )
        recomputed = compute_research_configuration_fingerprint(
            configuration_schema_version=record.configuration_schema_version,
            strategy_semantic_fingerprint=record.strategy_semantic_fingerprint,
            executable_strategy_plan_fingerprint=record.executable_strategy_plan_fingerprint,
            parameter_set_fingerprint=record.parameter_set_fingerprint,
            instrument_definition_id=record.instrument_definition_id,
            instrument_definition_fingerprint=record.instrument_definition_fingerprint,
            research_input_bindings=rebuilt_bindings,
            research_partition_policy_fingerprint=record.research_partition_policy_fingerprint,
            execution_policy_fingerprint=record.execution_policy_fingerprint,
            dike_state=DikeState(record.dike_state),
            dike_policy_fingerprint=record.dike_policy_fingerprint,
            required_derived_algorithm_identities=tuple(
                tuple(pair) for pair in record.required_derived_algorithm_identities
            ),
        )
        if recomputed != record.fingerprint:
            raise _mismatch("research_configurations", record.id, record.fingerprint, recomputed)
        return record

    def get_row(self, research_configuration_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_configurations WHERE id = %s", (research_configuration_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _to_record(row) -> ResearchConfigurationRecord:
        return ResearchConfigurationRecord(
            id=str(row["id"]),
            configuration_schema_version=row["configuration_schema_version"],
            strategy_semantic_fingerprint=row["strategy_semantic_fingerprint"],
            executable_strategy_plan_fingerprint=row["executable_strategy_plan_fingerprint"],
            parameter_set_fingerprint=row["parameter_set_fingerprint"],
            instrument_definition_id=row["instrument_definition_id"],
            instrument_definition_fingerprint=row["instrument_definition_fingerprint"],
            research_input_bindings=row["research_input_bindings"],
            research_partition_policy_fingerprint=row["research_partition_policy_fingerprint"],
            execution_policy_fingerprint=row["execution_policy_fingerprint"],
            dike_state=row["dike_state"],
            dike_policy_fingerprint=row["dike_policy_fingerprint"],
            required_derived_algorithm_identities=row["required_derived_algorithm_identities"],
            fingerprint=row["fingerprint"],
            created_at_utc=row["created_at_utc"],
        )
