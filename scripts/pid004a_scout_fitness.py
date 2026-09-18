#!/usr/bin/env python3
"""PID-004A sec40 real-world fitness harness.

Queries the LIVE DARWIN deployment's read-only SCOUT discoveries API
(default: http://192.168.11.10:8000/api/v1/scout/discoveries -- GET only,
no auth, no mutation) and runs each real discovery through the REAL
PID-004A validator (darwin.specification.validation.validate_draft), not
a hand-written classifier function. Exact SCOUT provenance (title,
source, rule availability) is preserved and printed alongside the
validator's own findings -- nothing is rewritten to make a discovery
"fit".

Honest, structural limitation this harness deliberately does NOT work
around: PID-004A implements no automated decomposition from raw
discovery text into a typed composition (matching the HSA archaeology's
own finding, docs/archaeology/HSA-PID004A-REUSE-ASSESSMENT.md #5:
"Decomposition into atomics is described as a doctrine-guided step... not
something the repository automates"), and the brief for this harness is
explicit that no general English NLP parser is required either. So every
`SpecificationDraft` this harness builds has `composition=None` --
because there genuinely is no code anywhere in PID-004A that could turn
"RSI momentum breakout on gold" into a typed AtomicCondition without
inventing trading logic the discovery's own rule text (often
ACCESS_RESTRICTED) never actually supplied. The validator's own
`MISSING_COMPOSITION` finding is therefore not a bug in this harness -- it
is the correct, honest answer for a `SpecificationDraft` a Workshop
authoring step (PID-004B, not yet built) has not yet populated.

PID-004A hardening item 4: this harness used to take SCOUT's raw
`source_symbol` (e.g. ``"XAUUSD"``) and use it directly as an
`EXPLICIT_SINGLE` canonical instrument applicability. That was wrong --
there is no governed source-symbol -> canonical-`InstrumentId` mapping
anywhere in DARWIN, so `"XAUUSD"` was never actually a canonical
instrument id; it merely looked like one. This harness now NEVER
constructs or infers an `InstrumentApplicability` from `source_symbol` --
`instrument_applicability` is always `None` on the draft it builds
(triggering the validator's own honest `MISSING_INSTRUMENT_APPLICABILITY`
finding, alongside `MISSING_COMPOSITION`), and the raw SCOUT symbol is
carried ONLY as provenance/context in the printed row, never fed into any
specification-model construction.

Run:
    /srv/DARWIN/.venv/bin/python scripts/pid004a_scout_fitness.py [--url URL] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime

from darwin.specification.applicability import IntrabarAmbiguityPolicy
from darwin.specification.composition import ExpiryMode, ExpirySpec
from darwin.specification.domain import SpecificationDraft
from darwin.specification.validation import ValidationOutcomeStatus, validate_draft

DEFAULT_URL = "http://192.168.11.10:8000/api/v1/scout/discoveries"


def fetch_discoveries(url: str, limit: int) -> list[dict]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in ("discoveries", "items", "data", "results"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None:
            raise SystemExit(f"Unrecognised response shape: top-level keys={sorted(payload.keys())}")
    else:
        raise SystemExit(f"Unrecognised response type: {type(payload)!r}")
    return items[: limit if limit > 0 else len(items)]


def attempt_specification(discovery: dict) -> SpecificationDraft:
    """Builds the most complete SpecificationDraft this harness can
    HONESTLY build from a real discovery record, with no invented
    semantics. `composition` is always None -- see module docstring.

    `instrument_applicability` is always None too (PID-004A hardening
    item 4): there is no governed source-symbol -> canonical-InstrumentId
    mapping, so SCOUT's raw `source_symbol` (e.g. "XAUUSD") must never be
    turned into, or treated as, a canonical `InstrumentId` -- not even
    under `INSTRUMENT_GENERIC` (that kind requires real governed
    `generic_criteria`, which "we don't have a mapping for this symbol" is
    not). The raw symbol is returned separately by `classify()` below, as
    provenance/context only.
    """
    discovery_id = str(discovery.get("id", "unknown"))
    return SpecificationDraft(
        draft_id=f"scout-fitness-{discovery_id}",
        candidate_id=f"scout-fitness-candidate-{discovery_id}",
        schema_semantic_version="1.0.0",
        title=str(discovery.get("title") or "<untitled>"),
        thesis=str(discovery.get("original_description") or discovery.get("originalDescription") or ""),
        instrument_applicability=None,
        composition=None,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
        setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )


def classify(discovery: dict) -> dict:
    draft = attempt_specification(discovery)
    outcome = validate_draft(draft)  # the REAL validator -- not reimplemented here
    rule_availability = discovery.get("latest_rule_availability") or discovery.get("latestRuleAvailability")
    # Provenance/context only -- never fed into the SpecificationDraft above
    # (PID-004A hardening item 4: no source-symbol -> canonical-InstrumentId
    # mapping exists, so the raw symbol is never treated as if it were one).
    raw_source_symbol = discovery.get("source_symbol") or discovery.get("sourceSymbol")
    if outcome.status == ValidationOutcomeStatus.VALID:
        classification = "SUFFICIENTLY_DEFINED/TESTABLE_OR_DATA_BLOCKED"
    else:
        classification = "STRATEGY_NOT_SUFFICIENTLY_DEFINED"
    return {
        "discovery_id": discovery.get("id"),
        "title": discovery.get("title"),
        "origin_kind": discovery.get("origin_kind") or discovery.get("originKind"),
        "raw_source_symbol_context": raw_source_symbol,
        "latest_rule_availability": rule_availability,
        "validator_status": outcome.status.value,
        "validator_finding_codes": [f.code for f in outcome.findings],
        "classification": classification,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help="SCOUT discoveries read API (GET only)")
    parser.add_argument("--limit", type=int, default=25, help="bounded sample size (0 = all returned)")
    args = parser.parse_args()

    print(f"# PID-004A real-SCOUT-fitness harness -- {datetime.now(UTC).isoformat()}")
    print(f"# source: {args.url} (read-only GET, no auth, bounded sample of {args.limit})")

    try:
        discoveries = fetch_discoveries(args.url, args.limit)
    except Exception as exc:  # noqa: BLE001 - top-level harness reporting
        print(f"FETCH_FAILED: {exc!r}")
        return 1

    print(f"# fetched {len(discoveries)} real discoveries")

    rows = [classify(d) for d in discoveries]
    for row in rows:
        print(json.dumps(row, default=str))

    print("# --- summary ---")
    classification_counts: dict[str, int] = {}
    rule_availability_counts: dict[str, int] = {}
    for row in rows:
        classification_counts[row["classification"]] = classification_counts.get(row["classification"], 0) + 1
        key = str(row["latest_rule_availability"])
        rule_availability_counts[key] = rule_availability_counts.get(key, 0) + 1

    print("# classification counts:")
    for classification, count in sorted(classification_counts.items()):
        print(f"#   {classification}: {count}")
    print("# latest_rule_availability breakdown (context, not used to change classification):")
    for availability, count in sorted(rule_availability_counts.items()):
        print(f"#   {availability}: {count}")
    print(f"# total discoveries classified: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
