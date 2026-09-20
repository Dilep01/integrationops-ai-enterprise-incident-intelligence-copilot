from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from integrationops.models import (
    Evidence,
    EvidenceSourceType,
    IncidentClassification,
    NormalizedIncident,
    ToolResult,
)


def _query_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


class MockOperationsTools:
    """Read-only synthetic operational adapters for the supported incident classes."""

    SCENARIOS = {
        IncidentClassification.AUTHENTICATION_FAILURE: {
            "log": (
                "LOG-AUTH-401-20260919",
                "Payment adapter authentication failures",
                "17 requests returned HTTP 401 beginning three minutes after secret rotation.",
                {"status_code": 401, "failure_count": 17},
            ),
            "configuration": (
                "CHG-2048",
                "OAuth client-secret rotation",
                "Secret v8 became active at 10:29 UTC while the adapter still referenced v7.",
                {"active_version": "v8", "configured_version": "v7"},
            ),
            "status": (
                "STATUS-BANK-API-20260919",
                "Bank API service status",
                "Bank API availability was normal and the authentication endpoint was reachable.",
                {},
            ),
            "incident": (
                "INC-10421",
                "Resolved authentication incident",
                "A prior HTTP 401 incident was caused by tokens issued with the previous secret.",
                {"resolution_status": "confirmed"},
            ),
        },
        IncidentClassification.TIMEOUT: {
            "log": (
                "LOG-TIMEOUT-20260920",
                "Downstream request timeouts",
                "23 payment requests exceeded the new five-second client timeout while the bank "
                "responded between seven and nine seconds.",
                {"failure_count": 23, "client_timeout_seconds": 5},
            ),
            "configuration": (
                "CHG-2077",
                "HTTP client timeout reduction",
                "Deployment 6.4 reduced the bank connector timeout from 30 seconds to 5 seconds.",
                {"previous_timeout_seconds": 30, "configured_timeout_seconds": 5},
            ),
            "status": (
                "STATUS-BANK-LATENCY-20260920",
                "Bank API latency status",
                "The bank remained available but p95 latency increased to 8.2 seconds.",
                {"availability": "available", "p95_latency_seconds": 8.2},
            ),
            "incident": (
                "INC-10502",
                "Resolved timeout incident",
                "A prior timeout spike was resolved by restoring the approved 15-second timeout.",
                {"resolution_status": "confirmed"},
            ),
        },
        IncidentClassification.MAPPING_ERROR: {
            "log": (
                "LOG-MAP-20260920",
                "Invoice transformation failures",
                "The mapper could not populate target field customerNumber because source field "
                "buyer_id was absent from every failed invoice.",
                {"failure_count": 11, "target_field": "customerNumber"},
            ),
            "configuration": (
                "CHG-2081",
                "Invoice schema and mapping deployment",
                "Source schema v12 renamed buyer_id to customer_id, but mapping rule v18 still "
                "reads buyer_id.",
                {"schema_version": "v12", "mapping_version": "v18"},
            ),
            "incident": (
                "INC-10518",
                "Resolved mapping incident",
                "A prior deployment failed when a source-field rename was not reflected in the "
                "mapping rule.",
                {"resolution_status": "confirmed"},
            ),
        },
        IncidentClassification.INVALID_PAYLOAD: {
            "log": (
                "LOG-PAYLOAD-20260920",
                "Payload validation failures",
                "The Bank API returned HTTP 422 because required field currency was missing.",
                {"status_code": 422, "missing_field": "currency"},
            ),
            "configuration": (
                "CHG-2088",
                "Payment contract v3 activation",
                "Contract v3 made currency mandatory while the producer remained on payload v2.",
                {"active_contract": "v3", "producer_contract": "v2"},
            ),
            "incident": (
                "INC-10531",
                "Resolved payload incident",
                "A prior HTTP 422 incident was resolved by adding the newly required "
                "currency field.",
                {"resolution_status": "confirmed"},
            ),
        },
        IncidentClassification.DUPLICATE_TRANSACTION: {
            "log": (
                "LOG-DUPLICATE-20260920",
                "Duplicate transaction rejection",
                "Two submissions used business reference PAY-88421; the second returned HTTP 409.",
                {"status_code": 409, "business_reference": "PAY-88421"},
            ),
            "configuration": (
                "CHG-2092",
                "Retry idempotency configuration",
                "Deployment 6.5 disabled forwarding of the Idempotency-Key header on retries.",
                {"idempotency_header_forwarding": False},
            ),
            "incident": (
                "INC-10544",
                "Resolved duplicate incident",
                "A prior duplicate was caused by retrying without the original idempotency key.",
                {"resolution_status": "confirmed"},
            ),
        },
    }

    def _scenario(self, incident: NormalizedIncident) -> dict:
        return self.SCENARIOS.get(incident.classification, {})

    def _result(
        self,
        incident: NormalizedIncident,
        key: str,
        source_type: EvidenceSourceType,
        tool_name: str,
        prefix: str,
        minute: int,
    ) -> ToolResult:
        scenario = self._scenario(incident)
        item = scenario.get(key)
        evidence = []
        if item:
            source_id, title, excerpt, metadata = item
            evidence = [
                Evidence(
                    source_type=source_type,
                    source_id=source_id,
                    title=title,
                    excerpt=excerpt,
                    reliability=0.95 if source_type != EvidenceSourceType.INCIDENT else 0.85,
                    occurred_at=datetime(2026, 9, 20, 10, minute, tzinfo=UTC),
                    source_uri=f"mock://{key}/{source_id}",
                    metadata=metadata,
                )
            ]
        return ToolResult(
            tool_name=tool_name,
            query_id=_query_id(prefix),
            succeeded=True,
            evidence=evidence,
        )

    def search_logs(self, incident: NormalizedIncident) -> ToolResult:
        return self._result(
            incident, "log", EvidenceSourceType.LOG, "search_logs", "LOGQ", 32
        )

    def get_configuration_changes(self, incident: NormalizedIncident) -> ToolResult:
        return self._result(
            incident,
            "configuration",
            EvidenceSourceType.CONFIGURATION,
            "get_configuration_changes",
            "CHGQ",
            29,
        )

    def get_service_health(self, incident: NormalizedIncident) -> ToolResult:
        return self._result(
            incident,
            "status",
            EvidenceSourceType.SERVICE_STATUS,
            "get_service_health",
            "STQ",
            38,
        )

    def find_similar_incidents(self, incident: NormalizedIncident) -> ToolResult:
        return self._result(
            incident,
            "incident",
            EvidenceSourceType.INCIDENT,
            "find_similar_incidents",
            "INCQ",
            45,
        )

    def collect_all(self, incident: NormalizedIncident) -> list[ToolResult]:
        collectors = [
            self.search_logs(incident),
            self.get_configuration_changes(incident),
            self.find_similar_incidents(incident),
        ]
        if incident.classification in {
            IncidentClassification.AUTHENTICATION_FAILURE,
            IncidentClassification.TIMEOUT,
        }:
            collectors.insert(2, self.get_service_health(incident))
        return collectors
