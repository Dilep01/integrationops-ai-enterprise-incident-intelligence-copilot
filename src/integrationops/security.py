from __future__ import annotations

import re
from dataclasses import dataclass


class SecurityViolation(ValueError):
    """Raised when untrusted input attempts to alter the investigation boundary."""


INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions?", re.I),
    re.compile(
        r"(?:reveal|show|print|return)\s+(?:the\s+)?(?:system\s+prompt|api\s*key|secret)",
        re.I,
    ),
    re.compile(r"(?:act|behave)\s+as\s+(?:an?\s+)?(?:administrator|system)", re.I),
)

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|client[_-]?secret|password)\s*[=:]\s*)\S+"),
)


@dataclass(frozen=True)
class RequestPrincipal:
    tenant_id: str
    roles: frozenset[str]
    user_id: str = "anonymous"

    def has_any_role(self, allowed: set[str]) -> bool:
        return bool(self.roles.intersection(allowed))


def validate_incident_message(message: str) -> None:
    if any(pattern.search(message) for pattern in INJECTION_PATTERNS):
        raise SecurityViolation(
            "The incident message contains instruction-like content and was rejected."
        )


def sanitize_untrusted_text(value: str) -> str:
    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    lines = [
        "[UNTRUSTED INSTRUCTION REMOVED]"
        if any(pattern.search(line) for pattern in INJECTION_PATTERNS)
        else line
        for line in sanitized.splitlines()
    ]
    return "\n".join(lines)
