"""PID-003 SCOUT domain-model unit tests (docs/pids/PID-003-SCOUT.md)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.scout.domain import (
    ALLOWED_INTAKE_TRANSITIONS,
    CLAIM_METRIC_FIELDS,
    DiscoveryRun,
    DiscoveryRunStatus,
    FamilyResolution,
    IntakeStatus,
    InvalidIntakeTransitionError,
    InvalidOriginError,
    OriginKind,
    RuleAvailability,
    ScoutDomainError,
    build_claim_values,
    build_manual_discovery,
    compute_snapshot_fingerprint,
    validate_intake_transition,
)

# --- exact-decimal handling --------------------------------------------------

def test_build_claim_values_converts_float_exactly_via_repr():
    values = build_claim_values({"net_pnl_percent": -70.08602735})
    assert values["net_pnl_percent"] == Decimal("-70.08602735")
    assert isinstance(values["net_pnl_percent"], Decimal)


def test_build_claim_values_missing_optional_metrics_stay_none():
    values = build_claim_values({"net_pnl_percent": 12.5})
    for name in CLAIM_METRIC_FIELDS:
        if name != "net_pnl_percent":
            assert values[name] is None


def test_build_claim_values_trade_count_is_exact_int():
    values = build_claim_values({"trade_count": 1470})
    assert values["trade_count"] == 1470
    assert isinstance(values["trade_count"], int)


def test_build_claim_values_rejects_malformed_text():
    with pytest.raises(ScoutDomainError):
        build_claim_values({"sharpe": "not-a-number"})


def test_build_claim_values_rejects_non_integer_trade_count():
    with pytest.raises(ScoutDomainError):
        build_claim_values({"trade_count": 12.5})


def test_build_claim_values_never_promotes_bool_to_numeric():
    with pytest.raises(ScoutDomainError):
        build_claim_values({"profit_factor": True})


# --- fingerprint --------------------------------------------------------------

def test_fingerprint_is_deterministic_for_identical_payload():
    payload = build_claim_values({"net_pnl_percent": 10, "sharpe": 1.5})
    fp1 = compute_snapshot_fingerprint(discovery_id="d1", claim_payload=payload)
    fp2 = compute_snapshot_fingerprint(discovery_id="d1", claim_payload=payload)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_changes_when_a_metric_value_changes():
    p1 = build_claim_values({"net_pnl_percent": 10})
    p2 = build_claim_values({"net_pnl_percent": 11})
    assert compute_snapshot_fingerprint(discovery_id="d1", claim_payload=p1) != compute_snapshot_fingerprint(
        discovery_id="d1", claim_payload=p2
    )


def test_fingerprint_differs_across_discoveries_for_identical_payload():
    payload = build_claim_values({"net_pnl_percent": 10})
    fp_a = compute_snapshot_fingerprint(discovery_id="discovery-a", claim_payload=payload)
    fp_b = compute_snapshot_fingerprint(discovery_id="discovery-b", claim_payload=payload)
    assert fp_a != fp_b


# --- intake transitions -------------------------------------------------------

def test_all_allowed_transitions_validate_without_raising():
    for current, targets in ALLOWED_INTAKE_TRANSITIONS.items():
        for target in targets:
            validate_intake_transition(current, target)  # must not raise


def test_same_state_transition_is_rejected_as_a_no_op():
    with pytest.raises(InvalidIntakeTransitionError):
        validate_intake_transition(IntakeStatus.NEW, IntakeStatus.NEW)


def test_disallowed_transition_is_rejected():
    with pytest.raises(InvalidIntakeTransitionError):
        validate_intake_transition(IntakeStatus.NEW, IntakeStatus.READY_FOR_SPECIFICATION)


def test_rejected_can_only_reopen_to_new():
    validate_intake_transition(IntakeStatus.REJECTED, IntakeStatus.NEW)
    with pytest.raises(InvalidIntakeTransitionError):
        validate_intake_transition(IntakeStatus.REJECTED, IntakeStatus.SHORTLISTED)


def test_in_workshop_state_exists_and_is_reachable_from_shortlisted():
    """Amendment 2026-09-17 sec10: IN_WORKSHOP is additive to the original
    NEW|SHORTLISTED|READY_FOR_SPECIFICATION|REJECTED set."""
    validate_intake_transition(IntakeStatus.SHORTLISTED, IntakeStatus.IN_WORKSHOP)


def test_ready_for_specification_never_implies_any_specified_state():
    """No PID-003 action produces SPECIFIED or a StrategyVersion -- there is
    no such state to transition into; this is a defensive existence check
    that IntakeStatus's closed set contains no such member."""
    assert "SPECIFIED" not in {s.value for s in IntakeStatus}
    assert {s.value for s in IntakeStatus} == {
        "NEW", "SHORTLISTED", "IN_WORKSHOP", "READY_FOR_SPECIFICATION", "REJECTED",
    }


# --- DiscoveryRun presence/absence invariant ----------------------------------

def test_running_discovery_run_must_not_carry_completed_at():
    with pytest.raises(ScoutDomainError):
        DiscoveryRun(
            id="r1", source_id="s1", adapter_name="a", adapter_version="v1",
            started_at_utc=datetime.now(UTC), status=DiscoveryRunStatus.RUNNING,
            completed_at_utc=datetime.now(UTC),
        )


