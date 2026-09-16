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

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status.value, "detail": self.detail}


@dataclass(frozen=True)
class ReadinessReport:
    components: tuple[ComponentHealth, ...]

    @property
    def ready(self) -> bool:
        # Foundation is "ready" only if nothing required is DOWN. HERMES being
        # DEGRADED (unreachable) degrades historical-work readiness but must not
        # crash the process or block Foundation's own control-plane responsibilities.
        return all(c.status != ComponentStatus.DOWN for c in self.components)

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "components": [c.as_dict() for c in self.components],
        }
