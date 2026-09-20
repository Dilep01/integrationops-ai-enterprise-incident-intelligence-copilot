from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class EvidenceSourceType(StrEnum):
    DOCUMENT = "document"
    LOG = "log"
    SERVICE_STATUS = "service_status"
    INCIDENT = "incident"
    CONFIGURATION = "configuration"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class IncidentClassification(StrEnum):
    AUTHENTICATION_FAILURE = "authentication_failure"
    TIMEOUT = "timeout"
    MAPPING_ERROR = "mapping_error"
    INVALID_PAYLOAD = "invalid_payload"
    DUPLICATE_TRANSACTION = "duplicate_transaction"
    UNKNOWN = "unknown"


class RemediationActionType(StrEnum):
    REPROCESS_FAILED_TRANSACTION = "reprocess_failed_transaction"


class RemediationStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class IncidentRequest(BaseModel):
    message: str = Field(min_length=5, max_length=4000)
    environment: str = Field(default="production", min_length=2, max_length=50)
    integration: str = Field(default="invoice-payment", min_length=2, max_length=100)
    incident_id: str | None = None
    correlation_id: str | None = None
    tenant_id: str = Field(default="demo-enterprise", min_length=2, max_length=100)
    roles: list[str] = Field(
        default_factory=lambda: ["integration-engineer"], min_length=1, max_length=20
    )


class NormalizedIncident(BaseModel):
    incident_id: str
    message: str
    environment: str
    integration: str
    correlation_id: str | None = None
    classification: IncidentClassification = IncidentClassification.UNKNOWN
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"EVD-{uuid4().hex[:10].upper()}")
    source_type: EvidenceSourceType
    source_id: str
    title: str
    excerpt: str = Field(min_length=1)
    reliability: float = Field(ge=0.0, le=1.0)
    occurred_at: datetime | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: str
    query_id: str
    succeeded: bool
    evidence: list[Evidence] = Field(default_factory=list)
    error: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Hypothesis(BaseModel):
    title: str
    explanation: str
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0)
    status: Literal["supported", "possible", "rejected"]


class ConfidenceBasis(BaseModel):
    source_type_count: int = Field(ge=0)
    independent_source_agreement: bool
    operational_confirmation: bool
    contradictory_evidence_count: int = Field(ge=0)
    citation_validation_passed: bool
    explanation: str


class GenerationMetadata(BaseModel):
    provider: str
    model: str
    prompt_version: str


class DiagnosisResult(BaseModel):
    summary: str
    hypotheses: list[Hypothesis]
    recommended_actions: list[str]
    missing_information: list[str] = Field(default_factory=list)
    generation: GenerationMetadata


class IncidentReport(BaseModel):
    run_id: str
    incident_id: str
    classification: IncidentClassification
    summary: str
    ranked_hypotheses: list[Hypothesis]
    recommended_actions: list[str]
    missing_information: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    confidence_basis: ConfidenceBasis
    evidence: list[Evidence]
    timeline: list[IncidentTimelineEvent] = Field(default_factory=list)
    generation: GenerationMetadata
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    read_only: bool = True

    @model_validator(mode="after")
    def validate_evidence_references(self) -> IncidentReport:
        available = {item.evidence_id for item in self.evidence}
        referenced = {
            evidence_id
            for hypothesis in self.ranked_hypotheses
            for evidence_id in (
                hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
            )
        }
        missing = referenced - available
        if missing:
            raise ValueError(f"Hypotheses reference missing evidence: {sorted(missing)}")
        return self


class IncidentTimelineEvent(BaseModel):
    event_id: str
    title: str
    source_type: EvidenceSourceType
    occurred_at: datetime
    details: str


class InvestigationSummary(BaseModel):
    run_id: str
    incident_id: str
    classification: IncidentClassification
    confidence: ConfidenceLevel
    summary: str
    created_at: datetime


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    corrected_root_cause: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class FeedbackResponse(BaseModel):
    feedback_id: str
    run_id: str
    created_at: datetime


class RemediationRequest(BaseModel):
    action_type: RemediationActionType = RemediationActionType.REPROCESS_FAILED_TRANSACTION
    transaction_reference: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=10, max_length=2000)


class RemediationDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str = Field(min_length=3, max_length=2000)


class RemediationAction(BaseModel):
    action_id: str
    run_id: str
    action_type: RemediationActionType
    transaction_reference: str
    reason: str
    status: RemediationStatus
    requested_by: str
    decided_by: str | None = None
    decision_notes: str | None = None
    execution_result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class RemediationAuditEvent(BaseModel):
    event_id: str
    action_id: str
    event_type: str
    actor_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
