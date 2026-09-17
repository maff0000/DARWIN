"""Build/version identity, exposed via /buildinfo and structured logs (PID-001 §8)."""
from __future__ import annotations

from dataclasses import dataclass

from darwin import __version__ as APP_VERSION
from darwin.core.config import BuildConfig


@dataclass(frozen=True)
class BuildInfo:
    application_version: str
    commit: str
    build_time: str
    environment: str

    def as_dict(self) -> dict:
        return {
            "application_version": self.application_version,
            "commit": self.commit,
            "build_time": self.build_time,
            "environment": self.environment,
        }


def build_info(config: BuildConfig) -> BuildInfo:
    return BuildInfo(
        application_version=APP_VERSION,
        commit=config.commit,
        build_time=config.build_time,
        environment=config.environment,
    )
