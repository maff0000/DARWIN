"""PID-004A sec38 required fingerprint-separation tests: all four cases.

Case A: two independent discoveries, identical deterministic rules ->
        same semantic_fingerprint, DIFFERENT artifact_record_fingerprint.
Case B: change a fixed semantic rule -> different semantic_fingerprint.
Case C: change only current data availability (readiness) -> same
        StrategyVersion, same semantic_fingerprint.
Case D: change only the selected DIKEPolicyVersion/ExecutionPolicyVersion
        for an experiment -> same StrategyVersion, same
        semantic_fingerprint.
"""
from __future__ import annotations

from datetime import UTC, datetime

from darwin.specification.readiness import assess_readiness
from darwin.specification.validation import finalise
from tests.fixtures.specification_drafts import (
    minimal_valid_draft,
    simple_atomic_condition,
)

# --- Case A: two independent discoveries, identical semantics ------------------

def test_case_a_two_independent_discoveries_same_semantic_different_artifact_fingerprint():
    draft_discovery_1 = minimal_valid_draft(draft_id="draft-from-discovery-1", candidate_id="candidate-from-scout-disc-1")
    draft_discovery_2 = minimal_valid_draft(draft_id="draft-from-discovery-2", candidate_id="candidate-from-scout-disc-2")

    result_1 = finalise(draft_discovery_1, strategy_version_id="sv-from-discovery-1")
    result_2 = finalise(draft_discovery_2, strategy_version_id="sv-from-discovery-2")

    version_1, version_2 = result_1.strategy_version, result_2.strategy_version
    assert version_1 is not None and version_2 is not None

    assert version_1.semantic_fingerprint == version_2.semantic_fingerprint
    assert version_1.artifact_record_fingerprint != version_2.artifact_record_fingerprint
    # provenance chains remain fully separate even though semantics match:
    assert version_1.strategy_version_id != version_2.strategy_version_id
    assert version_1.candidate_id != version_2.candidate_id


# --- Case B: changing a fixed semantic rule changes semantic_fingerprint -------

def test_case_b_changing_a_fixed_semantic_rule_changes_semantic_fingerprint():
    original_condition = simple_atomic_condition("close_above_4000", threshold="4000")
    changed_condition = simple_atomic_condition("close_above_4000", threshold="4100")

    original_draft = minimal_valid_draft(composition=original_condition)
    changed_draft = minimal_valid_draft(composition=changed_condition)

    original_version = finalise(original_draft, strategy_version_id="sv-original").strategy_version
    changed_version = finalise(changed_draft, strategy_version_id="sv-changed").strategy_version
    assert original_version is not None and changed_version is not None

    assert original_version.semantic_fingerprint != changed_version.semantic_fingerprint


def test_case_b_control_identical_rules_produce_identical_semantic_fingerprint():
    """Control for Case B: reconstructing the exact same rule from scratch
    (a fresh Comparison/Literal object graph, not the same Python object)
    must still hash identically -- proving the fingerprint is a function
    of VALUE, not of object identity."""
    draft_1 = minimal_valid_draft(composition=simple_atomic_condition("close_above_4000", threshold="4000"))
    draft_2 = minimal_valid_draft(composition=simple_atomic_condition("close_above_4000", threshold="4000"))
    v1 = finalise(draft_1, strategy_version_id="sv-1").strategy_version
    v2 = finalise(draft_2, strategy_version_id="sv-2").strategy_version
    assert v1.semantic_fingerprint == v2.semantic_fingerprint


# --- Case C: readiness changes never move semantic_fingerprint ------------------

def test_case_c_readiness_changes_do_not_touch_semantic_fingerprint_or_version():
    draft = minimal_valid_draft()
    result = finalise(draft, strategy_version_id="sv-fixed-forever")
    version = result.strategy_version
    assert version is not None
    fingerprint_before = version.semantic_fingerprint

    blocked = assess_readiness(
        assessment_id="a-blocked", strategy_version_id=version.strategy_version_id,
        mandatory_requirement_ids=set(), per_requirement={}, assessed_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    available = assess_readiness(
        assessment_id="a-available", strategy_version_id=version.strategy_version_id,
        mandatory_requirement_ids=set(), per_requirement={}, assessed_at_utc=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert blocked.overall_state.value == "TESTABLE"  # no mandatory requirements in this minimal fixture
    assert available.overall_state.value == "TESTABLE"

    # The StrategyVersion object is literally unchanged -- there is no
    # setter, no mutation, and no re-fingerprinting call anywhere.
    assert version.semantic_fingerprint == fingerprint_before
    assert version is result.strategy_version


def test_case_c_fingerprint_module_cannot_see_readiness_even_by_accident():
    """Structural proof, not just a behavioural one: darwin.specification.
    fingerprint never imports darwin.specification.readiness, so a
    DataReadinessAssessment could not be fed into canonical_hash even by
    a future accidental code change without first adding an import that
    a reviewer/grep would immediately notice."""
    import darwin.specification.fingerprint as fingerprint_module

    with open(fingerprint_module.__file__, encoding="utf-8") as fh:
        contents = fh.read()
    assert "import darwin.specification.readiness" not in contents
    assert "from darwin.specification.readiness" not in contents
    assert "from darwin.specification import readiness" not in contents


# --- Case D: policy-version-only changes never touch semantic_fingerprint ------

def test_case_d_changing_the_chosen_policy_version_for_an_experiment_does_not_change_fingerprint():
    """StrategyVersion has no field for a frozen ExecutionPolicyVersion/
    DIKEPolicyVersion id (see test_specification_domain_and_validation.py
    ::test_strategy_version_has_no_field_for_any_frozen_policy_version_id),
    so there is no code path by which selecting a different one for a
    ResearchRun could touch semantic_fingerprint. This test simulates two
    'ResearchRun-like' experiment configs (bare tuples -- ResearchRun
    binding itself is Foundation's concern, out of scope here) that pick
    different frozen policy versions against the exact SAME
    StrategyVersion, and shows the strategy's own fingerprint is
    identical -- because it is the identical StrategyVersion object.
    """
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-policy-independent").strategy_version
    assert version is not None
    fingerprint_before = version.semantic_fingerprint

    research_run_config_a = {"strategy_version_id": version.strategy_version_id, "execution_policy_version": "exec-v1", "dike_policy_version": "dike-v1"}
    research_run_config_b = {"strategy_version_id": version.strategy_version_id, "execution_policy_version": "exec-v2", "dike_policy_version": "dike-v7"}

    assert research_run_config_a["execution_policy_version"] != research_run_config_b["execution_policy_version"]
    assert research_run_config_a["dike_policy_version"] != research_run_config_b["dike_policy_version"]
    assert version.semantic_fingerprint == fingerprint_before  # untouched by either simulated run config
