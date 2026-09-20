from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter

from langgraph.checkpoint.memory import InMemorySaver

from integrationops.hybrid_retrieval import build_demo_hybrid_retriever
from integrationops.models import IncidentRequest
from integrationops.retrieval import KnowledgeRetriever
from integrationops.workflow import InvestigationWorkflow


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    case_count: int
    recall_at_k: float
    mean_reciprocal_rank: float
    access_control_failures: int
    source_diversity: float
    duplicate_result_rate: float


@dataclass(frozen=True)
class DiagnosisEvaluationResult:
    case_count: int
    classification_accuracy: float
    answer_relevance: float
    faithfulness: float
    groundedness: float
    citation_correctness: float
    hallucination_rate: float
    average_latency_ms: float
    p95_latency_ms: float
    estimated_cost_per_query_usd: float


class QualityGateError(RuntimeError):
    """Raised when an offline evaluation falls below an enforced threshold."""


def evaluate_retrieval(
    dataset_path: Path,
    knowledge_dir: Path,
    retriever: KnowledgeRetriever | None = None,
) -> RetrievalEvaluationResult:
    retriever = retriever or build_demo_hybrid_retriever(knowledge_dir)
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    hits = 0
    reciprocal_rank_total = 0.0
    access_control_failures = 0
    diversity_scores: list[float] = []
    duplicate_results = 0
    total_results = 0
    for case in cases:
        results = retriever.retrieve(
            case["query"],
            environment=case.get("environment", "production"),
            tenant_id=case.get("tenant_id", "demo-enterprise"),
            roles=case.get("roles", ["integration-engineer"]),
            limit=case.get("k", 3),
        )
        returned_ids = [item.metadata.get("document_id") for item in results]
        if results:
            unique_sources = len(set(returned_ids))
            diversity_scores.append(unique_sources / len(results))
            duplicate_results += len(results) - unique_sources
            total_results += len(results)
        expected_ids = set(case.get("expected_document_ids", []))
        if case.get("expect_no_results"):
            if results:
                access_control_failures += 1
            continue
        ranks = [index + 1 for index, item in enumerate(returned_ids) if item in expected_ids]
        if ranks:
            hits += 1
            reciprocal_rank_total += 1.0 / min(ranks)
    scored_cases = sum(1 for case in cases if not case.get("expect_no_results"))
    return RetrievalEvaluationResult(
        case_count=len(cases),
        recall_at_k=hits / scored_cases if scored_cases else 0.0,
        mean_reciprocal_rank=reciprocal_rank_total / scored_cases if scored_cases else 0.0,
        access_control_failures=access_control_failures,
        source_diversity=mean(diversity_scores) if diversity_scores else 1.0,
        duplicate_result_rate=duplicate_results / total_results if total_results else 0.0,
    )


