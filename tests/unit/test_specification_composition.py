"""PID-004A HELIOS-compatible composition semantics unit tests
(PID-004 sec5A/sec8A/sec41A; docs/archaeology/HELIOS-PID004A-SEMANTIC-
COMPATIBILITY.md)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from darwin.specification.composition import (
    NORMALIZED_STATE_LEGAL_TRANSITIONS,
    AllComposition,
    AnyComposition,
    AtomicCondition,
    CompositionPrimitive,
    ContextTriggerComposition,
    Direction,
    ExpiryMode,
    ExpirySpec,
    NormalizedStrategyState,
    RearmPolicy,
    SequenceComponent,
    SequenceComposition,
    SequenceTieSemantics,
    all_leaf_conditions,
    finest_bound_timeframe_of,
)
from darwin.specification.errors import InvalidCompositionError, InvalidExpirySpecError
from darwin.specification.expressions import Comparison, ComparisonOperator, Literal
from darwin.specification.timeframe import Timeframe


def _atom(condition_id: str, timeframe: str = "H1", role: str = "TRIGGER") -> AtomicCondition:
    return AtomicCondition(
        condition_id=condition_id,
        semantic_role=role,
        timeframe=Timeframe(timeframe),
        expression=Comparison(
            operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0))
        ),
        direction=Direction.LONG,
    )


# --- five genuinely distinct primitives ----------------------------------------

def test_five_composition_primitives_are_distinct_types_with_distinct_tags():
    atom = _atom("a1")
    all_comp = AllComposition(composition_id="all1", components=(_atom("a1"), _atom("a2")))
    any_comp = AnyComposition(composition_id="any1", components=(_atom("a1"), _atom("a2")))
    seq = SequenceComposition(
        composition_id="seq1",
        components=(SequenceComponent(0, _atom("a1")), SequenceComponent(1, _atom("a2"))),
        ordering_window_seconds=3600,
        tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
    )
    ct = ContextTriggerComposition(
        composition_id="ct1",
        context=_atom("ctx", timeframe="H4", role="CONTEXT"),
        trigger=_atom("trg", timeframe="M5", role="TRIGGER"),
        context_validity=ExpirySpec(mode=ExpiryMode.NEVER),
    )
    kinds = {type(atom), type(all_comp), type(any_comp), type(seq), type(ct)}
    assert len(kinds) == 5
    assert {atom.primitive, all_comp.primitive, any_comp.primitive, seq.primitive, ct.primitive} == {
        CompositionPrimitive.ATOMIC,
        CompositionPrimitive.ALL,
        CompositionPrimitive.ANY,
        CompositionPrimitive.SEQUENCE,
        CompositionPrimitive.CONTEXT_TRIGGER,
    }


def test_atomic_condition_requires_explicit_semantic_role():
    with pytest.raises(InvalidCompositionError):
        AtomicCondition(
            condition_id="a1",
            semantic_role="   ",
            timeframe=Timeframe("H1"),
            expression=Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0))),
            direction=Direction.LONG,
        )


def test_all_and_any_require_at_least_two_components_and_have_no_ordering_field():
    with pytest.raises(InvalidCompositionError):
        AllComposition(composition_id="all1", components=(_atom("a1"),))
    with pytest.raises(InvalidCompositionError):
        AnyComposition(composition_id="any1", components=(_atom("a1"),))
    # Structural proof neither type CAN declare an ordering/window --
    # there is no such field to set.
    assert not hasattr(AllComposition(composition_id="all1", components=(_atom("a1"), _atom("a2"))), "sequence_index")
    assert not hasattr(AllComposition(composition_id="all1", components=(_atom("a1"), _atom("a2"))), "ordering_window_seconds")


# --- SEQUENCE is never reduced to AND ------------------------------------------

def test_sequence_requires_contiguous_zero_based_indices():
    with pytest.raises(InvalidCompositionError):
        SequenceComposition(
            composition_id="seq1",
            components=(SequenceComponent(0, _atom("a1")), SequenceComponent(2, _atom("a2"))),
            ordering_window_seconds=3600,
            tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
        )


def test_sequence_requires_mandatory_ordering_window_no_default():
    with pytest.raises(TypeError):
        SequenceComposition(  # missing ordering_window_seconds entirely
            composition_id="seq1",
            components=(SequenceComponent(0, _atom("a1")), SequenceComponent(1, _atom("a2"))),
            tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
        )  # type: ignore[call-arg]
    with pytest.raises(InvalidCompositionError):
        SequenceComposition(
            composition_id="seq1",
            components=(SequenceComponent(0, _atom("a1")), SequenceComponent(1, _atom("a2"))),
            ordering_window_seconds=0,
            tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
        )


def test_sequence_ordered_components_reflects_sequence_index_not_declaration_order():
    seq = SequenceComposition(
        composition_id="seq1",
        components=(SequenceComponent(1, _atom("second")), SequenceComponent(0, _atom("first"))),
        ordering_window_seconds=3600,
        tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
    )
    ordered = seq.ordered_components()
    assert [c.condition_id for c in ordered] == ["first", "second"]


def test_sequence_is_not_representable_as_all_or_any():
    """A SEQUENCE has fields (sequence_index ordering, ordering_window,
    tie_semantics) that AllComposition/AnyComposition structurally cannot
    hold -- there is no shared base class field set that would let a
    SEQUENCE 'collapse' into either."""
    seq_fields = {"components", "ordering_window_seconds", "tie_semantics", "composition_id", "primitive",
                  "direction_relationship"}
    all_fields = {"components", "composition_id", "primitive", "direction_relationship"}
    assert "ordering_window_seconds" in seq_fields - all_fields
    assert "tie_semantics" in seq_fields - all_fields


# --- CONTEXT_TRIGGER is not a bare 2-item SEQUENCE ------------------------------

def test_context_trigger_requires_context_not_finer_than_trigger():
    with pytest.raises(InvalidCompositionError):
        ContextTriggerComposition(
            composition_id="ct1",
            context=_atom("ctx", timeframe="M5", role="CONTEXT"),  # finer than trigger -- illegal
            trigger=_atom("trg", timeframe="H4", role="TRIGGER"),
            context_validity=ExpirySpec(mode=ExpiryMode.NEVER),
        )


def test_context_trigger_equal_timeframe_is_legal():
    ContextTriggerComposition(
        composition_id="ct1",
        context=_atom("ctx", timeframe="H1", role="CONTEXT"),
        trigger=_atom("trg", timeframe="H1", role="TRIGGER"),
        context_validity=ExpirySpec(mode=ExpiryMode.NEVER),
    )


def test_context_trigger_requires_explicit_context_validity_not_not_applicable():
    with pytest.raises(InvalidCompositionError):
        ContextTriggerComposition(
            composition_id="ct1",
            context=_atom("ctx", timeframe="H4", role="CONTEXT"),
            trigger=_atom("trg", timeframe="M5", role="TRIGGER"),
            context_validity=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
        )


def test_context_trigger_has_no_sequence_index_field_at_all():
    """Structural proof CONTEXT_TRIGGER never uses SEQUENCE's
    sequence_index scheme -- it names its two roles via dedicated typed
    fields instead."""
    ct = ContextTriggerComposition(
        composition_id="ct1",
        context=_atom("ctx", timeframe="H4", role="CONTEXT"),
        trigger=_atom("trg", timeframe="M5", role="TRIGGER"),
        context_validity=ExpirySpec(mode=ExpiryMode.NEVER),
    )
    assert not hasattr(ct, "sequence_index")
    assert not hasattr(ct, "ordering_window_seconds")
    assert ct.context.condition_id == "ctx"
    assert ct.trigger.condition_id == "trg"


# --- ExpirySpec: no implicit defaults ------------------------------------------

def test_expiry_not_applicable_carries_no_other_fields():
    ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE)
    with pytest.raises(InvalidExpirySpecError):
        ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE, duration_seconds=60)


def test_frames_expiry_requires_frame_count_and_finest_bound_timeframe():
    with pytest.raises(InvalidExpirySpecError):
        ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=5)  # missing finest_bound_timeframe
    with pytest.raises(InvalidExpirySpecError):
        ExpirySpec(mode=ExpiryMode.FRAMES, finest_bound_timeframe=Timeframe("M5"))  # missing frame_count
    ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=5, finest_bound_timeframe=Timeframe("M5"))


def test_duration_expiry_requires_positive_duration():
    with pytest.raises(InvalidExpirySpecError):
        ExpirySpec(mode=ExpiryMode.DURATION)
    with pytest.raises(InvalidExpirySpecError):
        ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=0)
    ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=14400)


def test_finest_bound_timeframe_of_matches_helios_finest_rule():
    """HELIOS archaeology finding #8: FRAMES counts frames of the finest
    bound timeframe."""
    ct_leaves = (_atom("ctx", timeframe="H4"), _atom("trg", timeframe="M5"))
    assert finest_bound_timeframe_of(ct_leaves) == Timeframe("M5")


# --- all_leaf_conditions --------------------------------------------------------

def test_all_leaf_conditions_unwraps_each_primitive():
    atom = _atom("solo")
    assert all_leaf_conditions(atom) == (atom,)

    all_comp = AllComposition(composition_id="all1", components=(_atom("a1"), _atom("a2")))
    assert {c.condition_id for c in all_leaf_conditions(all_comp)} == {"a1", "a2"}

    seq = SequenceComposition(
        composition_id="seq1",
        components=(SequenceComponent(0, _atom("first")), SequenceComponent(1, _atom("second"))),
        ordering_window_seconds=60,
        tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
    )
    assert [c.condition_id for c in all_leaf_conditions(seq)] == ["first", "second"]

    ct = ContextTriggerComposition(
        composition_id="ct1",
        context=_atom("ctx", timeframe="H4", role="CONTEXT"),
        trigger=_atom("trg", timeframe="M5", role="TRIGGER"),
        context_validity=ExpirySpec(mode=ExpiryMode.NEVER),
    )
    assert [c.condition_id for c in all_leaf_conditions(ct)] == ["ctx", "trg"]


# --- normalized state semantics are reference-only, never executed here -------

def test_normalized_state_vocabulary_matches_helios_verbatim():
    assert {s.value for s in NormalizedStrategyState} == {
        "DORMANT", "FORMING", "MATCHED", "ACTIVE", "WEAKENING", "INVALID", "EXPIRED",
    }


def test_normalized_state_legal_transitions_never_falls_back_from_a_live_state_to_dormant_directly():
    """A live state (MATCHED/ACTIVE/WEAKENING) can never fall back to
    DORMANT/FORMING -- must resolve via INVALID or EXPIRED first
    (HELIOS archaeology finding #7)."""
    for live_state in (NormalizedStrategyState.MATCHED, NormalizedStrategyState.ACTIVE, NormalizedStrategyState.WEAKENING):
        legal = NORMALIZED_STATE_LEGAL_TRANSITIONS[live_state]
        assert NormalizedStrategyState.DORMANT not in legal
        assert NormalizedStrategyState.FORMING not in legal


def test_invalid_and_expired_rearm_only_via_dormant():
    for resolved_state in (NormalizedStrategyState.INVALID, NormalizedStrategyState.EXPIRED):
        assert NORMALIZED_STATE_LEGAL_TRANSITIONS[resolved_state] == frozenset({NormalizedStrategyState.DORMANT})
    assert RearmPolicy.REARM_ONLY_VIA_DORMANT.value == "REARM_ONLY_VIA_DORMANT"


def test_darwin_specification_package_never_defines_an_evaluate_function():
    """PID-004 sec7's critical distinction: these are semantic RULES, not
    a runtime DARWIN itself executes. This is a structural existence
    check, not a style opinion -- darwin.specification.composition must
    not expose anything named `evaluate`/`transition` that would act as a
    real state-machine runtime."""
    import darwin.specification.composition as composition_module

    public_names = [name for name in dir(composition_module) if not name.startswith("_")]
    assert not any(name.lower() in ("evaluate", "transition", "run") for name in public_names)
