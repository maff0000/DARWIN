"""Evidence-level/result-kind semantics (PID.md §11). Never silently blended."""
from __future__ import annotations

from enum import StrEnum


class EvidenceLevel(StrEnum):
    SOURCE_CLAIM = "SOURCE_CLAIM"
    ATHENA_RESULT = "ATHENA_RESULT"
    APOLLO_PROOF = "APOLLO_PROOF"
    #: PID-006B -- every APOLLO Candle Causal Core (v1) run persists at
    #: this level, ALWAYS, regardless of which cost policy was used
    #: (ZERO_COST mechanical run or a non-zero-cost run). This package
    #: implements no proof-eligibility gating (that requires a real
    #: proof-partition/holdout policy and genuine economic-cost-policy
    #: governance PID-006B does not build) -- `APOLLO_PROOF` above is
    #: left completely unchanged and is never produced by this engine.
    APOLLO_RESULT = "APOLLO_RESULT"
    PLUTUS_RESULT = "PLUTUS_RESULT"


EVIDENCE_LEVEL_IS_DARWIN_PROOF: dict[EvidenceLevel, bool] = {
    EvidenceLevel.SOURCE_CLAIM: False,
    EvidenceLevel.ATHENA_RESULT: False,
    EvidenceLevel.APOLLO_PROOF: True,
    EvidenceLevel.APOLLO_RESULT: False,
    EvidenceLevel.PLUTUS_RESULT: False,
}
