"""PID-004A generic canonicalisation/hashing unit tests
(darwin.specification.fingerprint)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from darwin.specification.fingerprint import (
    canonical_hash,
    canonical_json,
    canonicalize,
)


class _Color(StrEnum):
    RED = "RED"
    BLUE = "BLUE"


@dataclass(frozen=True)
class _Point:
    x: Decimal
    y: Decimal


def test_canonicalize_is_deterministic_regardless_of_dict_key_order():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert canonical_json(a) == canonical_json(b)


def test_canonicalize_decimal_uses_exact_text_not_binary_float():
    assert canonicalize(Decimal("1.10")) == "1.10"


def test_canonicalize_enum_uses_value():
    assert canonicalize(_Color.RED) == "RED"


def test_canonicalize_datetime_uses_isoformat():
    dt = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert canonicalize(dt) == dt.isoformat()


def test_canonicalize_dataclass_tags_type_name_to_avoid_collisions():
    payload = canonicalize(_Point(x=Decimal(1), y=Decimal(2)))
    assert payload["__type__"] == "_Point"
    assert payload["x"] == "1"


def test_canonical_hash_is_deterministic_and_sha256_length():
    point = _Point(x=Decimal(1), y=Decimal(2))
    h1 = canonical_hash(point)
    h2 = canonical_hash(point)
    assert h1 == h2
    assert len(h1) == 64


def test_canonical_hash_changes_when_a_field_changes():
    h1 = canonical_hash(_Point(x=Decimal(1), y=Decimal(2)))
    h2 = canonical_hash(_Point(x=Decimal(1), y=Decimal(3)))
    assert h1 != h2


def test_canonical_hash_distinguishes_structurally_similar_but_different_types():
    """Two dataclasses with identical field names/values but different
    types must never collide -- this is what makes CanonicalFactReference
    vs SpecificationDerivedFact-style distinctness survive into the
    fingerprint too."""

    @dataclass(frozen=True)
    class _OtherPoint:
        x: Decimal
        y: Decimal

    p1 = _Point(x=Decimal(1), y=Decimal(2))
    p2 = _OtherPoint(x=Decimal(1), y=Decimal(2))
    assert canonical_hash(p1) != canonical_hash(p2)


def test_canonicalize_tuple_and_list_are_equivalent():
    assert canonicalize((1, 2, 3)) == canonicalize([1, 2, 3])


def test_canonicalize_frozenset_is_sorted():
    assert canonicalize(frozenset({"b", "a"})) == ["a", "b"]
