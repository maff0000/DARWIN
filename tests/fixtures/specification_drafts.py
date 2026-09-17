"""Shared PID-004A SpecificationDraft builders for tests/contract fixtures.

Deliberately lives under tests/fixtures (mirrors tests/fixtures/hermes_rows.py)
rather than inside darwin.specification itself -- this is TEST-controlled
fixture data, never presented as real discovered/proven strategy evidence
(PID-004 sec30/sec41: "Controlled fixture only. Never present it as real
discovered/proven evidence.").
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from darwin.specification.applicability import (
    DstHandling,
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    IntrabarAmbiguityPolicy,
    SessionSpec,
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
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft
from darwin.specification.expressions import Comparison, ComparisonOperator, Literal
from darwin.specification.facts import (
    CanonicalFactReference,
    DataAuthorityClass,
    FactClass,
    FactReferenceKind,
)
from darwin.specification.provenance import (
    ProvenanceRecord,
    RuleAcceptanceState,
    RuleOrigin,
)
from darwin.specification.timeframe import Timeframe

XAU_USD_APPLICABILITY = InstrumentApplicability(
    kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("XAU_USD",)
)


def hermes_ohlcv_requirement_id(timeframe: str = "H1", instrument_id: str = "XAU_USD") -> str:
    """The one deterministic requirement_id every HERMES OHLCV
    `CanonicalFactReference` at this (instrument, timeframe) pair binds to
    (PID-004A hardening item 2: every canonical fact a strategy consumes
    must be deterministically backed by a declared DataRequirement --
    never left implicit)."""
    return f"hermes_{instrument_id.lower()}_{timeframe.lower()}_ohlcv"


def hermes_ohlcv_requirement(timeframe: str = "H1", instrument_id: str = "XAU_USD") -> DataRequirement:
    """The real DataRequirement backing HERMES canonical OHLCV bars at
    `timeframe` for `instrument_id` -- covers OPEN/HIGH/LOW/CLOSE/VOLUME as
    one bundle (a HERMES bar arrives as a whole, not per-field), so both
    `h1_close_reference`/`h1_high_reference` at the same timeframe are
    backed by this same requirement."""
    return DataRequirement(
        requirement_id=hermes_ohlcv_requirement_id(timeframe, instrument_id),
        display_name=f"{instrument_id} {timeframe} HERMES canonical OHLCV bars",
        fact_class=FactClass.MARKET_OHLCV,
        fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        instrument_applicability=(instrument_id,),
        timeframe=Timeframe(timeframe),
        required_historical_depth=HistoricalDepthRequirement(count=200, unit=HistoricalDepthUnit.BARS),
        units="USD_PER_TROY_OUNCE",
        required_fields=("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )


def _hermes_ohlcv_field_reference(
    field: str, timeframe: str, instrument_id: str = "XAU_USD"
) -> CanonicalFactReference:
    return CanonicalFactReference(
        fact_key=f"OHLCV.{field}",
        fact_class=FactClass.MARKET_OHLCV,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE",
        timeframe=Timeframe(timeframe),
        requirement_id=hermes_ohlcv_requirement_id(timeframe, instrument_id),
    )


def h1_close_reference(timeframe: str = "H1", *, instrument_id: str = "XAU_USD") -> CanonicalFactReference:
    return _hermes_ohlcv_field_reference("CLOSE", timeframe, instrument_id)


def h1_high_reference(timeframe: str = "H1", *, instrument_id: str = "XAU_USD") -> CanonicalFactReference:
    return _hermes_ohlcv_field_reference("HIGH", timeframe, instrument_id)


def simple_atomic_condition(
    condition_id: str = "close_above_4000",
    *,
    timeframe: str = "H1",
    semantic_role: str = "TRIGGER",
    threshold: str = "4000",
) -> AtomicCondition:
    return AtomicCondition(
        condition_id=condition_id,
        semantic_role=semantic_role,
        timeframe=Timeframe(timeframe),
        expression=Comparison(
            operator=ComparisonOperator.GT,
            left=h1_close_reference(timeframe),
            right=Literal(Decimal(threshold), unit="USD_PER_TROY_OUNCE"),
        ),
        direction=Direction.LONG,
    )


def accepted_provenance(subject_ref: str, *, origin: RuleOrigin = RuleOrigin.SOURCE_RULE) -> ProvenanceRecord:
    return ProvenanceRecord(
        provenance_id=f"prov-{subject_ref}",
        subject_ref=subject_ref,
        origin=origin,
        acceptance_state=RuleAcceptanceState.ACCEPTED_SPECIFICATION_RULE,
    )


def minimal_valid_draft(
    draft_id: str = "draft-1",
    candidate_id: str = "candidate-1",
    *,
    composition: AtomicCondition | None = None,
) -> SpecificationDraft:
    """The smallest SpecificationDraft that passes `validate_draft` cleanly:
    one atomic OHLCV condition, no other parameters/policies referenced,
    explicit NOT_APPLICABLE intrabar/expiry, no session. Its required
    HERMES market input (H1 `OHLCV.CLOSE`) is bound to a real, explicitly
    declared `DataRequirement` (PID-004A hardening item 2 -- this fixture
    used to consume canonical `OHLCV.CLOSE` while declaring zero
    DataRequirement at all, which is exactly the gap that hardening pass
    closed). Every `composition` override actually passed by this test
    suite's callers uses the same default H1 timeframe, so attaching this
    one requirement unconditionally is sufficient and never spurious."""
    condition = composition or simple_atomic_condition()
    draft = SpecificationDraft(
        draft_id=draft_id,
        candidate_id=candidate_id,
        schema_semantic_version="1.0.0",
        title="Simple close-above-level long",
        thesis="A controlled fixture, not a real trading hypothesis.",
        instrument_applicability=XAU_USD_APPLICABILITY,
        composition=condition,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
        setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    for leaf_condition_id in _leaf_ids(condition):
        draft.set_provenance(accepted_provenance(leaf_condition_id))
    return draft


def _leaf_ids(root) -> tuple[str, ...]:
    from darwin.specification.composition import all_leaf_conditions

    return tuple(c.condition_id for c in all_leaf_conditions(root))


def new_york_session() -> SessionSpec:
    return SessionSpec(
        iana_timezone="America/New_York",
        local_start="08:00",
        local_end="17:00",
        weekdays=(0, 1, 2, 3, 4),
        dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
