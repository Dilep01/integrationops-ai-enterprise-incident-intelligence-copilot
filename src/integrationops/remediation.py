from __future__ import annotations

from hashlib import sha256
from time import sleep
from typing import Any, Protocol

import httpx

from integrationops.config import Settings
from integrationops.models import RemediationAction


class RemediationError(RuntimeError):
    pass


class RemediationNotFound(RemediationError):
    pass


class RemediationConflict(RemediationError):
    pass


class RemediationPolicyError(RemediationError):
    pass


class RemediationTargetError(RemediationError):
    pass


class RemediationAdapter(Protocol):
    def reprocess_failed_transaction(
        self,
        *,
        action_id: str,
        transaction_reference: str,
        idempotency_key: str,
        requested_by: str,
    ) -> dict[str, Any]: ...


class SandboxRemediationAdapter:
    """Safe local adapter. It never calls an external integration endpoint."""

    def reprocess_failed_transaction(
        self,
        *,
        action_id: str,
        transaction_reference: str,
        idempotency_key: str,
        requested_by: str,
    ) -> dict[str, Any]:
        del action_id, requested_by
        digest = sha256(
            f"{transaction_reference}:{idempotency_key}".encode()
        ).hexdigest()[:12].upper()
        return {
            "execution_reference": f"SIM-{digest}",
            "transaction_reference": transaction_reference,
            "idempotency_key": idempotency_key,
            "outcome": "accepted_for_simulated_reprocessing",
            "simulated": True,
        }


class HttpRemediationAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 2.0,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.05,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def reprocess_failed_transaction(
        self,
        *,
        action_id: str,
        transaction_reference: str,
        idempotency_key: str,
        requested_by: str,
    ) -> dict[str, Any]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.post(
                    f"{self.base_url}/v1/transactions/{transaction_reference}/reprocess",
                    headers={
                        "X-API-Key": self.api_key,
                        "Idempotency-Key": idempotency_key,
                    },
                    json={"action_id": action_id, "requested_by": requested_by},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self.max_attempts:
                    raise RemediationTargetError(
                        f"Target system was unavailable after {self.max_attempts} attempts."
                    ) from exc
                sleep(self.retry_backoff_seconds * attempt)
                continue

            if response.status_code == 401:
                raise RemediationTargetError("Target system rejected remediation credentials.")
            if response.status_code >= 500:
                if attempt == self.max_attempts:
                    raise RemediationTargetError(
                        f"Target system failed after {self.max_attempts} attempts."
                    )
                sleep(self.retry_backoff_seconds * attempt)
                continue
            try:
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RemediationTargetError("Target system returned an invalid response.") from exc
            required = {"execution_reference", "transaction_reference", "idempotency_key"}
            if not isinstance(payload, dict) or not required.issubset(payload):
                raise RemediationTargetError("Target system returned an incomplete response.")
            return payload
        raise RemediationTargetError("Target system request did not complete.")


def build_remediation_adapter(settings: Settings) -> RemediationAdapter:
    if settings.remediation_provider == "sandbox":
        return SandboxRemediationAdapter()
    if settings.remediation_provider == "local_http":
        if settings.remediation_api_key is None:
            raise ValueError("A remediation API key is required for the local HTTP provider.")
        return HttpRemediationAdapter(
            base_url=settings.remediation_base_url,
            api_key=settings.remediation_api_key.get_secret_value(),
            timeout_seconds=settings.remediation_timeout_seconds,
            max_attempts=settings.remediation_max_attempts,
        )
    raise ValueError(f"Unsupported remediation provider: {settings.remediation_provider}")


def validate_execution_policy(action: RemediationAction) -> None:
    if action.action_type.value != "reprocess_failed_transaction":
        raise RemediationPolicyError("The requested remediation action is not allow-listed.")
