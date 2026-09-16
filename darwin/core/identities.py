"""Application-generated opaque stable identities (PID-001 §21).

UUIDv4 chosen over UUIDv7: Python 3.12's stdlib `uuid` module has no native
uuid7 implementation, and pulling in a third-party dependency purely for
sortable IDs is not justified at Foundation stage. IDs carry no business
meaning; human-readable names remain ordinary attributes, not identity.
"""
from __future__ import annotations

import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
