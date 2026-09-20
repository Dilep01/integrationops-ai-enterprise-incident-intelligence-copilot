import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  approveRemediation,
  createInvestigation,
  executeRemediation,
  getInvestigation,
  getRemediationAudit,
  listInvestigations,
  requestRemediation,
  submitFeedback
} from "./api";
import type {
  Evidence,
  IncidentReport,
  InvestigationSummary,
  RemediationAction,
  RemediationAuditEvent
} from "./types";

const demoMessage = "Payment integration failed with HTTP 401 after token rotation.";

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function EvidenceCard({ evidence }: { evidence: Evidence }) {
  return (
    <article className="evidence-card">
      <div className="evidence-card__header">
        <span className={`source-tag source-tag--${evidence.source_type}`}>
          {formatLabel(evidence.source_type)}
        </span>
        <span className="reliability">{Math.round(evidence.reliability * 100)}% reliable</span>
      </div>
      <h4>{evidence.title}</h4>
      <p>{evidence.excerpt}</p>
      <footer>
        <code>{evidence.evidence_id}</code>
        <span>{evidence.source_id}</span>
      </footer>
    </article>
  );
}

function App() {
  const [message, setMessage] = useState(demoMessage);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [history, setHistory] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeView, setActiveView] = useState<"diagnosis" | "evidence" | "timeline">(
    "diagnosis"
  );
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState("");
  const [transactionReference, setTransactionReference] = useState("TXN-DEMO-401");
  const [remediation, setRemediation] = useState<RemediationAction | null>(null);
  const [remediationAudit, setRemediationAudit] = useState<RemediationAuditEvent[]>([]);
  const [remediationStatus, setRemediationStatus] = useState("");

  const leadingHypothesis = report?.ranked_hypotheses[0];
  const evidenceMap = useMemo(
    () => new Map(report?.evidence.map((item) => [item.evidence_id, item]) ?? []),
    [report]
  );

  async function refreshHistory() {
    try {
      setHistory(await listInvestigations());
    } catch {
      // The empty-state remains usable if the API is still starting.
    }
  }

  useEffect(() => {
    void refreshHistory();
    const requestedRunId = new URLSearchParams(window.location.search).get("run_id");
    if (requestedRunId) {
      void openHistory(requestedRunId);
    }
  }, []);

  async function investigate(event: FormEvent) {
    event.preventDefault();
    if (message.trim().length < 5) return;
    setLoading(true);
    setError("");
    setFeedbackStatus("");
    try {
      const result = await createInvestigation(message.trim());
      setReport(result);
      setRemediation(null);
      setRemediationAudit([]);
      setRemediationStatus("");
      setActiveView("diagnosis");
      await refreshHistory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The investigation could not be started.");
    } finally {
      setLoading(false);
    }
  }

  async function openHistory(runId: string) {
    setLoading(true);
    setError("");
    try {
      setReport(await getInvestigation(runId));
      setRemediation(null);
      setRemediationAudit([]);
      setRemediationStatus("");
      setActiveView("diagnosis");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The investigation could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(rating: number) {
    if (!report) return;
    setFeedbackStatus("Saving…");
    try {
      await submitFeedback(report.run_id, rating, feedbackNotes);
      setFeedbackStatus("Feedback recorded");
      setFeedbackNotes("");
    } catch (caught) {
      setFeedbackStatus(caught instanceof Error ? caught.message : "Feedback failed");
    }
  }

  async function refreshRemediationAudit(actionId: string) {
    setRemediationAudit(await getRemediationAudit(actionId));
  }

  async function createRemediation() {
    if (!report || transactionReference.trim().length < 3) return;
    setRemediationStatus("Creating approval request…");
    try {
      const action = await requestRemediation(report.run_id, transactionReference.trim());
      setRemediation(action);
      await refreshRemediationAudit(action.action_id);
      setRemediationStatus("Waiting for an independent reviewer");
    } catch (caught) {
      setRemediationStatus(caught instanceof Error ? caught.message : "Request failed");
    }
  }

  async function approveCurrentRemediation() {
    if (!remediation) return;
    setRemediationStatus("Recording reviewer decision…");
    try {
      const action = await approveRemediation(remediation.action_id);
      setRemediation(action);
      await refreshRemediationAudit(action.action_id);
      setRemediationStatus("Approved; ready for operator execution");
    } catch (caught) {
      setRemediationStatus(caught instanceof Error ? caught.message : "Approval failed");
    }
  }

  async function executeCurrentRemediation() {
    if (!remediation) return;
    setRemediationStatus("Executing through the configured local runtime…");
    try {
      const action = await executeRemediation(remediation.action_id);
      setRemediation(action);
      await refreshRemediationAudit(action.action_id);
      setRemediationStatus("Local runtime execution completed");
    } catch (caught) {
      setRemediationStatus(caught instanceof Error ? caught.message : "Execution failed");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand__mark" aria-hidden="true">IO</div>
          <div>
            <strong>IntegrationOps</strong>
            <span>Incident Intelligence</span>
          </div>
        </div>

        <button className="new-investigation" onClick={() => {
          setReport(null);
          setRemediation(null);
          setRemediationAudit([]);
        }}>
          <span>＋</span> New investigation
        </button>

        <div className="history-heading">
          <span>Recent investigations</span>
          <button aria-label="Refresh history" onClick={() => void refreshHistory()}>↻</button>
        </div>
        <nav className="history-list" aria-label="Recent investigations">
          {history.length === 0 && <p className="history-empty">No investigations saved yet.</p>}
          {history.map((item) => (
            <button
              key={item.run_id}
              className={report?.run_id === item.run_id ? "history-item is-active" : "history-item"}
              onClick={() => void openHistory(item.run_id)}
            >
              <span className={`status-dot status-dot--${item.confidence}`} />
              <span className="history-item__body">
                <strong>{item.incident_id}</strong>
                <small>{formatLabel(item.classification)}</small>
              </span>
              <time>{formatDate(item.created_at)}</time>
            </button>
          ))}
        </nav>

        <div className="sidebar__footer">
          <span className="live-indicator"><i /> Approval-gated local runtime</span>
          <small>Tenant: demo-enterprise</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Operations workspace</span>
            <h1>Incident investigation</h1>
          </div>
          <div className="topbar__meta">
            <span>Hybrid RAG</span>
            <span>Evidence gated</span>
            <span>v0.10.0</span>
          </div>
        </header>

        <section className="query-panel">
          <form onSubmit={investigate}>
            <label htmlFor="incident-message">Describe the failure or paste an alert</label>
            <div className="query-input">
              <textarea
                id="incident-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={3}
                placeholder="Example: Payment integration failed with HTTP 401 after token rotation."
              />
              <button type="submit" disabled={loading || message.trim().length < 5}>
                {loading ? "Investigating…" : "Run investigation"}
              </button>
            </div>
          </form>
          {error && <p className="error-banner">{error}</p>}
        </section>

        {!report && !loading && (
          <section className="empty-state">
            <div className="empty-state__graphic" aria-hidden="true">
              <span>API</span><i /><span>CPI</span><i /><span>BANK</span>
            </div>
            <h2>Trace the failure across systems</h2>
            <p>
              The investigation graph correlates current runbooks, operational signals, service
              health, configuration changes, and resolved incidents before proposing a cause.
            </p>
            <div className="capability-grid">
              <article><strong>Hybrid retrieval</strong><span>Dense + sparse evidence search</span></article>
              <article><strong>Grounded diagnosis</strong><span>Every claim points to evidence</span></article>
              <article><strong>Safe actions</strong><span>Mutations require operator approval</span></article>
            </div>
          </section>
        )}

        {loading && (
          <section className="loading-state">
            <div className="scan-line" />
            <span>Collecting logs, changes, runbooks, and similar incidents…</span>
          </section>
        )}

        {report && !loading && (
          <div className="report-layout">
            <section className="report-main">
              <div className="report-title-row">
                <div>
                  <span className="eyebrow">{report.incident_id} · {report.run_id}</span>
                  <h2>{formatLabel(report.classification)}</h2>
                </div>
                <div className={`confidence confidence--${report.confidence}`}>
                  <span>{report.confidence}</span>
                  <small>confidence</small>
                </div>
              </div>

              <div className="report-tabs" role="tablist">
                <button
                  className={activeView === "diagnosis" ? "is-active" : ""}
                  onClick={() => setActiveView("diagnosis")}
                >Diagnosis</button>
                <button
                  className={activeView === "evidence" ? "is-active" : ""}
                  onClick={() => setActiveView("evidence")}
                >Evidence <span>{report.evidence.length}</span></button>
                <button
                  className={activeView === "timeline" ? "is-active" : ""}
                  onClick={() => setActiveView("timeline")}
                >Timeline <span>{report.timeline.length}</span></button>
              </div>

              {activeView === "diagnosis" ? (
                <div className="diagnosis-view">
                  <article className="summary-card">
                    <span className="card-label">Incident summary</span>
                    <p>{report.summary}</p>
                  </article>

                  {leadingHypothesis && (
                    <article className="hypothesis-card">
                      <div className="hypothesis-card__top">
                        <span className={`hypothesis-status hypothesis-status--${leadingHypothesis.status}`}>
                          {leadingHypothesis.status}
                        </span>
                        <strong>{Math.round(leadingHypothesis.score * 100)}%</strong>
                      </div>
                      <h3>{leadingHypothesis.title}</h3>
                      <p>{leadingHypothesis.explanation}</p>
                      <div className="evidence-links">
                        {leadingHypothesis.supporting_evidence_ids.map((id) => (
                          <button key={id} onClick={() => setActiveView("evidence")}>
                            {evidenceMap.get(id)?.source_id ?? id}
                          </button>
                        ))}
                      </div>
                    </article>
                  )}

                  <article className="actions-card">
                    <span className="card-label">Recommended actions</span>
                    <ol>
                      {report.recommended_actions.map((action) => <li key={action}>{action}</li>)}
                    </ol>
                  </article>
                </div>
              ) : activeView === "evidence" ? (
                <div className="evidence-grid">
                  {report.evidence.map((item) => <EvidenceCard key={item.evidence_id} evidence={item} />)}
                </div>
              ) : (
                <div className="timeline-list">
                  {report.timeline.map((event) => (
                    <article className="timeline-event" key={event.event_id}>
                      <time>{formatDate(event.occurred_at)}</time>
                      <div>
                        <span className="card-label">{formatLabel(event.source_type)}</span>
                        <h4>{event.title}</h4>
                        <p>{event.details}</p>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <aside className="report-aside">
              <article className="assurance-card">
                <span className="card-label">Grounding checks</span>
                <ul>
                  <li><span>✓</span>Citations validated</li>
                  <li><span>✓</span>{report.confidence_basis.source_type_count} evidence types</li>
                  <li><span>✓</span>Operational signal confirmed</li>
                  <li><span>✓</span>Read-only execution</li>
                </ul>
                <p>{report.confidence_basis.explanation}</p>
              </article>

              <article className="model-card">
                <span className="card-label">Generation record</span>
                <dl>
                  <div><dt>Provider</dt><dd>{report.generation.provider}</dd></div>
                  <div><dt>Model</dt><dd>{report.generation.model}</dd></div>
                  <div><dt>Prompt</dt><dd>{report.generation.prompt_version}</dd></div>
                </dl>
              </article>

              {report.confidence === "high" &&
                report.classification !== "duplicate_transaction" && (
                <article className="remediation-card">
                  <span className="card-label">Approval-gated remediation</span>
                  <p>Allow-listed action: reprocess one failed transaction through the configured target.</p>
                  {!remediation && (
                    <>
                      <input
                        value={transactionReference}
                        onChange={(event) => setTransactionReference(event.target.value)}
                        aria-label="Transaction reference"
                      />
                      <button onClick={() => void createRemediation()}>
                        Request approval
                      </button>
                    </>
                  )}
                  {remediation && (
                    <>
                      <div className={`remediation-state remediation-state--${remediation.status}`}>
                        {formatLabel(remediation.status)}
                      </div>
                      <code>{remediation.action_id}</code>
                      {remediation.status === "pending_approval" && (
                        <button onClick={() => void approveCurrentRemediation()}>
                          Review as separate approver
                        </button>
                      )}
                      {remediation.status === "approved" && (
                        <button onClick={() => void executeCurrentRemediation()}>
                          Execute through local runtime
                        </button>
                      )}
                      {remediation.execution_result?.execution_reference && (
                        <small>
                          Reference: {String(remediation.execution_result.execution_reference)}
                        </small>
                      )}
                      {remediation.execution_result?.target_system && (
                        <small>
                          Target: {String(remediation.execution_result.target_system)}
                        </small>
                      )}
                      <small>{remediationAudit.length} audit events recorded</small>
                    </>
                  )}
                  {remediationStatus && <small>{remediationStatus}</small>}
                </article>
              )}

              <article className="feedback-card">
                <span className="card-label">Engineer feedback</span>
                <p>Was this diagnosis useful?</p>
                <div className="rating-row">
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <button key={rating} onClick={() => void sendFeedback(rating)}>{rating}</button>
                  ))}
                </div>
                <textarea
                  value={feedbackNotes}
                  onChange={(event) => setFeedbackNotes(event.target.value)}
                  placeholder="Optional correction or note"
                  rows={3}
                />
                {feedbackStatus && <small>{feedbackStatus}</small>}
              </article>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
