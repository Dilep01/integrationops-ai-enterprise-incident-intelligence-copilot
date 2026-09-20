from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

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
    RemediationStatus,
)
from integrationops.remediation import (
    RemediationAdapter,
    RemediationConflict,
    RemediationNotFound,
    RemediationPolicyError,
    RemediationTargetError,
    validate_execution_policy,
)


class Base(DeclarativeBase):
    pass


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(128), index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    classification: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(Text)
    request_json: Mapped[dict] = mapped_column(JSON)
    report_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class FeedbackRecord(Base):
    __tablename__ = "investigation_feedback"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigations.run_id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    corrected_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RemediationActionRecord(Base):
    __tablename__ = "remediation_actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigations.run_id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    action_type: Mapped[str] = mapped_column(String(80))
    transaction_reference: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RemediationAuditRecord(Base):
    __tablename__ = "remediation_audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("remediation_actions.action_id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InvestigationRepository(Protocol):
    def save(self, request: IncidentRequest, report: IncidentReport) -> None: ...

    def get(self, run_id: str, tenant_id: str) -> IncidentReport | None: ...

    def list(self, tenant_id: str, limit: int = 20) -> list[InvestigationSummary]: ...

    def add_feedback(
        self, run_id: str, tenant_id: str, feedback: FeedbackRequest
    ) -> FeedbackResponse | None: ...

    def request_remediation(
        self, run_id: str, tenant_id: str, actor_id: str, request: RemediationRequest
    ) -> RemediationAction: ...

    def get_remediation(self, action_id: str, tenant_id: str) -> RemediationAction | None: ...

    def decide_remediation(
        self,
        action_id: str,
        tenant_id: str,
        actor_id: str,
        decision: RemediationDecisionRequest,
    ) -> RemediationAction: ...

    def execute_remediation(
        self,
        action_id: str,
        tenant_id: str,
        actor_id: str,
        idempotency_key: str,
        adapter: RemediationAdapter,
    ) -> RemediationAction: ...

    def list_remediation_audit(
        self, action_id: str, tenant_id: str
    ) -> list[RemediationAuditEvent]: ...


def _prepare_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url.endswith(":memory:"):
        return
    database_path = Path(database_url.removeprefix(prefix))
    database_path.parent.mkdir(parents=True, exist_ok=True)


