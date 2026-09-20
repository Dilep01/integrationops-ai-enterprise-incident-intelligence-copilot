from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from secrets import compare_digest
from threading import Lock
from time import sleep
from typing import Annotated, Literal

import uvicorn
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTEGRATION_RUNTIME_",
        env_file=".env",
        extra="ignore",
    )

    api_key: SecretStr = SecretStr("local-demo-key")
    timeout_simulation_seconds: float = 2.0


class ReprocessRequest(BaseModel):
    action_id: str = Field(min_length=5, max_length=64)
    requested_by: str = Field(min_length=2, max_length=128)


class ReprocessResult(BaseModel):
    execution_reference: str
    action_id: str
    requested_by: str
    transaction_reference: str
    idempotency_key: str
    outcome: str = "accepted_for_reprocessing"
    target_system: str = "integration-runtime-simulator"
    simulated: bool = True
    accepted_at: datetime


class RuntimeStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._executions: dict[tuple[str, str], ReprocessResult] = {}

    def reprocess(
        self,
        transaction_reference: str,
        idempotency_key: str,
        request: ReprocessRequest,
    ) -> ReprocessResult:
        key = (transaction_reference, idempotency_key)
        with self._lock:
            existing = self._executions.get(key)
            if existing:
                return existing
            digest = sha256(
                f"{transaction_reference}:{idempotency_key}".encode()
            ).hexdigest()[:10].upper()
            result = ReprocessResult(
                execution_reference=f"IRT-{digest}",
                action_id=request.action_id,
                requested_by=request.requested_by,
                transaction_reference=transaction_reference,
                idempotency_key=idempotency_key,
                accepted_at=datetime.now(UTC),
            )
            self._executions[key] = result
            return result

    def find(self, transaction_reference: str) -> list[ReprocessResult]:
        with self._lock:
            return [
                result
                for (reference, _), result in self._executions.items()
                if reference == transaction_reference
            ]


ApiKeyHeader = Annotated[str, Header(alias="X-API-Key")]
IdempotencyHeader = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=200)
]
FailureHeader = Annotated[
    Literal["none", "server_error", "timeout"],
    Header(alias="X-Simulate-Failure"),
]


def create_app(
    *,
    settings: RuntimeSettings | None = None,
    store: RuntimeStore | None = None,
) -> FastAPI:
    runtime_settings = settings or RuntimeSettings()
    runtime_store = store or RuntimeStore()
    application = FastAPI(
        title="Integration Runtime Simulator",
        description="Local target for approval-gated IntegrationOps remediation",
        version="1.0.0",
    )

    def authorize(api_key: str) -> None:
        expected = runtime_settings.api_key.get_secret_value()
        if not compare_digest(api_key, expected):
            raise HTTPException(status_code=401, detail="Invalid runtime API key")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "integration-runtime-simulator"}

    @application.post(
        "/v1/transactions/{transaction_reference}/reprocess",
        response_model=ReprocessResult,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def reprocess(
        transaction_reference: str,
        request: ReprocessRequest,
        api_key: ApiKeyHeader,
        idempotency_key: IdempotencyHeader,
        simulate_failure: FailureHeader = "none",
    ) -> ReprocessResult:
        authorize(api_key)
        if simulate_failure == "server_error":
            raise HTTPException(status_code=500, detail="Simulated runtime failure")
        if simulate_failure == "timeout":
            sleep(runtime_settings.timeout_simulation_seconds)
        return runtime_store.reprocess(transaction_reference, idempotency_key, request)

    @application.get(
        "/v1/transactions/{transaction_reference}/executions",
        response_model=list[ReprocessResult],
    )
    def executions(
        transaction_reference: str,
        api_key: ApiKeyHeader,
    ) -> list[ReprocessResult]:
        authorize(api_key)
        return runtime_store.find(transaction_reference)

    return application


app = create_app()


def run() -> None:
    uvicorn.run("integration_runtime.api:app", host="0.0.0.0", port=8081, reload=False)
