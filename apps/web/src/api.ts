import type {
  IncidentReport,
  InvestigationSummary,
  RemediationAction,
  RemediationAuditEvent
} from "./types";

const tenantHeaders = {
  "Content-Type": "application/json",
  "X-Tenant-ID": "demo-enterprise",
  "X-Roles": "integration-engineer",
  "X-User-ID": "analyst-demo"
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createInvestigation(message: string): Promise<IncidentReport> {
  const response = await fetch("/api/v1/investigations", {
    method: "POST",
    headers: tenantHeaders,
    body: JSON.stringify({
      message,
      environment: "production",
      integration: "invoice-payment",
      tenant_id: "demo-enterprise"
    })
  });
  return parseResponse<IncidentReport>(response);
}

export async function getInvestigation(runId: string): Promise<IncidentReport> {
  const response = await fetch(`/api/v1/investigations/${runId}`, {
    headers: tenantHeaders
  });
  return parseResponse<IncidentReport>(response);
}

export async function listInvestigations(): Promise<InvestigationSummary[]> {
  const response = await fetch("/api/v1/investigations?limit=20", {
    headers: tenantHeaders
  });
  return parseResponse<InvestigationSummary[]>(response);
}

export async function submitFeedback(
  runId: string,
  rating: number,
  notes: string
): Promise<void> {
  const response = await fetch(`/api/v1/investigations/${runId}/feedback`, {
    method: "POST",
    headers: tenantHeaders,
    body: JSON.stringify({ rating, notes: notes || null })
  });
  await parseResponse(response);
}

export async function requestRemediation(
  runId: string,
  transactionReference: string
): Promise<RemediationAction> {
  const response = await fetch(`/api/v1/investigations/${runId}/remediation-actions`, {
    method: "POST",
    headers: tenantHeaders,
    body: JSON.stringify({
      action_type: "reprocess_failed_transaction",
      transaction_reference: transactionReference,
      reason: "Reprocess after the evidence-backed credential correction is verified."
    })
  });
  return parseResponse<RemediationAction>(response);
}

export async function approveRemediation(actionId: string): Promise<RemediationAction> {
  const response = await fetch(`/api/v1/remediation-actions/${actionId}/decision`, {
    method: "POST",
    headers: {
      ...tenantHeaders,
      "X-Roles": "remediation-approver",
      "X-User-ID": "reviewer-demo"
    },
    body: JSON.stringify({
      decision: "approve",
      notes: "Evidence, transaction scope, and recovery preconditions verified."
    })
  });
  return parseResponse<RemediationAction>(response);
}

export async function executeRemediation(actionId: string): Promise<RemediationAction> {
  const response = await fetch(`/api/v1/remediation-actions/${actionId}/execute`, {
    method: "POST",
    headers: {
      ...tenantHeaders,
      "X-Roles": "remediation-operator",
      "X-User-ID": "operator-demo",
      "Idempotency-Key": `demo-execution-${actionId}`
    }
  });
  return parseResponse<RemediationAction>(response);
}

export async function getRemediationAudit(
  actionId: string
): Promise<RemediationAuditEvent[]> {
  const response = await fetch(`/api/v1/remediation-actions/${actionId}/audit`, {
    headers: tenantHeaders
  });
  return parseResponse<RemediationAuditEvent[]>(response);
}
