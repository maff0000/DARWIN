"""DIKE deterministic capital-protection identity state (Amendment A-003,
PID.md §5.12/§22b, PID-001 §1d).

Foundation records DIKE identity only -- it never evaluates or enforces a
policy. TRON is the sole system with live enforcement authority; DARWIN
researches and proves DIKE policy behaviour against historical evidence.
"""
from __future__ import annotations

from enum import StrEnum


class DikeState(StrEnum):
    DISABLED = "DIKE_DISABLED"
    GUARDED = "DIKE_GUARDED"
