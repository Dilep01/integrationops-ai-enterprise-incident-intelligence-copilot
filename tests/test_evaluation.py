from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from integrationops.evaluation import (
    DiagnosisEvaluationResult,
    QualityGateError,
    RetrievalEvaluationResult,
    enforce_quality_gates,
    evaluate_diagnosis,
)
from integrationops.workflow import InvestigationWorkflow


def test_diagnosis_evaluation_reports_grounding_metrics() -> None:
    root = Path(__file__).parents[1]
    result = evaluate_diagnosis(
        root / "data" / "evaluation" / "diagnosis_cases.jsonl",
        workflow=InvestigationWorkflow(checkpointer=InMemorySaver()),
    )

    assert result.case_count == 16
    assert result.classification_accuracy == 1.0
    assert result.answer_relevance == 1.0
    assert result.faithfulness == 1.0
    assert result.groundedness == 1.0
    assert result.citation_correctness == 1.0
    assert result.hallucination_rate == 0.0
    assert result.average_latency_ms > 0
    assert result.estimated_cost_per_query_usd == 0.0


def _passing_retrieval() -> RetrievalEvaluationResult:
    return RetrievalEvaluationResult(
        case_count=10,
        recall_at_k=1.0,
        mean_reciprocal_rank=0.9,
        access_control_failures=0,
        source_diversity=1.0,
        duplicate_result_rate=0.0,
    )


def _passing_diagnosis() -> DiagnosisEvaluationResult:
    return DiagnosisEvaluationResult(
        case_count=16,
        classification_accuracy=1.0,
        answer_relevance=1.0,
        faithfulness=1.0,
        groundedness=1.0,
        citation_correctness=1.0,
        hallucination_rate=0.0,
        average_latency_ms=20.0,
        p95_latency_ms=40.0,
        estimated_cost_per_query_usd=0.0,
    )


def test_quality_gates_accept_expected_metrics() -> None:
    enforce_quality_gates(_passing_retrieval(), _passing_diagnosis())


def test_quality_gates_reject_retrieval_and_hallucination_regressions() -> None:
    retrieval = _passing_retrieval()
    retrieval = RetrievalEvaluationResult(
        **{**retrieval.__dict__, "recall_at_k": 0.5, "duplicate_result_rate": 0.2}
    )
    diagnosis = _passing_diagnosis()
    diagnosis = DiagnosisEvaluationResult(
        **{**diagnosis.__dict__, "hallucination_rate": 0.1}
    )

    with pytest.raises(QualityGateError, match="recall_at_k"):
        enforce_quality_gates(retrieval, diagnosis)
