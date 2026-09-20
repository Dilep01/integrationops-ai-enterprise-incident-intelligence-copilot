from __future__ import annotations

from typing import Annotated, Never

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from integrationops import __version__
from integrationops.config import get_settings
from integrationops.models import (
    FeedbackRequest,
    FeedbackResponse,
    IncidentReport,
    IncidentRequest,
    InvestigationSummary,
    RemediationAction,
    RemediationAuditEvent,
    RemediationDecisionRequest,
    RemediationRequest,
)
from integrationops.observability import (
    configure_telemetry,
    metrics_snapshot,
    record_security_rejection,
)
from integrationops.persistence import (
    InvestigationRepository,
    SqlAlchemyInvestigationRepository,
)
from integrationops.remediation import (
    RemediationAdapter,
    RemediationConflict,
    RemediationNotFound,
    RemediationPolicyError,
    RemediationTargetError,
    build_remediation_adapter,
)
from integrationops.security import (
    RequestPrincipal,
    SecurityViolation,
    validate_incident_message,
)
from integrationops.workflow import InvestigationWorkflow

TenantHeader = Annotated[str, Header(alias="X-Tenant-ID")]
RolesHeader = Annotated[str, Header(alias="X-Roles")]
UserHeader = Annotated[str, Header(alias="X-User-ID")]
IdempotencyHeader = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=200)
]

VIEW_ROLES = {"incident-viewer", "integration-engineer", "support-engineer", "admin"}
INVESTIGATE_ROLES = {"integration-engineer", "support-engineer", "admin"}
FEEDBACK_ROLES = {"integration-engineer", "support-engineer", "admin"}
REMEDIATION_REQUEST_ROLES = {"integration-engineer", "support-engineer", "admin"}
REMEDIATION_APPROVER_ROLES = {"remediation-approver", "admin"}
REMEDIATION_OPERATOR_ROLES = {"remediation-operator", "admin"}


def request_principal(
    tenant_id: TenantHeader = "demo-enterprise",
    roles_header: RolesHeader = "integration-engineer",
    user_id: UserHeader = "analyst-demo",
) -> RequestPrincipal:
    roles = frozenset(role.strip() for role in roles_header.split(",") if role.strip())
    if not roles:
        raise HTTPException(status_code=403, detail="At least one role is required")
    return RequestPrincipal(tenant_id=tenant_id, roles=roles, user_id=user_id)


Principal = Annotated[RequestPrincipal, Depends(request_principal)]


def require_any_role(principal: RequestPrincipal, allowed: set[str]) -> None:
    if not principal.has_any_role(allowed):
        raise HTTPException(status_code=403, detail="The caller is not authorized for this action")


