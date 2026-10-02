"""PID-006B plan-adapter (Central Architecture corrections CA-006B-1,
CA-006B-4, CA-006B-8).

APOLLO's engine-native entry specification is derived EXCLUSIVELY from
the compiled `ExecutableStrategyPlan.semantic_payload` -- the exact
canonical dict shape `darwin.specification.fingerprint.canonicalize()`
produces (every dataclass instance tagged `{"__type__": ClassName, ...}`,
every enum reduced to its `.value` string, every `Decimal` reduced to
`str(...)`) -- never by independently reinterpreting raw `StrategyVersion`
semantics. This module never imports `StrategyVersion` for execution
meaning; `darwin.apollo.preflight` cross-checks
`executable_plan.source_semantic_fingerprint == strategy_version.
semantic_fingerprint`, AND independently recomputes the plan's own
`semantic_payload` from `strategy_version` and compares it field-for-field
(CA-006B-7) -- both purely for provenance/integrity, never here.

This module NEVER modifies `darwin.research_contracts.compiler`'s shared
`ExecutableStrategyPlan`/`CanonicalStrategyCompiler` contract -- it only
reads the payload that contract already produces. If the existing plan
payload shape is ever genuinely insufficient for something APOLLO needs,
that is an Architect-review escalation, not a license to change the
shared contract here.

Exhaustive gate (CA-006B-4, tightened by CA-006B-8): every one of
`StrategyVersion.SEMANTIC_FIELD_NAMES`'s eleven fields is inspected below.
Each is either actively supported and consumed, or explicitly
capability-blocked -- never "recorded but ignored". In particular
(CA-006B-8):

- `schema_semantic_version` must be one APOLLO v1 actually understands
  (`SUPPORTED_SCHEMA_SEMANTIC_VERSIONS`) -- an unrecognised schema version
  is capability-blocked, not silently assumed compatible.
- Declared parameters (`fixed_parameters`/`tunable_parameters` combined)
  must be EXACTLY the set APOLLO consumes -- the two risk parameters plus
  the entry-threshold parameter when (and only when) it is referenced via
  `ParameterReference`. Any additional declared-but-unused parameter is
  capability-blocked.
- Every parameter APOLLO consumes, and the compared OHLCV fact itself,
  must carry EXACTLY `SUPPORTED_PRICE_UNIT` -- a Literal entry value
  without that unit is equally blocked.
- The sole `DataRequirement` must be the ACTUAL requirement the compared
  fact references (`requirement_id` cross-checked, not just a shape
  match), must declare the compared field in `required_fields`, must be
  `mandatory=True`, and its historical depth must be `BARS`-denominated
  (`darwin.apollo.preflight` enforces the dataset actually has that many
  bars before replay).
- Any policy declaration carrying a non-empty `authorized_search_envelope`
  is capability-blocked outright (APOLLO implements no partial
  policy-search-envelope evaluation); `EXECUTION_POLICY` compatibility
  must be `REQUIRED` or `PERMITTED` (never `DISABLED`/`IRRELEVANT`, both
  of which would misrepresent that APOLLO always binds and applies a
  real `ExecutionPolicyVersion`).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from darwin.apollo.errors import (
    CapabilityBlockContext,
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
    InvalidConfigurationError,
)
from darwin.apollo.signal import SUPPORTED_FIELDS, SUPPORTED_OPERATORS, EntrySignalSpec
from darwin.research_contracts.compiler import ExecutableStrategyPlan

#: PID-006B scope: this engine slice's only supported instrument.
SUPPORTED_INSTRUMENT = "XAU_USD"

#: PID-006B scope: the only Specification schema shape this engine slice
#: has ever been built/tested against (CA-006B-8). A plan compiled from a
#: StrategyVersion carrying any other `schema_semantic_version` is
#: capability-blocked outright -- APOLLO cannot know a payload shape it
#: has never seen is safe to interpret the same way.
SUPPORTED_SCHEMA_SEMANTIC_VERSIONS: frozenset[str] = frozenset({"1.0.0"})

#: PID-006B scope: the one price-distance unit this engine slice
#: interprets (XAU_USD's own governed price unit --
#: `darwin.hermes.instrument_definition.get_instrument_definition
#: ("XAU_USD").price_unit`). Every SL/TP/entry-threshold parameter, and
#: the compared OHLCV fact itself, must carry exactly this unit
#: (CA-006B-8) -- never merely "is a Decimal".
SUPPORTED_PRICE_UNIT = "USD_PER_TROY_OUNCE"

#: PID-006B scope: historical depth is honoured in BARS only (CA-006B-8) --
#: `darwin.apollo.preflight` checks the supplied MarketDataset actually
#: has at least this many bars before a single bar is replayed.
SUPPORTED_HISTORICAL_DEPTH_UNIT = "BARS"

#: The one intrabar ambiguity policy this engine slice actually
#: implements (mirrors `darwin.apollo.capability.INTRABAR_CONSERVATIVE_SL_FIRST`'s
#: execution-mechanics counterpart) -- a StrategyVersion declaring
#: anything else (including `NOT_APPLICABLE`) would misrepresent the real
#: SL/TP mechanics APOLLO always applies.
SUPPORTED_INTRABAR_AMBIGUITY_POLICY = "CONSERVATIVE_SL_FIRST"

#: PID-006B engine-defined mandatory risk-parameter ids (mirrors
#: `darwin.apollo.economics`'s own constants exactly -- duplicated as
#: plain strings here, rather than importing economics.py, to keep this
#: module's only dependency the shared research_contracts compiler
#: output; kept in sync by tests/architecture/test_apollo_layering.py and
#: the integration suite).
STOP_LOSS_PARAMETER_ID = "stop_loss_distance_usd"
TAKE_PROFIT_PARAMETER_ID = "take_profit_distance_usd"

#: Policy classes APOLLO cannot honour if a StrategyVersion declares them
#: REQUIRED (APOLLO has no sizing-policy/news-context-policy mechanics,
#: and always executes under DIKE_DISABLED -- PID-006B preflight check
#: #9 rejects DIKE_GUARDED outright).
_POLICY_CLASSES_APOLLO_CANNOT_REQUIRE = frozenset({"DIKE_POLICY", "SIZING_POLICY", "NEWS_CONTEXT_POLICY"})

#: EXECUTION_POLICY is the one policy class APOLLO always genuinely uses
#: -- DISABLED/IRRELEVANT would both misrepresent that fact.
_EXECUTION_POLICY_ALLOWED_COMPATIBILITY = frozenset({"REQUIRED", "PERMITTED"})


@dataclass(frozen=True)
class ResolvedPlanCapability:
    """Everything `darwin.apollo.preflight` needs from a successful
    capability check: the engine-native entry spec, plus the mandatory
    historical depth (in bars) the supplied `MarketDataset` must satisfy
    before a single bar is replayed (CA-006B-8)."""

    entry_signal_spec: EntrySignalSpec
    required_historical_depth_bars: int


def _blocked(message: str, *, reason: CapabilityBlockReason, subject_ref: str, **detail: str) -> EngineCapabilityBlockedError:
    return EngineCapabilityBlockedError(
        message, context=CapabilityBlockContext(reason=reason, subject_ref=subject_ref, detail=tuple(detail.items()))
    )


def _dict_of_type(node: object, expected_type: str, *, subject_ref: str, field_name: str) -> dict:
    if not isinstance(node, dict) or node.get("__type__") != expected_type:
        got = node.get("__type__") if isinstance(node, dict) else type(node).__name__
        raise _blocked(
            f"APOLLO Candle Causal Core v1 expected plan field {field_name!r} to be a "
            f"canonicalized {expected_type!r}, got {got!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=subject_ref,
            field=field_name, expected_type=expected_type, got_type=str(got),
        )
    return node


def _check_schema_semantic_version(payload: dict) -> None:
    """CA-006B-8: an unrecognised `schema_semantic_version` is
    capability-blocked -- APOLLO cannot know a payload shape it has never
    seen is safe to interpret the same way as the version(s) it was
    actually built/tested against."""
    version = payload.get("schema_semantic_version")
    if version not in SUPPORTED_SCHEMA_SEMANTIC_VERSIONS:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 only understands Specification schema_semantic_version "
            f"{sorted(SUPPORTED_SCHEMA_SEMANTIC_VERSIONS)}, got {version!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_SCHEMA_SEMANTIC_VERSION, subject_ref="schema_semantic_version",
            declared_version=str(version),
        )


def _check_instrument_applicability(payload: dict) -> None:
    node = payload["instrument_applicability"]
    kind = node.get("kind") if isinstance(node, dict) else None
    if kind == "INSTRUMENT_GENERIC":
        raise _blocked(
            "APOLLO Candle Causal Core v1 supports EXPLICIT_SINGLE/EXPLICIT_SET instrument "
            "applicability only -- INSTRUMENT_GENERIC strategies are not yet evaluable by this "
            "engine slice",
            reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE, subject_ref="instrument_applicability",
            instrument_applicability_kind=str(kind),
        )
    if kind not in ("EXPLICIT_SINGLE", "EXPLICIT_SET"):
        raise _blocked(
            f"APOLLO Candle Causal Core v1 could not recognise instrument_applicability.kind "
            f"{kind!r} in the compiled plan",
            reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE, subject_ref="instrument_applicability",
        )
    instrument_ids = node.get("instrument_ids") or []
    if SUPPORTED_INSTRUMENT not in instrument_ids:
        raise InvalidConfigurationError(
            f"Compiled plan's instrument_applicability {instrument_ids!r} does not include "
            f"{SUPPORTED_INSTRUMENT!r} -- this replay request is for an instrument the strategy "
            f"does not declare itself applicable to"
        )


@dataclass(frozen=True)
class _CompositionCheckResult:
    spec: EntrySignalSpec
    condition_timeframe_code: str
    left_requirement_id: str
    compared_field: str
    entry_parameter_id: str | None  # set iff the entry RHS is a ParameterReference


def _check_composition(payload: dict) -> _CompositionCheckResult:
    composition = payload["composition"]
    if not isinstance(composition, dict) or composition.get("__type__") != "AtomicCondition":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports ATOMIC entry composition only, got "
            f"{composition.get('__type__') if isinstance(composition, dict) else type(composition).__name__!r} "
            f"in the compiled plan",
            reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE, subject_ref="composition",
        )
    condition_id = composition["condition_id"]
    if composition.get("direction") != "LONG":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports LONG direction only, got "
            f"{composition.get('direction')!r} (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_DIRECTION, subject_ref=condition_id,
            direction=str(composition.get("direction")),
        )
    timeframe_node = _dict_of_type(composition.get("timeframe"), "Timeframe", subject_ref=condition_id, field_name="composition.timeframe")
    condition_timeframe_code = timeframe_node["code"]

    expression = composition.get("expression")
    if not isinstance(expression, dict) or expression.get("__type__") != "Comparison":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports a single Comparison expression only, got "
            f"{expression.get('__type__') if isinstance(expression, dict) else type(expression).__name__!r} "
            f"(condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
        )
    operator = expression.get("operator")
    if operator not in SUPPORTED_OPERATORS:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 does not support comparison operator {operator!r} "
            f"(condition_id={condition_id!r}) -- CROSSES_ABOVE/CROSSES_BELOW require previous-bar "
            f"state, not implemented in v1",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
            operator=str(operator),
        )

    left = expression.get("left")
    if (
        not isinstance(left, dict)
        or left.get("__type__") != "CanonicalFactReference"
        or left.get("fact_class") != "MARKET_OHLCV"
    ):
        raise _blocked(
            f"APOLLO Candle Causal Core v1 requires Comparison.left to be a MARKET_OHLCV "
            f"CanonicalFactReference (condition_id={condition_id!r}), got {left!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
        )
    fact_key = left.get("fact_key", "")
    _namespace, _dot, field = fact_key.partition(".")
    if field not in SUPPORTED_FIELDS:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports OHLCV fields {sorted(SUPPORTED_FIELDS)} only, "
            f"got {fact_key!r} (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id, fact_key=fact_key,
        )
    if left.get("unit") != SUPPORTED_PRICE_UNIT:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 requires the compared OHLCV fact's unit to be exactly "
            f"{SUPPORTED_PRICE_UNIT!r}, got {left.get('unit')!r} (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_UNIT, subject_ref=condition_id, unit=str(left.get("unit")),
        )
    left_requirement_id = left.get("requirement_id")
    if not left_requirement_id:
        raise _blocked(
            f"Compared OHLCV fact carries no requirement_id (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=condition_id,
        )
    left_timeframe_node = _dict_of_type(left.get("timeframe"), "Timeframe", subject_ref=condition_id, field_name="composition.expression.left.timeframe")
    if left_timeframe_node["code"] != condition_timeframe_code:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 requires the compared OHLCV fact's own timeframe "
            f"({left_timeframe_node['code']!r}) to agree with the AtomicCondition's bound "
            f"timeframe ({condition_timeframe_code!r}) -- (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_TIMEFRAME_MISMATCH, subject_ref=condition_id,
        )

    right = expression.get("right")
    if not isinstance(right, dict):
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports Literal or ParameterReference on the "
            f"right-hand side of the entry comparison only, got {right!r} (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
        )
    right_type = right.get("__type__")
    entry_parameter_id: str | None
    if right_type == "Literal":
        raw_value = right.get("value")
        try:
            right_literal = Decimal(raw_value) if not isinstance(raw_value, bool) else None
        except (InvalidOperation, TypeError):
            right_literal = None
        if right_literal is None:
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires a Decimal Literal on the right-hand side "
                f"of the entry comparison (condition_id={condition_id!r}), got {raw_value!r}",
                reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
            )
        if right.get("unit") != SUPPORTED_PRICE_UNIT:
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires a Literal entry threshold's unit to be "
                f"exactly {SUPPORTED_PRICE_UNIT!r}, got {right.get('unit')!r} (condition_id={condition_id!r})",
                reason=CapabilityBlockReason.UNSUPPORTED_UNIT, subject_ref=condition_id, unit=str(right.get("unit")),
            )
        right_kind, right_parameter_id, entry_parameter_id = "LITERAL", None, None
    elif right_type == "ParameterReference":
        right_kind, right_literal, right_parameter_id = "PARAMETER", None, right["parameter_id"]
        entry_parameter_id = right_parameter_id
    else:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports Literal or ParameterReference on the "
            f"right-hand side of the entry comparison only, got {right_type!r} (condition_id={condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE, subject_ref=condition_id,
        )

    spec = EntrySignalSpec(
        condition_id=condition_id, field=field, operator=operator, right_kind=right_kind,
        right_literal=right_literal, right_parameter_id=right_parameter_id,
    )
    return _CompositionCheckResult(
        spec=spec, condition_timeframe_code=condition_timeframe_code, left_requirement_id=left_requirement_id,
        compared_field=field, entry_parameter_id=entry_parameter_id,
    )


def _check_parameters(payload: dict, *, entry_parameter_id: str | None) -> None:
    """CA-006B-4/CA-006B-8: `fixed_parameters`/`tunable_parameters` are
    actively consumed -- the declared set must be EXACTLY {SL distance,
    TP distance} plus the entry-threshold parameter when (and only when)
    the entry expression references one. Any additional declared
    parameter APOLLO does not consume is capability-blocked (never
    silently ignored); every consumed parameter must be DECIMAL-typed
    and carry exactly `SUPPORTED_PRICE_UNIT`."""
    declared: dict[str, dict] = {}
    for bucket_name in ("fixed_parameters", "tunable_parameters"):
        for node in payload.get(bucket_name) or []:
            if isinstance(node, dict) and node.get("__type__") == "ParameterDefinition":
                declared[node.get("parameter_id")] = node

    required_ids = {STOP_LOSS_PARAMETER_ID, TAKE_PROFIT_PARAMETER_ID}
    if entry_parameter_id is not None:
        required_ids.add(entry_parameter_id)

    extra = sorted(set(declared) - required_ids)
    if extra:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 does not consume declared parameter(s) {extra} -- a "
            f"StrategyVersion must not declare a parameter this engine never reads",
            reason=CapabilityBlockReason.UNSUPPORTED_PARAMETER_DECLARATION, subject_ref=",".join(extra),
            extra_parameter_ids=",".join(extra),
        )

    missing = sorted(required_ids - set(declared))
    if missing:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 requires the compiled plan to declare parameter(s) "
            f"{missing} (FIXED or TUNABLE, DECIMAL, unit={SUPPORTED_PRICE_UNIT!r})",
            reason=CapabilityBlockReason.MISSING_RISK_PARAMETER_DECLARATION, subject_ref=",".join(missing),
        )

    for parameter_id in sorted(required_ids):
        definition = declared[parameter_id]
        if definition.get("value_type") != "DECIMAL":
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires parameter {parameter_id!r} to be "
                f"DECIMAL-typed, got {definition.get('value_type')!r}",
                reason=CapabilityBlockReason.MISSING_RISK_PARAMETER_DECLARATION, subject_ref=parameter_id,
            )
        if definition.get("unit") != SUPPORTED_PRICE_UNIT:
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires parameter {parameter_id!r} unit to be "
                f"exactly {SUPPORTED_PRICE_UNIT!r}, got {definition.get('unit')!r}",
                reason=CapabilityBlockReason.UNSUPPORTED_UNIT, subject_ref=parameter_id,
                unit=str(definition.get("unit")),
            )


def _check_policy_declarations(payload: dict) -> None:
    """CA-006B-4/CA-006B-8: every declared `PolicyCompatibilityDeclaration`
    is inspected. APOLLO implements no partial policy-search-envelope
    evaluation at all -- ANY non-empty `authorized_search_envelope` is
    capability-blocked outright, never partially honoured. A StrategyVersion
    requiring a policy class APOLLO cannot honour (DIKE/SIZING/NEWS_CONTEXT
    as REQUIRED), or declaring EXECUTION_POLICY compatibility other than
    REQUIRED/PERMITTED (APOLLO always binds and applies a real
    `ExecutionPolicyVersion` -- DISABLED/IRRELEVANT would both be a direct
    contradiction), is equally capability-blocked."""
    for node in payload.get("policy_declarations") or []:
        if not isinstance(node, dict) or node.get("__type__") != "PolicyCompatibilityDeclaration":
            continue
        policy_class = node.get("policy_class")
        compatibility = node.get("compatibility")
        envelope = node.get("authorized_search_envelope") or []
        if envelope:
            raise _blocked(
                f"StrategyVersion declares a non-empty authorized_search_envelope for "
                f"{policy_class} -- APOLLO Candle Causal Core v1 implements no policy-search-"
                f"envelope evaluation at all, and never partially interprets one",
                reason=CapabilityBlockReason.UNSUPPORTED_POLICY_DECLARATION, subject_ref=str(policy_class),
                envelope_size=str(len(envelope)),
            )
        if policy_class == "EXECUTION_POLICY" and compatibility not in _EXECUTION_POLICY_ALLOWED_COMPATIBILITY:
            raise _blocked(
                f"StrategyVersion declares EXECUTION_POLICY compatibility {compatibility!r}, but "
                f"APOLLO always binds and applies a real ExecutionPolicyVersion -- only REQUIRED/"
                f"PERMITTED are consistent with that, never silently run under a policy regime "
                f"the strategy forbids or declares irrelevant",
                reason=CapabilityBlockReason.UNSUPPORTED_POLICY_DECLARATION, subject_ref=str(policy_class),
                compatibility=str(compatibility),
            )
        if policy_class in _POLICY_CLASSES_APOLLO_CANNOT_REQUIRE and compatibility == "REQUIRED":
            raise _blocked(
                f"StrategyVersion declares {policy_class} compatibility REQUIRED, which APOLLO "
                f"Candle Causal Core v1 has no mechanics to honour (fixed quantity, no sizing "
                f"policy; no news-context policy; DIKE_DISABLED only)",
                reason=CapabilityBlockReason.UNSUPPORTED_POLICY_DECLARATION, subject_ref=str(policy_class),
                compatibility=str(compatibility),
            )


def _check_data_requirements(
    payload: dict, *, condition_timeframe_code: str, left_requirement_id: str, compared_field: str
) -> int:
    """CA-006B-4/CA-006B-8: the declared `data_requirements` must be
    EXACTLY the one HERMES canonical OHLCV requirement the compared fact
    itself references (`requirement_id` cross-checked -- a requirement
    with the right generic shape but a different identity is a
    structurally orphaned/mismatched binding, not a superficial pass),
    must declare the compared field, must be mandatory, and its
    historical depth must be BARS-denominated. Returns the required bar
    count for `darwin.apollo.preflight` to enforce against the actual
    `MarketDataset`."""
    requirements = payload.get("data_requirements") or []
    if len(requirements) != 1:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports exactly one data requirement (HERMES "
            f"canonical OHLCV), got {len(requirements)}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref="data_requirements",
            requirement_count=str(len(requirements)),
        )
    requirement = requirements[0]
    if not isinstance(requirement, dict) or requirement.get("__type__") != "DataRequirement":
        raise _blocked(
            "APOLLO Candle Causal Core v1 could not recognise the declared data requirement",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref="data_requirements",
        )
    requirement_id = requirement.get("requirement_id")
    if requirement_id != left_requirement_id:
        raise _blocked(
            f"The declared data requirement_id {requirement_id!r} does not match the compared "
            f"fact's own requirement_id {left_requirement_id!r} -- a requirement with the right "
            f"shape but the wrong identity is a structurally mismatched binding",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=str(requirement_id),
        )
    if requirement.get("fact_class") != "MARKET_OHLCV" or requirement.get("authority_class") != "HERMES_CANONICAL_MARKET":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports a HERMES_CANONICAL_MARKET/MARKET_OHLCV data "
            f"requirement only, got fact_class={requirement.get('fact_class')!r} "
            f"authority_class={requirement.get('authority_class')!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    requirement_timeframe = requirement.get("timeframe") or {}
    if requirement_timeframe.get("code") != condition_timeframe_code:
        raise _blocked(
            f"Data requirement timeframe {requirement_timeframe.get('code')!r} does not agree "
            f"with the entry condition's own bound timeframe {condition_timeframe_code!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    if SUPPORTED_INSTRUMENT not in (requirement.get("instrument_applicability") or []):
        raise InvalidConfigurationError(
            f"Data requirement {requirement_id!r} instrument_applicability does not include "
            f"{SUPPORTED_INSTRUMENT!r}"
        )
    required_fields = requirement.get("required_fields") or []
    if compared_field not in required_fields:
        raise _blocked(
            f"Data requirement {requirement_id!r} required_fields {required_fields!r} does not "
            f"include the compared field {compared_field!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    if requirement.get("mandatory") is not True:
        raise _blocked(
            f"Data requirement {requirement_id!r} must be mandatory=True -- APOLLO treats its "
            f"one supported market-data requirement as a hard dependency, never optional",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    depth = requirement.get("required_historical_depth")
    if not isinstance(depth, dict) or depth.get("__type__") != "HistoricalDepthRequirement":
        raise _blocked(
            f"Data requirement {requirement_id!r} carries no recognisable required_historical_depth",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    if depth.get("unit") != SUPPORTED_HISTORICAL_DEPTH_UNIT:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 honours historical depth in "
            f"{SUPPORTED_HISTORICAL_DEPTH_UNIT!r} only, got {depth.get('unit')!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_HISTORICAL_DEPTH_UNIT, subject_ref=requirement_id,
            depth_unit=str(depth.get("unit")),
        )
    count = depth.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise _blocked(
            f"Data requirement {requirement_id!r} required_historical_depth.count must be a "
            f"positive integer, got {count!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement_id,
        )
    return count


def _check_session_spec(payload: dict) -> None:
    """CA-006B-4: APOLLO v1 implements no session-based filtering/force-flat
    at all -- a non-null `session_spec` is a real, unimplemented semantic
    (e.g. a London/New York session restriction) and must never silently
    run as if the session restriction did not exist."""
    if payload.get("session_spec") is not None:
        raise _blocked(
            "APOLLO Candle Causal Core v1 implements no session-based filtering -- a "
            "StrategyVersion declaring a non-null session_spec cannot be silently run as if the "
            "session restriction did not exist",
            reason=CapabilityBlockReason.UNSUPPORTED_SESSION_SPEC, subject_ref="session_spec",
        )


def _check_intrabar_ambiguity_policy(payload: dict) -> None:
    policy = payload.get("intrabar_ambiguity_policy")
    if policy != SUPPORTED_INTRABAR_AMBIGUITY_POLICY:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 only ever applies CONSERVATIVE_SL_FIRST intrabar "
            f"resolution -- a StrategyVersion declaring intrabar_ambiguity_policy={policy!r} "
            f"would misrepresent the real mechanics this engine applies",
            reason=CapabilityBlockReason.UNSUPPORTED_INTRABAR_AMBIGUITY_POLICY, subject_ref="intrabar_ambiguity_policy",
            declared_policy=str(policy),
        )


def _check_setup_expiry(payload: dict) -> None:
    """CA-006B-4: APOLLO v1 implements no general setup-expiry mechanic
    (an order's own next-bar-open-or-end-of-data terminal outcome is
    unconditional engine mechanics, never a per-strategy FRAMES/DURATION
    expiry window) -- only `NOT_APPLICABLE` is supported."""
    expiry = payload.get("setup_expiry")
    mode = expiry.get("mode") if isinstance(expiry, dict) else None
    if mode != "NOT_APPLICABLE":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 implements no setup-expiry mechanic -- a "
            f"StrategyVersion declaring setup_expiry.mode={mode!r} is not yet evaluable by this "
            f"engine slice",
            reason=CapabilityBlockReason.UNSUPPORTED_SETUP_EXPIRY, subject_ref="setup_expiry",
            declared_mode=str(mode),
        )


def _check_exit_rules(payload: dict) -> None:
    exit_rules = payload.get("exit_rules") or []
    if exit_rules:
        raise _blocked(
            "APOLLO Candle Causal Core v1 supports no StrategyVersion-level exit_rules -- "
            "position exit is via SL/TP parameters only (see darwin.apollo.economics)",
            reason=CapabilityBlockReason.UNSUPPORTED_EXIT_RULES, subject_ref="exit_rules",
            exit_rules_count=str(len(exit_rules)),
        )


def check_plan_capability(executable_plan: ExecutableStrategyPlan) -> ResolvedPlanCapability:
    """THE one entry point translating a compiled `ExecutableStrategyPlan`
    into APOLLO's engine-native capability result -- exhaustively checking
    every semantic field the plan carries (CA-006B-1/CA-006B-4/CA-006B-8).
    Raises `EngineCapabilityBlockedError`/`InvalidConfigurationError` --
    never a bare crash -- for anything outside this engine slice's
    supported subset, before a single bar is ever processed.
    """
    payload = executable_plan.semantic_payload
    _check_schema_semantic_version(payload)
    _check_instrument_applicability(payload)
    composition_result = _check_composition(payload)
    _check_parameters(payload, entry_parameter_id=composition_result.entry_parameter_id)
    _check_policy_declarations(payload)
    required_depth_bars = _check_data_requirements(
        payload, condition_timeframe_code=composition_result.condition_timeframe_code,
        left_requirement_id=composition_result.left_requirement_id, compared_field=composition_result.compared_field,
    )
    _check_session_spec(payload)
    _check_intrabar_ambiguity_policy(payload)
    _check_setup_expiry(payload)
    _check_exit_rules(payload)
    return ResolvedPlanCapability(entry_signal_spec=composition_result.spec, required_historical_depth_bars=required_depth_bars)


def plan_condition_timeframe_code(executable_plan: ExecutableStrategyPlan) -> str:
    """Re-reads the entry condition's own bound timeframe code straight
    from the plan payload -- used by `darwin.apollo.preflight`'s
    dataset-timeframe-agreement check (preflight check #6), so that check
    also flows through the plan rather than the raw `StrategyVersion`."""
    composition = executable_plan.semantic_payload["composition"]
    timeframe_node = composition["timeframe"]
    return timeframe_node["code"]
