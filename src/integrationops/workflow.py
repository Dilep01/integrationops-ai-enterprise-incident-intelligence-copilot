from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from integrationops.checkpoints import create_sqlite_checkpointer
from integrationops.config import get_settings
from integrationops.diagnosis import (
    ActionSafetyPolicy,
    DiagnosisEngine,
    DiagnosisError,
    EvidenceSufficiencyPolicy,
    build_diagnosis_engine,
)
from integrationops.hybrid_retrieval import build_demo_hybrid_retriever
from integrationops.models import (
    ConfidenceBasis,
    ConfidenceLevel,
    DiagnosisResult,
    Evidence,
    EvidenceSourceType,
    IncidentClassification,
    IncidentReport,
    IncidentRequest,
    IncidentTimelineEvent,
    NormalizedIncident,
    ToolResult,
)
from integrationops.observability import investigation_span
from integrationops.retrieval import KnowledgeRetriever
from integrationops.tools import MockOperationsTools


class InvestigationState(TypedDict, total=False):
    request: IncidentRequest
    run_id: str
    incident: NormalizedIncident
    document_evidence: list[Evidence]
    tool_results: list[ToolResult]
    evidence: list[Evidence]
    diagnosis: DiagnosisResult
    citations_valid: bool
    report: IncidentReport


def _default_knowledge_dir() -> Path:
    configured = Path(get_settings().knowledge_dir)
    if configured.is_absolute():
        return configured
    project_relative = Path.cwd() / configured
    if project_relative.exists():
        return project_relative
    return Path(__file__).resolve().parents[2] / configured


