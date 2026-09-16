"""Shared API error conventions. No raw exception/credential disclosure (PID-001 §29)."""
from __future__ import annotations


class DarwinError(Exception):
    """Base class for all DARWIN domain errors."""

    code: str = "DARWIN_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class NotReadyError(DarwinError):
    code = "NOT_READY"


class ConfigurationError(DarwinError):
    code = "CONFIGURATION_ERROR"


class HermesContractViolation(DarwinError):
    """A row or query result violates the canonical HERMES contract (PID-001 §14)."""

    code = "HERMES_CONTRACT_VIOLATION"


class HermesUnavailableError(DarwinError):
    """HERMES could not be reached. Must never be treated as a HERMES fault to repair."""

    code = "HERMES_UNAVAILABLE"


class InvalidRequestError(DarwinError):
    code = "INVALID_REQUEST"


def to_error_response(exc: DarwinError) -> dict:
    """Sanitised error body — never includes secrets, stack traces, or connection strings."""
    return {"error": {"code": exc.code, "message": str(exc)}}
