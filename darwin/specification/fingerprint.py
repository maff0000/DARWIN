"""Generic canonicalisation + deterministic hashing (PID-004 sec38).

This module knows nothing about strategy semantics. It walks whatever
Python object graph it is given (dataclasses, enums, tuples, dicts,
Decimal, datetime) into a deterministic, JSON-serialisable structure and
SHA-256 hashes it -- mirroring `darwin.scout.domain.compute_snapshot_
fingerprint`'s exact-Decimal-text, stable-key-order discipline, generalised
to an arbitrary object tree so `darwin.specification.domain` never has to
hand-write per-type serialisation.

Which fields actually get fed into this module is entirely
`darwin.specification.domain.StrategyVersion.semantic_payload`/
`artifact_payload`'s responsibility -- this module has no opinion on
"semantic" vs "artifact", and deliberately does not import
`darwin.specification.readiness` at all, so a DataReadinessAssessment
could not be canonicalised through this path even by accident.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


def canonicalize(obj: object) -> object:
    """Deterministic, JSON-safe canonical form of `obj`. Dataclass
    instances are tagged with their own class name (`__type__`) so that
    two structurally-similar-but-distinct types (e.g.
    `CanonicalFactReference` vs `SpecificationDerivedFact`) never collide
    even if some field names happen to overlap."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        fields = dataclasses.fields(obj)
        return {
            "__type__": type(obj).__name__,
            **{f.name: canonicalize(getattr(obj, f.name)) for f in fields},
        }
    if isinstance(obj, (list, tuple)):
        return [canonicalize(v) for v in obj]
    if isinstance(obj, frozenset):
        return sorted(canonicalize(v) for v in obj)
    if isinstance(obj, dict):
        return {str(k): canonicalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    raise TypeError(f"canonicalize: unsupported type {type(obj)!r} for value {obj!r}")


def canonical_json(obj: object) -> str:
    return json.dumps(canonicalize(obj), sort_keys=True, separators=(",", ":"))


def canonical_hash(obj: object) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
