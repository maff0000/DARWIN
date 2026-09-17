"""PID-004A canonical-vs-derived fact model + causal external-fact model
unit tests (PID-004 sec9/sec9A/sec10/sec24A/sec25A/sec31A)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from darwin.specification.causal import (
    CausalTimingPolicy,
    ExternalFactObservation,
    is_causally_available,
    select_causally_available_revision,
)
from darwin.specification.errors import (
    CausalTimingViolationError,
    FactReferenceKindError,
    SpecificationError,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    DataAuthorityClass,
    FactReferenceKind,
    MissingInputBehavior,
    SpecificationDerivedFact,
    derivation_chain_algorithms,
    fact_reference_kind,
    require_canonical,
)
from darwin.specification.timeframe import Timeframe

# --- canonical vs derived: structural distinctness -----------------------------

def _canonical_close(timeframe: str = "H1") -> CanonicalFactReference:
    return CanonicalFactReference(
        fact_key="OHLCV.CLOSE",
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE",
        timeframe=Timeframe(timeframe),
    )


def _ema_50(input_fact: CanonicalFactReference | SpecificationDerivedFact | None = None) -> SpecificationDerivedFact:
    return SpecificationDerivedFact(
        derived_fact_id="ema_50_h1",
        input_facts=(input_fact or _canonical_close(),),
        algorithm_id="EMA",
        algorithm_version="v1",
        parameters=(("period", 50),),
        timeframe=Timeframe("H1"),
        warm_up_bars=50,
        output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )


def test_canonical_and_derived_are_genuinely_distinct_types():
    canonical = _canonical_close()
    derived = _ema_50()
    assert type(canonical) is not type(derived)
    assert fact_reference_kind(canonical) == FactReferenceKind.CANONICAL_FACT_REFERENCE
    assert fact_reference_kind(derived) == FactReferenceKind.SPECIFICATION_DERIVED_FACT


def test_derived_fact_cannot_claim_canonical_authority():
    """PID-004 sec9A: 'A derived value must never masquerade as a HERMES
    canonical fact.' This is enforced structurally: SpecificationDerivedFact
    has no field that could make it pass a canonical-only check, and
    `require_canonical` proves that by raising."""
    derived = _ema_50()
    with pytest.raises(FactReferenceKindError):
        require_canonical(derived)
    # the canonical reference DOES pass:
    assert require_canonical(_canonical_close()) is not None


def test_fact_reference_kind_rejects_non_fact_objects():
    with pytest.raises(FactReferenceKindError):
        fact_reference_kind(object())  # type: ignore[arg-type]


def test_canonical_fact_reference_kind_is_fixed():
    with pytest.raises(FactReferenceKindError):
        CanonicalFactReference(
            fact_key="OHLCV.CLOSE",
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
            unit="USD_PER_TROY_OUNCE",
            timeframe=Timeframe("H1"),
            kind=FactReferenceKind.SPECIFICATION_DERIVED_FACT,
        )


def test_derived_fact_requires_at_least_one_input():
    with pytest.raises(SpecificationError):
        SpecificationDerivedFact(
            derived_fact_id="orphan",
            input_facts=(),
            algorithm_id="EMA",
            algorithm_version="v1",
            parameters=(),
            timeframe=Timeframe("H1"),
            warm_up_bars=1,
            output_unit="USD",
            missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
        )


def test_derivation_chain_recurses_through_nested_derived_facts():
    """A derived fact computed from another derived fact -- the chain must
    surface BOTH algorithm/version pairs, canonical leaves excluded."""
    inner = _ema_50()
    outer = SpecificationDerivedFact(
        derived_fact_id="ema_of_ema",
        input_facts=(inner,),
        algorithm_id="EMA",
        algorithm_version="v2",
        parameters=(("period", 10),),
        timeframe=Timeframe("H1"),
        warm_up_bars=10,
        output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    chain = derivation_chain_algorithms(outer)
    assert chain == (("EMA", "v2"), ("EMA", "v1"))
    assert derivation_chain_algorithms(_canonical_close()) == ()


# --- causal external-fact semantics --------------------------------------------

def _obs(*, revision: str, published_hours_ago: int, effective_hours_ago: int, value: object) -> ExternalFactObservation:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ExternalFactObservation(
        fact_requirement_id="cpi_yoy",
        event_time=now - timedelta(hours=published_hours_ago + 1),
        published_at_utc=now - timedelta(hours=published_hours_ago),
        observed_at_utc=now - timedelta(hours=published_hours_ago),
        effective_at_utc=now - timedelta(hours=effective_hours_ago),
        revision=revision,
        value=value,
    )


def test_effective_before_published_is_rejected():
    """A fact cannot become causally available before it was published."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(CausalTimingViolationError):
        ExternalFactObservation(
            fact_requirement_id="cpi_yoy",
            event_time=now - timedelta(hours=2),
            published_at_utc=now,
            observed_at_utc=now,
            effective_at_utc=now - timedelta(hours=1),
            revision="original",
            value=3.1,
        )


