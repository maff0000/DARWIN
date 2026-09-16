"""Strategy candidate lifecycle stages (PID.md §9, PID-001 §20).

Foundation stores and validates these values; it does not implement
stage-transition business rules beyond basic representation.
"""
from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    SPECIFIED = "SPECIFIED"
    ATHENA_TESTED = "ATHENA_TESTED"
    ATHENA_QUALIFIED = "ATHENA_QUALIFIED"
    APOLLO_PROVEN = "APOLLO_PROVEN"
    PROMISING = "PROMISING"


PIPELINE_STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.DISCOVERED,
    PipelineStage.SPECIFIED,
    PipelineStage.ATHENA_TESTED,
    PipelineStage.ATHENA_QUALIFIED,
    PipelineStage.APOLLO_PROVEN,
    PipelineStage.PROMISING,
)
