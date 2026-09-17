"""Health/readiness aggregation (PID-001 §10).

/health: is the process alive and internally functioning.
/ready: can DARWIN perform Foundation responsibilities right now.
Readiness must never execute large historical queries — only lightweight checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComponentStatus(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: ComponentStatus
    detail: str = ""
    # Whether this component's status can prevent overall readiness.
    # Blocking components (postgres, migrations) are DARWIN's own internal
    # control-plane preconditions -- if not OK, Foundation cannot correctly
    # serve its own endpoints. Non-blocking components (the HERMES adapter)
    # are external systems DARWIN cannot control; PID-001 §10 requires their
    # unavailability to degrade historical-work readiness without blocking
    # Foundation's own control-plane, so they never flip overall readiness.
    blocking: bool = True

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status.value, "detail": self.detail}


@dataclass(frozen=True)
class ReadinessReport:
    components: tuple[ComponentHealth, ...]

    @property
    def ready(self) -> bool:
        # Foundation is "ready" only if every BLOCKING component is fully OK.
        # A blocking component that is merely DEGRADED (e.g. Postgres migrations
        # pending) still means Foundation's own control-plane endpoints cannot
        # correctly serve requests, so DEGRADED must not be treated as good enough
        # for a blocking component -- only OK is. Non-blocking components (e.g.
        # the HERMES adapter) never affect this regardless of their status: HERMES
        # being unreachable degrades historical-work readiness specifically (see
        # PID-001 §10) but must not block Foundation's own control-plane.
        return all(
            c.status == ComponentStatus.OK
            for c in self.components
            if c.blocking
        )

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "components": [c.as_dict() for c in self.components],
        }