def test_observed_before_published_is_rejected():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(CausalTimingViolationError):
        ExternalFactObservation(
            fact_requirement_id="cpi_yoy",
            event_time=now - timedelta(hours=2),
            published_at_utc=now,
            observed_at_utc=now - timedelta(hours=1),
            effective_at_utc=now,
            revision="original",
            value=3.1,
        )


def test_is_causally_available_boundary_is_inclusive():
    obs = _obs(revision="original", published_hours_ago=2, effective_hours_ago=2, value=3.1)
    assert is_causally_available(obs, decision_instant_utc=obs.effective_at_utc)
    assert not is_causally_available(obs, decision_instant_utc=obs.effective_at_utc - timedelta(seconds=1))


def test_a_later_revision_cannot_leak_backward():
    """PID-004 sec24A/sec31A: 'A later-revised number must never leak
    backward.' original is effective at T; revision is effective at T+48h
    (published later). A decision instant BEFORE the revision's own
    effective time must never see the revision."""
    original = _obs(revision="original", published_hours_ago=48, effective_hours_ago=48, value=3.0)
    revision = _obs(revision="revised", published_hours_ago=2, effective_hours_ago=2, value=3.4)

    decision_at_original_time = original.effective_at_utc
    selected = select_causally_available_revision(
        [original, revision], decision_instant_utc=decision_at_original_time
    )
    assert selected is original
    assert selected.value == 3.0  # never the revised 3.4

    decision_after_revision = revision.effective_at_utc
    selected_later = select_causally_available_revision(
        [original, revision], decision_instant_utc=decision_after_revision
    )
    assert selected_later is revision
    assert selected_later.value == 3.4


def test_no_observation_available_before_any_effective_instant_returns_none():
    obs = _obs(revision="original", published_hours_ago=1, effective_hours_ago=1, value=3.0)
    too_early = obs.effective_at_utc - timedelta(days=1)
    assert select_causally_available_revision([obs], decision_instant_utc=too_early) is None


def test_select_requires_observations_of_exactly_one_fact():
    obs_a = _obs(revision="a", published_hours_ago=1, effective_hours_ago=1, value=1)
    obs_b = ExternalFactObservation(
        fact_requirement_id="different_fact",
        event_time=obs_a.event_time,
        published_at_utc=obs_a.published_at_utc,
        observed_at_utc=obs_a.observed_at_utc,
        effective_at_utc=obs_a.effective_at_utc,
        revision="b",
        value=2,
    )
    with pytest.raises(SpecificationError):
        select_causally_available_revision([obs_a, obs_b], decision_instant_utc=obs_a.effective_at_utc)


def test_causal_timing_policy_not_applicable_is_a_real_explicit_value():
    assert CausalTimingPolicy.NOT_APPLICABLE.value == "NOT_APPLICABLE"