def test_terminal_discovery_run_must_carry_completed_at():
    with pytest.raises(ScoutDomainError):
        DiscoveryRun(
            id="r1", source_id="s1", adapter_name="a", adapter_version="v1",
            started_at_utc=datetime.now(UTC), status=DiscoveryRunStatus.SUCCEEDED,
            completed_at_utc=None,
        )


def test_valid_running_and_terminal_discovery_run_construct_cleanly():
    running = DiscoveryRun(
        id="r1", source_id="s1", adapter_name="a", adapter_version="v1",
        started_at_utc=datetime.now(UTC), status=DiscoveryRunStatus.RUNNING,
    )
    assert running.completed_at_utc is None
    done = DiscoveryRun(
        id="r1", source_id="s1", adapter_name="a", adapter_version="v1",
        started_at_utc=datetime.now(UTC), status=DiscoveryRunStatus.SUCCEEDED,
        completed_at_utc=datetime.now(UTC),
    )
    assert done.completed_at_utc is not None


# --- manual discovery construction (Amendment 2026-09-17 sec10) --------------

def test_my_idea_rejects_origin_url():
    with pytest.raises(InvalidOriginError):
        build_manual_discovery(
            source_id="src-my-idea", origin_kind=OriginKind.MY_IDEA,
            title="A hunch about gold mean reversion", origin_url="https://example.invalid/x",
        )


def test_my_idea_rejects_claimed_metrics():
    with pytest.raises(InvalidOriginError):
        build_manual_discovery(
            source_id="src-my-idea", origin_kind=OriginKind.MY_IDEA,
            title="A hunch about gold mean reversion", claimed_metrics={"net_pnl_percent": 5},
        )


def test_my_idea_creates_discovery_with_zero_snapshots():
    discovery, snapshot, claim = build_manual_discovery(
        source_id="src-my-idea", origin_kind=OriginKind.MY_IDEA,
        title="A hunch about gold mean reversion",
    )
    assert discovery.origin_kind == OriginKind.MY_IDEA
    assert discovery.source_strategy_id is None
    assert discovery.origin_url is None
    assert snapshot is None
    assert claim is None
    assert discovery.discovery_lifecycle_state == "DISCOVERED"
    assert discovery.intake_status == IntakeStatus.NEW


def test_user_discovered_with_metrics_creates_snapshot_and_claim():
    discovery, snapshot, claim = build_manual_discovery(
        source_id="src-user", origin_kind=OriginKind.USER_DISCOVERED,
        title="London breakout idea from a forum post",
        origin_description="Found on a trading forum", origin_url="https://forum.example.invalid/thread/1",
        claimed_metrics={"net_pnl_percent": 42.5, "trade_count": 100},
    )
    assert snapshot is not None
    assert claim is not None
    assert claim.net_pnl_percent == Decimal("42.5")
    assert claim.trade_count == 100
    assert claim.evidence_level == "SOURCE_CLAIM"
    assert discovery.last_snapshot_id == snapshot.id


def test_user_discovered_with_no_content_creates_no_snapshot():
    _discovery, snapshot, claim = build_manual_discovery(
        source_id="src-user", origin_kind=OriginKind.USER_DISCOVERED, title="Just a bare title",
    )
    assert snapshot is None
    assert claim is None


def test_manual_discovery_requires_non_empty_title():
    with pytest.raises(ScoutDomainError):
        build_manual_discovery(source_id="src-user", origin_kind=OriginKind.USER_DISCOVERED, title="   ")


def test_pasted_rule_text_is_stored_verbatim_as_inert_text_only():
    """Untrusted-data discipline: SCOUT never executes/evals pasted text.
    This test proves the exact bytes pass through unmodified as a plain
    string field, never parsed/interpreted/executed."""
    hostile_text = "<script>alert(1)</script>; import os; os.system('rm -rf /')"
    discovery, snapshot, _claim = build_manual_discovery(
        source_id="src-user", origin_kind=OriginKind.USER_DISCOVERED, title="Suspicious paste",
        pasted_rule_text=hostile_text,
    )
    assert discovery.pasted_rule_text == hostile_text
    assert snapshot.raw_metadata["pasted_rule_text"] == hostile_text
    assert snapshot.rule_availability == RuleAvailability.AVAILABLE


def test_family_resolution_defaults_unresolved():
    discovery, _s, _c = build_manual_discovery(
        source_id="src-user", origin_kind=OriginKind.USER_DISCOVERED, title="x",
    )
    assert discovery.family_resolution == FamilyResolution.UNRESOLVED


def test_source_symbol_timeframe_never_normalized_in_domain_layer():
    """PID-003 sec4: '1d' vs 'D' vs '60' all stored exactly as supplied --
    darwin.scout.domain must never import anything from darwin.hermes (no
    implicit InstrumentId mapping exists anywhere in this module)."""
    import darwin.scout.domain as domain_module

    with open(domain_module.__file__, encoding="utf-8") as fh:
        contents = fh.read()
    assert "import darwin.hermes" not in contents
    assert "from darwin.hermes" not in contents