class InvestigationWorkflow:
    def __init__(
        self,
        retriever: KnowledgeRetriever | None = None,
        tools: MockOperationsTools | None = None,
        diagnosis_engine: DiagnosisEngine | None = None,
        sufficiency_policy: EvidenceSufficiencyPolicy | None = None,
        action_safety_policy: ActionSafetyPolicy | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self.retriever = retriever or build_demo_hybrid_retriever(_default_knowledge_dir())
        self.tools = tools or MockOperationsTools()
        self.diagnosis_engine = diagnosis_engine or build_diagnosis_engine(get_settings())
        self.sufficiency_policy = sufficiency_policy or EvidenceSufficiencyPolicy()
        self.action_safety_policy = action_safety_policy or ActionSafetyPolicy()
        self.checkpointer = checkpointer or create_sqlite_checkpointer(
            get_settings().checkpoint_path
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(InvestigationState)
        builder.add_node("normalize", self._normalize)
        builder.add_node("retrieve_knowledge", self._retrieve_knowledge)
        builder.add_node("collect_operations", self._collect_operations)
        builder.add_node("diagnose", self._diagnose)
        builder.add_node("validate_citations", self._validate_citations)
        builder.add_node("compose_report", self._compose_report)

        builder.add_edge(START, "normalize")
        builder.add_edge("normalize", "retrieve_knowledge")
        builder.add_edge("retrieve_knowledge", "collect_operations")
        builder.add_edge("collect_operations", "diagnose")
        builder.add_edge("diagnose", "validate_citations")
        builder.add_edge("validate_citations", "compose_report")
        builder.add_edge("compose_report", END)
        return builder.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _normalize(state: InvestigationState) -> dict:
        request = state["request"]
        message_lower = request.message.lower()
        classification = IncidentClassification.UNKNOWN
        if any(term in message_lower for term in ("duplicate", "already processed", "idempotency")):
            classification = IncidentClassification.DUPLICATE_TRANSACTION
        elif "401" in message_lower or "oauth" in message_lower or "token" in message_lower:
            classification = IncidentClassification.AUTHENTICATION_FAILURE
        elif any(term in message_lower for term in ("timeout", "timed out", "504", "latency")):
            classification = IncidentClassification.TIMEOUT
        elif any(term in message_lower for term in ("mapping", "transformation", "map field")):
            classification = IncidentClassification.MAPPING_ERROR
        elif any(
            term in message_lower
            for term in ("invalid payload", "malformed", "missing required", "http 400", "422")
        ):
            classification = IncidentClassification.INVALID_PAYLOAD
        incident_id = request.incident_id or f"INC-DEMO-{uuid4().hex[:6].upper()}"
        return {
            "run_id": state.get("run_id", f"RUN-{uuid4().hex[:10].upper()}"),
            "incident": NormalizedIncident(
                incident_id=incident_id,
                message=request.message,
                environment=request.environment,
                integration=request.integration,
                correlation_id=request.correlation_id,
                classification=classification,
            ),
        }

    def _retrieve_knowledge(self, state: InvestigationState) -> dict:
        incident = state["incident"]
        evidence = self.retriever.retrieve(
            incident.message,
            environment=incident.environment,
            tenant_id=state["request"].tenant_id,
            roles=state["request"].roles,
            limit=3,
        )
        return {"document_evidence": evidence}

    def _collect_operations(self, state: InvestigationState) -> dict:
        results = self.tools.collect_all(state["incident"])
        operational_evidence = [
            evidence for result in results if result.succeeded for evidence in result.evidence
        ]
        return {
            "tool_results": results,
            "evidence": [*state.get("document_evidence", []), *operational_evidence],
        }

    def _diagnose(self, state: InvestigationState) -> dict:
        incident = state["incident"]
        evidence = state.get("evidence", [])
        sufficient, missing = self.sufficiency_policy.assess(evidence)
        if not sufficient:
            diagnosis = DiagnosisResult(
                summary="The investigation stopped because the evidence gate did not pass.",
                hypotheses=[],
                recommended_actions=[
                    "Collect the missing authorized evidence and investigate again."
                ],
                missing_information=missing,
                generation=self.diagnosis_engine.generation,
            )
        else:
            try:
                diagnosis = self.diagnosis_engine.diagnose(incident, evidence)
            except DiagnosisError as exc:
                diagnosis = DiagnosisResult(
                    summary="The diagnosis model failed safely without producing a conclusion.",
                    hypotheses=[],
                    recommended_actions=[
                        "Review the evidence manually or retry with an approved model endpoint."
                    ],
                    missing_information=[str(exc)],
                    generation=self.diagnosis_engine.generation,
                )
        guarded_actions = self.action_safety_policy.guard(diagnosis.recommended_actions)
        return {"diagnosis": diagnosis.model_copy(update={"recommended_actions": guarded_actions})}

    @staticmethod
    def _validate_citations(state: InvestigationState) -> dict:
        available = {item.evidence_id for item in state.get("evidence", [])}
        diagnosis = state["diagnosis"]
        referenced = {
            evidence_id
            for hypothesis in diagnosis.hypotheses
            for evidence_id in (
                hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
            )
        }
        return {"citations_valid": bool(referenced) and referenced.issubset(available)}

    @staticmethod
    def _compose_report(state: InvestigationState) -> dict:
        incident = state["incident"]
        evidence = state.get("evidence", [])
        diagnosis = state["diagnosis"]
        hypotheses = diagnosis.hypotheses
        source_types = {item.source_type for item in evidence}
        operational_confirmation = any(
            item.source_type == EvidenceSourceType.CONFIGURATION for item in evidence
        ) and any(item.source_type == EvidenceSourceType.LOG for item in evidence)
        citations_valid = state.get("citations_valid", False)
        supported = [item for item in hypotheses if item.status == "supported"]

        if supported and len(source_types) >= 4 and operational_confirmation and citations_valid:
            confidence = ConfidenceLevel.HIGH
            confidence_explanation = (
                "The leading cause is supported by matching operational signals, authorized "
                "documentation, and a confirmed historical incident."
            )
        elif supported and citations_valid:
            confidence = ConfidenceLevel.MEDIUM
            confidence_explanation = "The leading hypothesis is cited but lacks broad confirmation."
        else:
            confidence = ConfidenceLevel.INSUFFICIENT
            confidence_explanation = (
                "The available evidence is insufficient for a supported diagnosis."
            )

        timeline = [
            IncidentTimelineEvent(
                event_id=item.evidence_id,
                title=item.title,
                source_type=item.source_type,
                occurred_at=item.occurred_at,
                details=item.excerpt,
            )
            for item in sorted(
                (entry for entry in evidence if entry.occurred_at is not None),
                key=lambda entry: entry.occurred_at,
            )
        ]
        report = IncidentReport(
            run_id=state["run_id"],
            incident_id=incident.incident_id,
            classification=incident.classification,
            summary=diagnosis.summary,
            ranked_hypotheses=sorted(hypotheses, key=lambda item: item.score, reverse=True),
            recommended_actions=diagnosis.recommended_actions,
            missing_information=diagnosis.missing_information,
            confidence=confidence,
            confidence_basis=ConfidenceBasis(
                source_type_count=len(source_types),
                independent_source_agreement=len(source_types) >= 3,
                operational_confirmation=operational_confirmation,
                contradictory_evidence_count=sum(
                    len(item.contradicting_evidence_ids) for item in supported
                ),
                citation_validation_passed=citations_valid,
                explanation=confidence_explanation,
            ),
            evidence=evidence,
            timeline=timeline,
            generation=diagnosis.generation,
        )
        return {"report": report}

    def investigate(self, request: IncidentRequest) -> IncidentReport:
        run_id = f"RUN-{uuid4().hex[:10].upper()}"
        with investigation_span(
            {
                "integrationops.run_id": run_id,
                "integrationops.tenant_id": request.tenant_id,
                "integrationops.environment": request.environment,
                "integrationops.integration": request.integration,
            }
        ):
            final_state = self.graph.invoke(
                {"request": request, "run_id": run_id},
                config={"configurable": {"thread_id": run_id}},
            )
        return final_state["report"]