def evaluate_diagnosis(
    dataset_path: Path,
    workflow: InvestigationWorkflow | None = None,
) -> DiagnosisEvaluationResult:
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    workflow = workflow or InvestigationWorkflow(checkpointer=InMemorySaver())
    classification_hits = 0
    relevance_scores: list[float] = []
    faithfulness_scores: list[float] = []
    groundedness_scores: list[float] = []
    citation_scores: list[float] = []
    hallucinated_references = 0
    total_references = 0
    latencies: list[float] = []

    for case in cases:
        started = perf_counter()
        report = workflow.investigate(IncidentRequest(**case["request"]))
        latencies.append((perf_counter() - started) * 1000)

        classification_hits += report.classification.value == case["expected_classification"]
        answer_text = " ".join(
            [
                report.summary,
                *(hypothesis.title for hypothesis in report.ranked_hypotheses),
                *(hypothesis.explanation for hypothesis in report.ranked_hypotheses),
            ]
        ).lower()
        expected_terms = [term.lower() for term in case.get("expected_answer_terms", [])]
        relevance_scores.append(
            sum(term in answer_text for term in expected_terms) / len(expected_terms)
            if expected_terms
            else 1.0
        )

        evidence_ids = {item.evidence_id for item in report.evidence}
        references = [
            evidence_id
            for hypothesis in report.ranked_hypotheses
            for evidence_id in (
                hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
            )
        ]
        invalid_references = [item for item in references if item not in evidence_ids]
        total_references += len(references)
        hallucinated_references += len(invalid_references)
        citation_scores.append(1.0 if not invalid_references else 0.0)
        supported = [
            item for item in report.ranked_hypotheses if item.status == "supported"
        ]
        groundedness_scores.append(
            1.0
            if all(item.supporting_evidence_ids for item in supported)
            and not invalid_references
            else 0.0
        )
        faithfulness_scores.append(
            1.0
            if report.confidence.value == "insufficient"
            or (bool(supported) and report.confidence_basis.citation_validation_passed)
            else 0.0
        )

    sorted_latencies = sorted(latencies)
    p95_index = max(0, min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95)))
    count = len(cases)
    return DiagnosisEvaluationResult(
        case_count=count,
        classification_accuracy=classification_hits / count if count else 0.0,
        answer_relevance=mean(relevance_scores) if relevance_scores else 0.0,
        faithfulness=mean(faithfulness_scores) if faithfulness_scores else 0.0,
        groundedness=mean(groundedness_scores) if groundedness_scores else 0.0,
        citation_correctness=mean(citation_scores) if citation_scores else 0.0,
        hallucination_rate=(
            hallucinated_references / total_references if total_references else 0.0
        ),
        average_latency_ms=round(mean(latencies), 3) if latencies else 0.0,
        p95_latency_ms=round(sorted_latencies[p95_index], 3) if latencies else 0.0,
        estimated_cost_per_query_usd=0.0,
    )


def enforce_quality_gates(
    retrieval: RetrievalEvaluationResult,
    diagnosis: DiagnosisEvaluationResult,
) -> None:
    failures: list[str] = []
    minimums = {
        "retrieval.recall_at_k": (retrieval.recall_at_k, 0.90),
        "retrieval.mean_reciprocal_rank": (retrieval.mean_reciprocal_rank, 0.80),
        "retrieval.source_diversity": (retrieval.source_diversity, 0.90),
        "diagnosis.classification_accuracy": (diagnosis.classification_accuracy, 0.95),
        "diagnosis.answer_relevance": (diagnosis.answer_relevance, 0.90),
        "diagnosis.faithfulness": (diagnosis.faithfulness, 0.95),
        "diagnosis.groundedness": (diagnosis.groundedness, 0.95),
        "diagnosis.citation_correctness": (diagnosis.citation_correctness, 0.95),
    }
    for name, (actual, minimum) in minimums.items():
        if actual < minimum:
            failures.append(f"{name}={actual:.3f} is below {minimum:.3f}")
    if retrieval.access_control_failures:
        failures.append(
            f"retrieval.access_control_failures={retrieval.access_control_failures} must be 0"
        )
    if retrieval.duplicate_result_rate > 0.05:
        failures.append(
            "retrieval.duplicate_result_rate="
            f"{retrieval.duplicate_result_rate:.3f} exceeds 0.050"
        )
    if diagnosis.hallucination_rate > 0.0:
        failures.append(
            f"diagnosis.hallucination_rate={diagnosis.hallucination_rate:.3f} must be 0"
        )
    if failures:
        raise QualityGateError("; ".join(failures))


def run() -> None:
    parser = argparse.ArgumentParser(description="Run IntegrationOps offline evaluations.")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when retrieval or diagnosis quality gates fail.",
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    knowledge_dir = root / "data" / "demo" / "knowledge"
    retriever = build_demo_hybrid_retriever(knowledge_dir)
    retrieval = evaluate_retrieval(
        root / "data" / "evaluation" / "retrieval_cases.jsonl",
        knowledge_dir,
        retriever,
    )
    diagnosis = evaluate_diagnosis(
        root / "data" / "evaluation" / "diagnosis_cases.jsonl",
        workflow=InvestigationWorkflow(
            retriever=retriever,
            checkpointer=InMemorySaver(),
        ),
    )
    results = {"retrieval": asdict(retrieval), "diagnosis": asdict(diagnosis)}
    print(json.dumps(results, indent=2))
    if arguments.enforce:
        enforce_quality_gates(retrieval, diagnosis)


if __name__ == "__main__":
    run()
