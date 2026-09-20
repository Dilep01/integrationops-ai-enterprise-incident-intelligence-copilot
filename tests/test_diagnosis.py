import json

import httpx
import pytest

from integrationops.config import Settings
from integrationops.diagnosis import (
    ActionSafetyPolicy,
    EvidenceSufficiencyPolicy,
    GroundingError,
    ModelTransportError,
    OllamaTransport,
    StructuredLLMDiagnosisEngine,
    build_diagnosis_engine,
)
from integrationops.models import (
    Evidence,
    EvidenceSourceType,
    IncidentClassification,
    IncidentRequest,
    NormalizedIncident,
)
from integrationops.workflow import InvestigationWorkflow


class StaticTransport:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return json.dumps(self.response)


def _incident() -> NormalizedIncident:
    return NormalizedIncident(
        incident_id="INC-TEST-401",
        message="HTTP 401 after token rotation",
        environment="production",
        integration="invoice-payment",
        classification=IncidentClassification.AUTHENTICATION_FAILURE,
    )


def _evidence() -> list[Evidence]:
    return [
        Evidence(
            evidence_id="EVD-DOC",
            source_type=EvidenceSourceType.DOCUMENT,
            source_id="runbook:v1",
            title="Authentication runbook",
            excerpt="Tokens created with an inactive secret are rejected with HTTP 401.",
            reliability=0.9,
        ),
        Evidence(
            evidence_id="EVD-LOG",
            source_type=EvidenceSourceType.LOG,
            source_id="LOG-1",
            title="Authentication failures",
            excerpt="HTTP 401 began after the secret rotation.",
            reliability=0.95,
        ),
    ]


def _valid_response() -> dict:
    return {
        "summary": "The token was created with an inactive secret.",
        "hypotheses": [
            {
                "title": "Inactive client secret",
                "explanation": "The runbook and logs agree.",
                "supporting_evidence_ids": ["EVD-DOC", "EVD-LOG"],
                "contradicting_evidence_ids": [],
                "score": 0.91,
                "status": "supported",
            }
        ],
        "recommended_actions": ["Generate a replacement token."],
        "missing_information": [],
    }


def test_structured_model_output_is_parsed_and_grounded() -> None:
    transport = StaticTransport(_valid_response())
    engine = StructuredLLMDiagnosisEngine(
        transport,
        provider="test-provider",
        model="test-model",
    )

    result = engine.diagnose(_incident(), _evidence())

    assert result.hypotheses[0].status == "supported"
    assert result.generation.provider == "test-provider"
    assert result.generation.prompt_version == "diagnosis-v2"
    assert "untrusted data" in transport.system_prompt
    assert "include at least one supported hypothesis" in transport.system_prompt
    assert "EVD-DOC" in transport.user_prompt


def test_model_cannot_cite_evidence_that_was_not_retrieved() -> None:
    response = _valid_response()
    response["hypotheses"][0]["supporting_evidence_ids"] = ["EVD-INVENTED"]
    engine = StructuredLLMDiagnosisEngine(
        StaticTransport(response),
        provider="test-provider",
        model="test-model",
    )

    with pytest.raises(GroundingError, match="unavailable evidence"):
        engine.diagnose(_incident(), _evidence())


def test_evidence_gate_requires_document_and_operational_sources() -> None:
    policy = EvidenceSufficiencyPolicy()
    sufficient, missing = policy.assess([_evidence()[0]])

    assert sufficient is False
    assert any("operational evidence" in item for item in missing)


def test_state_changing_actions_are_converted_to_approval_requests() -> None:
    guarded = ActionSafetyPolicy().guard(
        [
            "Generate a replacement token.",
            "Verify the active secret version.",
            "Restart the payment adapter after approval.",
        ]
    )

    assert guarded[0].startswith("Request operator approval before:")
    assert guarded[1] == "Verify the active secret version."
    assert guarded[2] == "Restart the payment adapter after approval."


def test_workflow_fails_closed_when_model_invents_a_citation() -> None:
    response = _valid_response()
    response["hypotheses"][0]["supporting_evidence_ids"] = ["EVD-INVENTED"]
    engine = StructuredLLMDiagnosisEngine(
        StaticTransport(response),
        provider="test-provider",
        model="test-model",
    )

    report = InvestigationWorkflow(diagnosis_engine=engine).investigate(
        IncidentRequest(
            incident_id="INC-DEMO-401",
            message="Payment integration failed with HTTP 401 after token rotation.",
        )
    )

    assert report.confidence.value == "insufficient"
    assert report.ranked_hypotheses == []
    assert report.confidence_basis.citation_validation_passed is False
    assert any("unavailable evidence" in item for item in report.missing_information)


def test_ollama_transport_enforces_schema_and_disables_thinking() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json={"message": {"role": "assistant", "content": json.dumps(_valid_response())}},
        )

    transport = OllamaTransport(
        base_url="http://ollama.test",
        model="qwen3:4b",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = StructuredLLMDiagnosisEngine(
        transport,
        provider="ollama",
        model="qwen3:4b",
    ).diagnose(_incident(), _evidence())

    assert result.generation.provider == "ollama"
    assert captured["model"] == "qwen3:4b"
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["format"]["type"] == "object"
    assert captured["options"] == {"temperature": 0, "seed": 42}


def test_ollama_transport_converts_connection_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Ollama is unavailable", request=request)

    transport = OllamaTransport(
        base_url="http://ollama.test",
        model="qwen3:4b",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ModelTransportError, match="Ollama endpoint failed"):
        transport.complete(system_prompt="system", user_prompt="user")


def test_ollama_provider_builds_local_model_engine() -> None:
    engine = build_diagnosis_engine(
        Settings(
            llm_provider="ollama",
            llm_model="qwen3:4b",
            ollama_base_url="http://127.0.0.1:11434",
        )
    )

    assert engine.generation.provider == "ollama"
    assert engine.generation.model == "qwen3:4b"
