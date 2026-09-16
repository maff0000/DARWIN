"""Evidence-level/result-kind semantics (PID.md §11). Never silently blended."""
from __future__ import annotations

from enum import StrEnum


class EvidenceLevel(StrEnum):
    SOURCE_CLAIM = "SOURCE_CLAIM"
    ATHENA_RESULT = "ATHENA_RESULT"
    APOLLO_PROOF = "APOLLO_PROOF"
    PLUTUS_RESULT = "PLUTUS_RESULT"


EVIDENCE_LEVEL_IS_DARWIN_PROOF: dict[EvidenceLevel, bool] = {
    EvidenceLevel.SOURCE_CLAIM: False,
    EvidenceLevel.ATHENA_RESULT: False,
    EvidenceLevel.APOLLO_PROOF: True,
    EvidenceLevel.PLUTUS_RESULT: False,
}
