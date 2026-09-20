import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from integration_runtime.api import RuntimeSettings, RuntimeStore, create_app
from integrationops.config import Settings
from integrationops.remediation import (
    HttpRemediationAdapter,
    RemediationTargetError,
    SandboxRemediationAdapter,
    build_remediation_adapter,
)


def _runtime_client() -> TestClient:
    return TestClient(
        create_app(
            settings=RuntimeSettings(api_key=SecretStr("test-runtime-key")),
            store=RuntimeStore(),
        )
    )


def test_runtime_requires_authentication_and_enforces_idempotency() -> None:
    client = _runtime_client()
    url = "/v1/transactions/TXN-100/reprocess"
    body = {"action_id": "ACT-100", "requested_by": "operator-1"}

    unauthorized = client.post(
        url,
        headers={"X-API-Key": "wrong-key", "Idempotency-Key": "retry-TXN-100"},
        json=body,
    )
    assert unauthorized.status_code == 401

    headers = {
        "X-API-Key": "test-runtime-key",
        "Idempotency-Key": "retry-TXN-100",
    }
    first = client.post(url, headers=headers, json=body)
    replay = client.post(url, headers=headers, json=body)

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()
    assert first.json()["simulated"] is True

    executions = client.get(
        "/v1/transactions/TXN-100/executions",
        headers={"X-API-Key": "test-runtime-key"},
    )
    assert len(executions.json()) == 1


def test_runtime_supports_controlled_server_failure() -> None:
    response = _runtime_client().post(
        "/v1/transactions/TXN-500/reprocess",
        headers={
            "X-API-Key": "test-runtime-key",
            "Idempotency-Key": "retry-TXN-500",
            "X-Simulate-Failure": "server_error",
        },
        json={"action_id": "ACT-500", "requested_by": "operator-1"},
    )
    assert response.status_code == 500


def test_http_adapter_sends_contract_and_parses_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "adapter-key"
        assert request.headers["idempotency-key"] == "idem-123456"
        assert request.url.path.endswith("/TXN-200/reprocess")
        return httpx.Response(
            202,
            json={
                "execution_reference": "IRT-000001-TXN-200",
                "transaction_reference": "TXN-200",
                "idempotency_key": "idem-123456",
                "outcome": "accepted_for_reprocessing",
                "simulated": True,
            },
        )

    adapter = HttpRemediationAdapter(
        base_url="http://runtime.test",
        api_key="adapter-key",
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    result = adapter.reprocess_failed_transaction(
        action_id="ACT-200",
        transaction_reference="TXN-200",
        idempotency_key="idem-123456",
        requested_by="operator-1",
    )
    assert result["execution_reference"] == "IRT-000001-TXN-200"


@pytest.mark.parametrize("failure", ["server_error", "timeout"])
def test_http_adapter_retries_transient_failures(failure: str) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("simulated timeout", request=request)
        return httpx.Response(500, json={"detail": "simulated failure"})

    adapter = HttpRemediationAdapter(
        base_url="http://runtime.test",
        api_key="adapter-key",
        max_attempts=3,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RemediationTargetError, match="after 3 attempts"):
        adapter.reprocess_failed_transaction(
            action_id="ACT-500",
            transaction_reference="TXN-500",
            idempotency_key="idem-500000",
            requested_by="operator-1",
        )
    assert attempts == 3


def test_http_adapter_does_not_retry_invalid_credentials() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"detail": "invalid key"})

    adapter = HttpRemediationAdapter(
        base_url="http://runtime.test",
        api_key="bad-key",
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RemediationTargetError, match="credentials"):
        adapter.reprocess_failed_transaction(
            action_id="ACT-401",
            transaction_reference="TXN-401",
            idempotency_key="idem-401000",
            requested_by="operator-1",
        )
    assert attempts == 1


def test_adapter_factory_keeps_sandbox_default_and_requires_http_key() -> None:
    assert isinstance(build_remediation_adapter(Settings()), SandboxRemediationAdapter)

    with pytest.raises(ValueError, match="API key"):
        build_remediation_adapter(
            Settings(
                remediation_provider="local_http",
                remediation_api_key=None,
            )
        )
