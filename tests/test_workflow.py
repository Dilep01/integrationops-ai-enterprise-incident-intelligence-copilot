import pytest

from integrationops.models import ConfidenceLevel, IncidentClassification, IncidentRequest
from integrationops.workflow import InvestigationWorkflow


def test_authentication_incident_is_grounded_and_cited() -> None:
    report = InvestigationWorkflow().investigate(
        IncidentRequest(
            incident_id="INC-DEMO-401",
            message="Payment integration failed with HTTP 401 after token rotation.",
            environment="production",
        )
    )

    assert report.classification == IncidentClassification.AUTHENTICATION_FAILURE
    assert report.confidence == ConfidenceLevel.HIGH
    assert report.read_only is True
    assert report.confidence_basis.citation_validation_passed is True
    assert report.confidence_basis.operational_confirmation is True
    assert report.ranked_hypotheses[0].status == "supported"
    assert report.generation.provider == "deterministic"

    available = {item.evidence_id for item in report.evidence}
    assert set(report.ranked_hypotheses[0].supporting_evidence_ids) <= available
    assert "approval" in report.recommended_actions[-1].lower()
    assert "approval" in report.recommended_actions[1].lower()


def test_unsupported_failure_class_returns_insufficient_evidence() -> None:
    report = InvestigationWorkflow().investigate(
        IncidentRequest(message="Invoice processing failed unexpectedly without an error code.")
    )

    assert report.classification == IncidentClassification.UNKNOWN
    assert report.confidence == ConfidenceLevel.INSUFFICIENT
    assert report.ranked_hypotheses == []
    assert report.missing_information


@pytest.mark.parametrize(
    ("message", "classification", "expected_term"),
    [
        (
            "Bank API requests timed out after the client timeout was reduced.",
            IncidentClassification.TIMEOUT,
            "latency",
        ),
        (
            "Invoice mapping failed after buyer_id was renamed to customer_id.",
            IncidentClassification.MAPPING_ERROR,
            "customer_id",
        ),
        (
            "HTTP 422 invalid payload is missing required currency.",
            IncidentClassification.INVALID_PAYLOAD,
            "currency",
        ),
        (
            "Duplicate transaction after retry lost the Idempotency-Key.",
            IncidentClassification.DUPLICATE_TRANSACTION,
            "idempotency",
        ),
    ],
)
def test_supported_incident_classes_are_grounded(
    message: str,
    classification: IncidentClassification,
    expected_term: str,
) -> None:
    report = InvestigationWorkflow().investigate(IncidentRequest(message=message))

    assert report.classification == classification
    assert report.confidence == ConfidenceLevel.HIGH
    assert report.confidence_basis.citation_validation_passed is True
    assert expected_term in (
        report.summary + " " + report.ranked_hypotheses[0].explanation
    ).lower()
    assert len(report.timeline) >= 3
    assert report.timeline == sorted(report.timeline, key=lambda event: event.occurred_at)
