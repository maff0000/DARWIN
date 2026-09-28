"""PID-006A ResearchInputBinding / ResearchPartitionPolicyVersion tests
(docs/pids/PID-006-APOLLO.md sec9/sec10)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import build_market_dataset
from darwin.research_contracts.errors import (
    InvalidConfigurationError,
    ResearchInputBindingError,
)
from darwin.research_contracts.input_binding import (
    ResearchInputKind,
    build_research_input_binding,
    research_input_binding_from_market_dataset,
)
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, hourly_series


def _dataset(dataset_id: str = "ds-1", n: int = 5):
    rows = hourly_series(UTC_2026_09_16_15, n)
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


def _binding(dataset_id: str = "ds-1", role: str = "PRIMARY_MARKET_DATA"):
    return research_input_binding_from_market_dataset(logical_input_role=role, market_dataset=_dataset(dataset_id))


# --- ResearchInputBinding ----------------------------------------------------


def test_binds_market_dataset_identity_never_a_filesystem_path() -> None:
    dataset = _dataset()
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=dataset)
    assert binding.governed_dataset_id == dataset.dataset_id
    assert binding.dataset_semantic_fingerprint == dataset.fingerprint_sha256
    assert binding.input_kind == ResearchInputKind.MARKET_CANDLE_DATASET


def test_input_binding_rejects_empty_role() -> None:
    with pytest.raises(ResearchInputBindingError):
        build_research_input_binding(
            logical_input_role="",
            input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
            governed_dataset_id="ds-1",
            dataset_semantic_fingerprint="abc123",
        )


def test_different_dataset_identity_produces_different_binding_fingerprint() -> None:
    b1 = _binding("ds-1")
    b2 = _binding("ds-2")
    assert b1.fingerprint != b2.fingerprint


# --- ResearchPartitionPolicyVersion ------------------------------------------


def test_development_validation_holdout_are_structurally_distinct() -> None:
    binding = _binding()
    dev = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    val = build_research_partition_policy_version(role=ResearchPartitionRole.VALIDATION, input_binding=binding)
    holdout = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding)
    assert len({dev.fingerprint, val.fingerprint, holdout.fingerprint}) == 3


def test_same_role_different_dataset_identity_produces_different_fingerprint() -> None:
    binding_a = _binding("ds-a")
    binding_b = _binding("ds-b")
    policy_a = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding_a)
    policy_b = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding_b)
    assert policy_a.fingerprint != policy_b.fingerprint


def test_protected_holdout_distinguishable_by_role_and_data_identity_not_role_alone() -> None:
    """PID-006A sec9: a PROTECTED_HOLDOUT bound to dataset A must never be
    confusable with a PROTECTED_HOLDOUT bound to dataset B merely because
    both carry the same role label."""
    binding_a = _binding("ds-a")
    binding_b = _binding("ds-b")
    holdout_a = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding_a)
    holdout_b = build_research_partition_policy_version(role=ResearchPartitionRole.PROTECTED_HOLDOUT, input_binding=binding_b)
    assert holdout_a.role == holdout_b.role == ResearchPartitionRole.PROTECTED_HOLDOUT
    assert holdout_a.fingerprint != holdout_b.fingerprint


def test_deterministic_regardless_of_construction_argument_ordering() -> None:
    dataset = _dataset()
    binding_first = build_research_input_binding(
        logical_input_role="PRIMARY_MARKET_DATA",
        input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        governed_dataset_id=dataset.dataset_id,
        dataset_semantic_fingerprint=dataset.fingerprint_sha256,
    )
    binding_second = build_research_input_binding(
        dataset_semantic_fingerprint=dataset.fingerprint_sha256,
        governed_dataset_id=dataset.dataset_id,
        input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        logical_input_role="PRIMARY_MARKET_DATA",
    )
    assert binding_first.fingerprint == binding_second.fingerprint

    policy_first = build_research_partition_policy_version(role=ResearchPartitionRole.VALIDATION, input_binding=binding_first)
    policy_second = build_research_partition_policy_version(input_binding=binding_second, role=ResearchPartitionRole.VALIDATION)
    assert policy_first.fingerprint == policy_second.fingerprint


def test_invalid_role_rejected() -> None:
    binding = _binding()
    with pytest.raises(InvalidConfigurationError):
        build_research_partition_policy_version(role="NOT_A_REAL_ROLE", input_binding=binding)  # type: ignore[arg-type]
