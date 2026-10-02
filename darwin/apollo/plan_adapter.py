"""PID-006B plan-adapter (Central Architecture correction CA-006B-1 /
CA-006B-4).

APOLLO's engine-native entry specification is derived EXCLUSIVELY from
the compiled `ExecutableStrategyPlan.semantic_payload` -- the exact
canonical dict shape `darwin.specification.fingerprint.canonicalize()`
produces (every dataclass instance tagged `{"__type__": ClassName, ...}`,
every enum reduced to its `.value` string, every `Decimal` reduced to
`str(...)`) -- never by independently reinterpreting raw `StrategyVersion`
semantics. This module never imports `StrategyVersion` for execution
meaning; `darwin.apollo.preflight` cross-checks
`executable_plan.source_semantic_fingerprint == strategy_version.
semantic_fingerprint` separately, purely for provenance/integrity (CA-
006B-1: "StrategyVersion may still be supplied alongside for provenance/
integrity cross-checking").

This module NEVER modifies `darwin.research_contracts.compiler`'s shared
`ExecutableStrategyPlan`/`CanonicalStrategyCompiler` contract -- it only
reads the payload that contract already produces. If the existing plan
payload shape is ever genuinely insufficient for something APOLLO needs,
that is an Architect-review escalation, not a license to change the
shared contract here.

Exhaustive gate (CA-006B-4): every one of `StrategyVersion.
SEMANTIC_FIELD_NAMES`'s eleven fields is inspected below. Each is either
actively supported and consumed, or explicitly capability-blocked -- see
the per-field `_check_*` function for each one. `schema_semantic_version`
is the one deliberate exception: it is the SPECIFICATION CONTRACT's own
schema-shape version (PID-004 sec4.4), not a trading/execution semantic --
it carries no APOLLO-relevant behavioural meaning to support or block,
exactly as `CanonicalStrategyCompiler` itself treats it (copied into the
payload for fingerprinting only, never branched on).
"""
from __future__ import annotations

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
#: #9 rejects DIKE_GUARDED outright). EXECUTION_POLICY is excluded from
#: this set because it is always mandatory for APOLLO (every replay binds
#: a real ExecutionPolicyVersion) -- that axis is checked separately
#: (DISABLED there is the contradiction, not REQUIRED).
_POLICY_CLASSES_APOLLO_CANNOT_REQUIRE = frozenset({"DIKE_POLICY", "SIZING_POLICY", "NEWS_CONTEXT_POLICY"})


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


def _check_composition(payload: dict) -> tuple[EntrySignalSpec, str]:
    """Returns `(spec, condition_timeframe_code)` -- the timeframe code is
    also needed by `_check_data_requirements` and by
    `darwin.apollo.preflight`'s dataset-timeframe-agreement check."""
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
        right_kind, right_parameter_id = "LITERAL", None
    elif right_type == "ParameterReference":
        right_kind, right_literal, right_parameter_id = "PARAMETER", None, right["parameter_id"]
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
    return spec, condition_timeframe_code


def _check_parameters(payload: dict) -> None:
    """CA-006B-4: `fixed_parameters`/`tunable_parameters` are actively
    consumed -- the two mandatory SL/TP risk-parameter ids
    (`darwin.apollo.economics`'s own convention) must be declared,
    DECIMAL-typed, in one of the two buckets."""
    declared: dict[str, dict] = {}
    for bucket_name in ("fixed_parameters", "tunable_parameters"):
        for node in payload.get(bucket_name) or []:
            if isinstance(node, dict) and node.get("__type__") == "ParameterDefinition":
                declared[node.get("parameter_id")] = node

    for parameter_id in (STOP_LOSS_PARAMETER_ID, TAKE_PROFIT_PARAMETER_ID):
        definition = declared.get(parameter_id)
        if definition is None:
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires the compiled plan to declare parameter "
                f"{parameter_id!r} (FIXED or TUNABLE, DECIMAL) -- this StrategyVersion never "
                f"told this engine how to manage risk",
                reason=CapabilityBlockReason.MISSING_RISK_PARAMETER_DECLARATION, subject_ref=parameter_id,
            )
        if definition.get("value_type") != "DECIMAL":
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires parameter {parameter_id!r} to be "
                f"DECIMAL-typed, got {definition.get('value_type')!r}",
                reason=CapabilityBlockReason.MISSING_RISK_PARAMETER_DECLARATION, subject_ref=parameter_id,
            )


