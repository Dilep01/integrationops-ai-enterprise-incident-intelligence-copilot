export type Confidence = "high" | "medium" | "low" | "insufficient";

export interface Evidence {
  evidence_id: string;
  source_type: string;
  source_id: string;
  title: string;
  excerpt: string;
  reliability: number;
  occurred_at: string | null;
  source_uri: string | null;
  metadata: Record<string, unknown>;
}

export interface Hypothesis {
  title: string;
  explanation: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  score: number;
  status: "supported" | "possible" | "rejected";
}

export interface IncidentReport {
  run_id: string;
  incident_id: string;
  classification: string;
  summary: string;
  ranked_hypotheses: Hypothesis[];
  recommended_actions: string[];
  missing_information: string[];
  confidence: Confidence;
  confidence_basis: {
    source_type_count: number;
    independent_source_agreement: boolean;
    operational_confirmation: boolean;
    contradictory_evidence_count: number;
    citation_validation_passed: boolean;
    explanation: string;
  };
  evidence: Evidence[];
  timeline: {
    event_id: string;
    title: string;
    source_type: string;
    occurred_at: string;
    details: string;
  }[];
  generation: {
    provider: string;
    model: string;
    prompt_version: string;
  };
  generated_at: string;
  read_only: boolean;
}

export interface InvestigationSummary {
  run_id: string;
  incident_id: string;
  classification: string;
  confidence: Confidence;
  summary: string;
  created_at: string;
}

export type RemediationStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "executed"
  | "failed";

export interface RemediationAction {
  action_id: string;
  run_id: string;
  action_type: "reprocess_failed_transaction";
  transaction_reference: string;
  reason: string;
  status: RemediationStatus;
  requested_by: string;
  decided_by: string | null;
  decision_notes: string | null;
  execution_result: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RemediationAuditEvent {
  event_id: string;
  action_id: string;
  event_type: string;
  actor_id: string;
  details: Record<string, unknown>;
  created_at: string;
}
