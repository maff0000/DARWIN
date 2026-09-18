"""PID-004B Strategy Workshop (docs/pids/PID-004-SPECIFICATION-WORKSHOP.md
sec45-sec56).

The ARENA/human (and, in a later PID, MENDEL) authoring layer wrapped
around the already-accepted PID-004A domain model (`darwin.specification`)
and finalisation transaction
(`darwin.research_store.specification_finalisation`). This package never
redefines SpecificationDraft/StrategyVersion semantics, never reimplements
validation/finalisation, and never gives FastAPI a generic "run a command"
or "read/write an arbitrary path" capability (PID-004 sec48).
"""
from __future__ import annotations