def raise_remediation_http(exc: Exception) -> Never:
    if isinstance(exc, RemediationNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RemediationConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, RemediationPolicyError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, RemediationTargetError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


def create_app(
    *,
    workflow: InvestigationWorkflow | None = None,
    repository: InvestigationRepository | None = None,
    remediation_adapter: RemediationAdapter | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_telemetry(settings.telemetry_service_name)
    investigation_workflow = workflow or InvestigationWorkflow()
    investigation_repository = repository or SqlAlchemyInvestigationRepository(
        settings.database_url
    )
    action_adapter = remediation_adapter or build_remediation_adapter(settings)

    application = FastAPI(
        title="IntegrationOps AI",
        description="Evidence-grounded enterprise integration incident intelligence",
        version=__version__,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "X-Tenant-ID",
            "X-Roles",
            "X-User-ID",
            "Idempotency-Key",
        ],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "environment": settings.env,
            "llm_provider": settings.llm_provider,
            "retrieval_backend": settings.retrieval_backend,
        }

    @application.get("/api/v1/demo/incidents/auth-401", response_model=IncidentRequest)
    def demo_incident() -> IncidentRequest:
        return IncidentRequest(
            incident_id="INC-DEMO-401",
            message="Payment integration failed with HTTP 401 after token rotation.",
            environment="production",
            integration="invoice-payment",
            correlation_id="corr-payment-20260919-001",
        )

    @application.get("/api/v1/metrics")
    def metrics(principal: Principal) -> dict[str, float | int]:
        require_any_role(principal, VIEW_ROLES)
        return metrics_snapshot()

    @application.post(
        "/api/v1/investigations",
        response_model=IncidentReport,
        status_code=status.HTTP_201_CREATED,
    )
    def investigate(request: IncidentRequest, principal: Principal) -> IncidentReport:
        require_any_role(principal, INVESTIGATE_ROLES)
        try:
            validate_incident_message(request.message)
        except SecurityViolation as exc:
            record_security_rejection()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        authorized_request = request.model_copy(
            update={
                "tenant_id": principal.tenant_id,
                "roles": sorted(principal.roles),
            }
        )
        report = investigation_workflow.investigate(authorized_request)
        investigation_repository.save(authorized_request, report)
        return report

    @application.get(
        "/api/v1/investigations",
        response_model=list[InvestigationSummary],
    )
    def list_investigations(
        principal: Principal,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[InvestigationSummary]:
        require_any_role(principal, VIEW_ROLES)
        return investigation_repository.list(principal.tenant_id, limit)

    @application.get(
        "/api/v1/investigations/{run_id}",
        response_model=IncidentReport,
    )
    def get_investigation(
        run_id: str,
        principal: Principal,
    ) -> IncidentReport:
        require_any_role(principal, VIEW_ROLES)
        report = investigation_repository.get(run_id, principal.tenant_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return report

    @application.post(
        "/api/v1/investigations/{run_id}/feedback",
        response_model=FeedbackResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def add_feedback(
        run_id: str,
        feedback: FeedbackRequest,
        principal: Principal,
    ) -> FeedbackResponse:
        require_any_role(principal, FEEDBACK_ROLES)
        result = investigation_repository.add_feedback(run_id, principal.tenant_id, feedback)
        if result is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return result

    @application.post(
        "/api/v1/investigations/{run_id}/remediation-actions",
        response_model=RemediationAction,
        status_code=status.HTTP_201_CREATED,
    )
    def request_remediation(
        run_id: str,
        request: RemediationRequest,
        principal: Principal,
    ) -> RemediationAction:
        require_any_role(principal, REMEDIATION_REQUEST_ROLES)
        try:
            return investigation_repository.request_remediation(
                run_id,
                principal.tenant_id,
                principal.user_id,
                request,
            )
        except (RemediationNotFound, RemediationPolicyError) as exc:
            raise_remediation_http(exc)

    @application.get(
        "/api/v1/remediation-actions/{action_id}",
        response_model=RemediationAction,
    )
    def get_remediation(action_id: str, principal: Principal) -> RemediationAction:
        require_any_role(principal, VIEW_ROLES | REMEDIATION_APPROVER_ROLES)
        action = investigation_repository.get_remediation(action_id, principal.tenant_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Remediation action not found")
        return action

    @application.post(
        "/api/v1/remediation-actions/{action_id}/decision",
        response_model=RemediationAction,
    )
    def decide_remediation(
        action_id: str,
        decision: RemediationDecisionRequest,
        principal: Principal,
    ) -> RemediationAction:
        require_any_role(principal, REMEDIATION_APPROVER_ROLES)
        try:
            return investigation_repository.decide_remediation(
                action_id,
                principal.tenant_id,
                principal.user_id,
                decision,
            )
        except (
            RemediationNotFound,
            RemediationConflict,
            RemediationPolicyError,
        ) as exc:
            raise_remediation_http(exc)

    @application.post(
        "/api/v1/remediation-actions/{action_id}/execute",
        response_model=RemediationAction,
    )
    def execute_remediation(
        action_id: str,
        idempotency_key: IdempotencyHeader,
        principal: Principal,
    ) -> RemediationAction:
        require_any_role(principal, REMEDIATION_OPERATOR_ROLES)
        try:
            return investigation_repository.execute_remediation(
                action_id,
                principal.tenant_id,
                principal.user_id,
                idempotency_key,
                action_adapter,
            )
        except (
            RemediationNotFound,
            RemediationConflict,
            RemediationPolicyError,
            RemediationTargetError,
        ) as exc:
            raise_remediation_http(exc)

    @application.get(
        "/api/v1/remediation-actions/{action_id}/audit",
        response_model=list[RemediationAuditEvent],
    )
    def remediation_audit(
        action_id: str,
        principal: Principal,
    ) -> list[RemediationAuditEvent]:
        require_any_role(principal, VIEW_ROLES | REMEDIATION_APPROVER_ROLES)
        try:
            return investigation_repository.list_remediation_audit(
                action_id, principal.tenant_id
            )
        except RemediationNotFound as exc:
            raise_remediation_http(exc)

    return application


app = create_app()


def run() -> None:
    uvicorn.run("integrationops.api:app", host="0.0.0.0", port=8000, reload=False)
