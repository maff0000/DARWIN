"""Structured logging. UTC timestamps, no secrets, correlation-friendly fields (PID-001 §9)."""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_REDACT_KEYS = {"password", "secret", "token", "credential", "authorization"}


def _redact(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        k: ("<redacted>" if any(bad in k.lower() for bad in _REDACT_KEYS) else v)
        for k, v in fields.items()
    }


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, build_commit: str) -> None:
        super().__init__()
        self.service = service
        self.build_commit = build_commit

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp_utc": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "build_commit": self.build_commit,
            "event": record.getMessage(),
            "logger": record.name,
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(_redact(extra))
        if record.exc_info:
            payload["error_class"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str)


def configure_logging(level: str, build_commit: str, service: str = "darwin_core") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter(service=service, build_commit=build_commit))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})