def _check_policy_declarations(payload: dict) -> None:
    """CA-006B-4: every declared `PolicyCompatibilityDeclaration` is
    inspected -- a StrategyVersion requiring a policy class APOLLO cannot
    honour (DIKE/SIZING/NEWS_CONTEXT as REQUIRED), or declaring
    EXECUTION_POLICY as DISABLED (APOLLO always binds a real
    `ExecutionPolicyVersion` -- DISABLED would be a direct contradiction),
    is capability-blocked rather than silently run under a policy regime
    it never actually honours."""
    for node in payload.get("policy_declarations") or []:
        if not isinstance(node, dict) or node.get("__type__") != "PolicyCompatibilityDeclaration":
            continue
        policy_class = node.get("policy_class")
        compatibility = node.get("compatibility")
        if policy_class == "EXECUTION_POLICY" and compatibility == "DISABLED":
            raise _blocked(
                "StrategyVersion declares EXECUTION_POLICY compatibility DISABLED, but APOLLO "
                "always binds and applies a real ExecutionPolicyVersion -- this is a direct "
                "contradiction, never silently run under a policy regime the strategy forbids",
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


def _check_data_requirements(payload: dict, *, condition_timeframe_code: str) -> None:
    """CA-006B-4: the declared `data_requirements` must be EXACTLY the one
    HERMES canonical OHLCV requirement this engine slice supplies -- an
    additional requirement (e.g. news/IV/economic-release data this
    engine never supplies) is capability-blocked, never silently ignored."""
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
    if requirement.get("fact_class") != "MARKET_OHLCV" or requirement.get("authority_class") != "HERMES_CANONICAL_MARKET":
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports a HERMES_CANONICAL_MARKET/MARKET_OHLCV data "
            f"requirement only, got fact_class={requirement.get('fact_class')!r} "
            f"authority_class={requirement.get('authority_class')!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement.get("requirement_id", "?"),
        )
    requirement_timeframe = requirement.get("timeframe") or {}
    if requirement_timeframe.get("code") != condition_timeframe_code:
        raise _blocked(
            f"Data requirement timeframe {requirement_timeframe.get('code')!r} does not agree "
            f"with the entry condition's own bound timeframe {condition_timeframe_code!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT, subject_ref=requirement.get("requirement_id", "?"),
        )
    if SUPPORTED_INSTRUMENT not in (requirement.get("instrument_applicability") or []):
        raise InvalidConfigurationError(
            f"Data requirement {requirement.get('requirement_id')!r} instrument_applicability "
            f"does not include {SUPPORTED_INSTRUMENT!r}"
        )


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


def check_plan_capability(executable_plan: ExecutableStrategyPlan) -> EntrySignalSpec:
    """THE one entry point translating a compiled `ExecutableStrategyPlan`
    into APOLLO's engine-native `EntrySignalSpec` -- exhaustively checking
    every semantic field the plan carries (CA-006B-1/CA-006B-4). Raises
    `EngineCapabilityBlockedError`/`InvalidConfigurationError` -- never a
    bare crash -- for anything outside this engine slice's supported
    subset, before a single bar is ever processed.
    """
    payload = executable_plan.semantic_payload
    _check_instrument_applicability(payload)
    spec, condition_timeframe_code = _check_composition(payload)
    _check_parameters(payload)
    _check_policy_declarations(payload)
    _check_data_requirements(payload, condition_timeframe_code=condition_timeframe_code)
    _check_session_spec(payload)
    _check_intrabar_ambiguity_policy(payload)
    _check_setup_expiry(payload)
    _check_exit_rules(payload)
    return spec


def plan_condition_timeframe_code(executable_plan: ExecutableStrategyPlan) -> str:
    """Re-reads the entry condition's own bound timeframe code straight
    from the plan payload -- used by `darwin.apollo.preflight`'s
    dataset-timeframe-agreement check (preflight check #6), so that check
    also flows through the plan rather than the raw `StrategyVersion`."""
    composition = executable_plan.semantic_payload["composition"]
    timeframe_node = composition["timeframe"]
    return timeframe_node["code"]