class SqlAlchemyInvestigationRepository:
    def __init__(self, database_url: str, *, create_schema: bool = True) -> None:
        _prepare_sqlite_directory(database_url)
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine_options = {"connect_args": connect_args}
        if database_url.endswith(":memory:"):
            engine_options["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **engine_options)
        if create_schema:
            Base.metadata.create_all(self.engine)

    def save(self, request: IncidentRequest, report: IncidentReport) -> None:
        record = InvestigationRecord(
            run_id=report.run_id,
            incident_id=report.incident_id,
            tenant_id=request.tenant_id,
            classification=report.classification.value,
            confidence=report.confidence.value,
            summary=report.summary,
            request_json=request.model_dump(mode="json"),
            report_json=report.model_dump(mode="json"),
            created_at=report.generated_at,
        )
        with Session(self.engine) as session:
            session.merge(record)
            session.commit()

    def get(self, run_id: str, tenant_id: str) -> IncidentReport | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(InvestigationRecord).where(
                    InvestigationRecord.run_id == run_id,
                    InvestigationRecord.tenant_id == tenant_id,
                )
            )
            return IncidentReport.model_validate(record.report_json) if record else None

    def list(self, tenant_id: str, limit: int = 20) -> list[InvestigationSummary]:
        with Session(self.engine) as session:
            records = session.scalars(
                select(InvestigationRecord)
                .where(InvestigationRecord.tenant_id == tenant_id)
                .order_by(InvestigationRecord.created_at.desc())
                .limit(limit)
            ).all()
            return [
                InvestigationSummary(
                    run_id=record.run_id,
                    incident_id=record.incident_id,
                    classification=record.classification,
                    confidence=record.confidence,
                    summary=record.summary,
                    created_at=record.created_at,
                )
                for record in records
            ]

    def add_feedback(
        self, run_id: str, tenant_id: str, feedback: FeedbackRequest
    ) -> FeedbackResponse | None:
        with Session(self.engine) as session:
            investigation_exists = session.scalar(
                select(InvestigationRecord.run_id).where(
                    InvestigationRecord.run_id == run_id,
                    InvestigationRecord.tenant_id == tenant_id,
                )
            )
            if investigation_exists is None:
                return None
            feedback_id = f"FDB-{uuid4().hex[:12].upper()}"
            created_at = datetime.now(UTC)
            session.add(
                FeedbackRecord(
                    feedback_id=feedback_id,
                    run_id=run_id,
                    rating=feedback.rating,
                    corrected_root_cause=feedback.corrected_root_cause,
                    notes=feedback.notes,
                    created_at=created_at,
                )
            )
            session.commit()
            return FeedbackResponse(
                feedback_id=feedback_id,
                run_id=run_id,
                created_at=created_at,
            )

    @staticmethod
    def _to_remediation_action(record: RemediationActionRecord) -> RemediationAction:
        return RemediationAction(
            action_id=record.action_id,
            run_id=record.run_id,
            action_type=record.action_type,
            transaction_reference=record.transaction_reference,
            reason=record.reason,
            status=record.status,
            requested_by=record.requested_by,
            decided_by=record.decided_by,
            decision_notes=record.decision_notes,
            execution_result=record.execution_result,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _audit(
        session: Session,
        *,
        action_id: str,
        tenant_id: str,
        event_type: str,
        actor_id: str,
        details: dict,
    ) -> None:
        session.add(
            RemediationAuditRecord(
                event_id=f"AUD-{uuid4().hex[:12].upper()}",
                action_id=action_id,
                tenant_id=tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                details=details,
                created_at=datetime.now(UTC),
            )
        )

    def request_remediation(
        self,
        run_id: str,
        tenant_id: str,
        actor_id: str,
        request: RemediationRequest,
    ) -> RemediationAction:
        with Session(self.engine) as session:
            investigation = session.scalar(
                select(InvestigationRecord).where(
                    InvestigationRecord.run_id == run_id,
                    InvestigationRecord.tenant_id == tenant_id,
                )
            )
            if investigation is None:
                raise RemediationNotFound("Investigation not found")
            confidence = investigation.report_json.get("confidence")
            classification = investigation.report_json.get("classification")
            citation_valid = investigation.report_json.get("confidence_basis", {}).get(
                "citation_validation_passed"
            )
            if confidence != "high" or not citation_valid:
                raise RemediationPolicyError(
                    "Remediation requires a high-confidence, citation-validated investigation."
                )
            if classification == "duplicate_transaction":
                raise RemediationPolicyError(
                    "Duplicate transactions require ledger reconciliation and cannot be "
                    "automatically reprocessed."
                )
            now = datetime.now(UTC)
            record = RemediationActionRecord(
                action_id=f"ACT-{uuid4().hex[:12].upper()}",
                run_id=run_id,
                tenant_id=tenant_id,
                action_type=request.action_type.value,
                transaction_reference=request.transaction_reference,
                reason=request.reason,
                status=RemediationStatus.PENDING_APPROVAL.value,
                requested_by=actor_id,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                action_id=record.action_id,
                tenant_id=tenant_id,
                event_type="requested",
                actor_id=actor_id,
                details={
                    "action_type": record.action_type,
                    "transaction_reference": record.transaction_reference,
                },
            )
            session.commit()
            session.refresh(record)
            return self._to_remediation_action(record)

    def get_remediation(self, action_id: str, tenant_id: str) -> RemediationAction | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(RemediationActionRecord).where(
                    RemediationActionRecord.action_id == action_id,
                    RemediationActionRecord.tenant_id == tenant_id,
                )
            )
            return self._to_remediation_action(record) if record else None

    def decide_remediation(
        self,
        action_id: str,
        tenant_id: str,
        actor_id: str,
        decision: RemediationDecisionRequest,
    ) -> RemediationAction:
        with Session(self.engine) as session:
            record = session.scalar(
                select(RemediationActionRecord).where(
                    RemediationActionRecord.action_id == action_id,
                    RemediationActionRecord.tenant_id == tenant_id,
                )
            )
            if record is None:
                raise RemediationNotFound("Remediation action not found")
            if record.status != RemediationStatus.PENDING_APPROVAL.value:
                raise RemediationConflict("Only pending actions can be reviewed")
            if record.requested_by == actor_id:
                raise RemediationPolicyError("The requester cannot approve or reject this action")
            record.status = (
                RemediationStatus.APPROVED.value
                if decision.decision == "approve"
                else RemediationStatus.REJECTED.value
            )
            record.decided_by = actor_id
            record.decision_notes = decision.notes
            record.updated_at = datetime.now(UTC)
            self._audit(
                session,
                action_id=action_id,
                tenant_id=tenant_id,
                event_type=decision.decision + "d",
                actor_id=actor_id,
                details={"notes": decision.notes},
            )
            session.commit()
            session.refresh(record)
            return self._to_remediation_action(record)

    def execute_remediation(
        self,
        action_id: str,
        tenant_id: str,
        actor_id: str,
        idempotency_key: str,
        adapter: RemediationAdapter,
    ) -> RemediationAction:
        with Session(self.engine) as session:
            record = session.scalar(
                select(RemediationActionRecord).where(
                    RemediationActionRecord.action_id == action_id,
                    RemediationActionRecord.tenant_id == tenant_id,
                )
            )
            if record is None:
                raise RemediationNotFound("Remediation action not found")
            action = self._to_remediation_action(record)
            validate_execution_policy(action)
            if record.status == RemediationStatus.EXECUTED.value:
                if record.idempotency_key != idempotency_key:
                    raise RemediationConflict(
                        "This action was already executed with another idempotency key"
                    )
                self._audit(
                    session,
                    action_id=action_id,
                    tenant_id=tenant_id,
                    event_type="execution_replayed",
                    actor_id=actor_id,
                    details={"idempotency_key": idempotency_key},
                )
                session.commit()
                return self._to_remediation_action(record)
            if record.status != RemediationStatus.APPROVED.value:
                raise RemediationConflict("Only approved actions can be executed")

            try:
                result = adapter.reprocess_failed_transaction(
                    action_id=action_id,
                    transaction_reference=record.transaction_reference,
                    idempotency_key=idempotency_key,
                    requested_by=actor_id,
                )
            except RemediationTargetError:
                self._audit(
                    session,
                    action_id=action_id,
                    tenant_id=tenant_id,
                    event_type="execution_failed",
                    actor_id=actor_id,
                    details={"reason": "target_system_error"},
                )
                session.commit()
                raise
            record.status = RemediationStatus.EXECUTED.value
            record.idempotency_key = idempotency_key
            record.execution_result = result
            record.updated_at = datetime.now(UTC)
            self._audit(
                session,
                action_id=action_id,
                tenant_id=tenant_id,
                event_type="executed",
                actor_id=actor_id,
                details={
                    "idempotency_key": idempotency_key,
                    "execution_reference": result.get("execution_reference"),
                    "simulated": result.get("simulated", False),
                },
            )
            session.commit()
            session.refresh(record)
            return self._to_remediation_action(record)

    def list_remediation_audit(
        self, action_id: str, tenant_id: str
    ) -> list[RemediationAuditEvent]:
        with Session(self.engine) as session:
            action_exists = session.scalar(
                select(RemediationActionRecord.action_id).where(
                    RemediationActionRecord.action_id == action_id,
                    RemediationActionRecord.tenant_id == tenant_id,
                )
            )
            if action_exists is None:
                raise RemediationNotFound("Remediation action not found")
            records = session.scalars(
                select(RemediationAuditRecord)
                .where(
                    RemediationAuditRecord.action_id == action_id,
                    RemediationAuditRecord.tenant_id == tenant_id,
                )
                .order_by(RemediationAuditRecord.created_at.asc())
            ).all()
            return [
                RemediationAuditEvent(
                    event_id=record.event_id,
                    action_id=record.action_id,
                    event_type=record.event_type,
                    actor_id=record.actor_id,
                    details=record.details,
                    created_at=record.created_at,
                )
                for record in records
            ]
