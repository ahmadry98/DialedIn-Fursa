"use client";

import { useEffect, useMemo, useState } from "react";
import {
  deleteProfileCandidate,
  listProfileCandidates,
  promoteProfileCandidate,
  rerunProfileCandidateResearch,
  type ProfileCandidate,
  updateProfileCandidate,
} from "../../lib/api";

function formatJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseNotes(value: string): string[] {
  return value
    .split("\n")
    .map((note) => note.trim())
    .filter(Boolean);
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function statusClass(status: string): string {
  if (status === "draft_ready") return "ready";
  if (status === "needs_research") return "research";
  if (status === "draft_needs_review") return "review";
  return "neutral";
}

export function ProfileCandidateReview() {
  const [candidates, setCandidates] = useState<ProfileCandidate[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [draftText, setDraftText] = useState("{}");
  const [notesText, setNotesText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function refresh(nextSelectedKey?: string) {
    setLoading(true);
    setError(null);
    try {
      const payload = await listProfileCandidates();
      setCandidates(payload.candidates);
      const nextKey = nextSelectedKey ?? selectedKey ?? payload.candidates[0]?.candidate_key ?? "";
      setSelectedKey(payload.candidates.some((candidate) => candidate.candidate_key === nextKey) ? nextKey : payload.candidates[0]?.candidate_key ?? "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load candidates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const selected = useMemo(
    () => candidates.find((candidate) => candidate.candidate_key === selectedKey) ?? null,
    [candidates, selectedKey]
  );
  const readyCount = candidates.filter((candidate) => candidate.status === "draft_ready").length;
  const researchCount = candidates.filter((candidate) => candidate.status === "needs_research").length;
  const evidenceCount = selected?.research_evidence?.sources?.length ?? 0;

  useEffect(() => {
    setDraftText(formatJson(selected?.draft_profile));
    setNotesText((selected?.review_notes ?? []).join("\n"));
    setMessage(null);
    setError(null);
  }, [selected]);

  async function saveCandidate() {
    if (!selected) return;
    setBusy("save");
    setError(null);
    setMessage(null);
    try {
      const draft = JSON.parse(draftText) as Record<string, unknown>;
      await updateProfileCandidate(selected.candidate_key, {
        draft_profile: draft,
        review_notes: parseNotes(notesText),
        status: selected.status === "needs_research" ? "draft_needs_review" : selected.status,
      });
      setMessage("Candidate saved.");
      await refresh(selected.candidate_key);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save candidate");
    } finally {
      setBusy(null);
    }
  }

  async function rerunResearch() {
    if (!selected) return;
    setBusy("research");
    setError(null);
    setMessage(null);
    try {
      await rerunProfileCandidateResearch(selected.candidate_key);
      setMessage("Research finished and draft was updated.");
      await refresh(selected.candidate_key);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not rerun research");
    } finally {
      setBusy(null);
    }
  }

  async function promoteCandidate() {
    if (!selected) return;
    setBusy("promote");
    setError(null);
    setMessage(null);
    try {
      const draft = JSON.parse(draftText) as Record<string, unknown>;
      await updateProfileCandidate(selected.candidate_key, {
        draft_profile: draft,
        review_notes: parseNotes(notesText),
        status: selected.status === "needs_research" ? "draft_needs_review" : selected.status,
      });
      await promoteProfileCandidate(selected.candidate_key);
      setMessage("Candidate promoted and removed from the review queue.");
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not promote candidate");
    } finally {
      setBusy(null);
    }
  }


  async function deleteCandidate() {
    if (!selected) return;
    const confirmed = window.confirm(`Delete ${selected.name_entered} from the review queue?`);
    if (!confirmed) return;
    setBusy("delete");
    setError(null);
    setMessage(null);
    try {
      await deleteProfileCandidate(selected.candidate_key);
      setMessage("Candidate deleted from the review queue.");
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete candidate");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="admin-shell">
      <div className="admin-summary-grid" aria-label="Candidate review summary">
        <div className="admin-summary-card primary">
          <span>Total queue</span>
          <strong>{loading ? "-" : candidates.length}</strong>
          <small>Unknown gear captured by the coach</small>
        </div>
        <div className="admin-summary-card">
          <span>Ready drafts</span>
          <strong>{readyCount}</strong>
          <small>Can be reviewed and promoted</small>
        </div>
        <div className="admin-summary-card">
          <span>Needs research</span>
          <strong>{researchCount}</strong>
          <small>Run evidence + Bedrock drafting</small>
        </div>
      </div>

      <section className="admin-workspace">
        <aside className="panel candidate-list-panel">
          <div className="panel-heading admin-list-heading">
            <div>
              <h2>Review Queue</h2>
              <p>{loading ? "Loading candidates" : "Select one draft to inspect"}</p>
            </div>
            <button className="secondary-button compact-button" onClick={() => void refresh()} disabled={loading || Boolean(busy)}>
              Refresh
            </button>
          </div>

          <div className="candidate-list">
            {candidates.map((candidate) => (
              <button
                key={candidate.candidate_key}
                className={`candidate-row ${candidate.candidate_key === selectedKey ? "active" : ""}`}
                onClick={() => setSelectedKey(candidate.candidate_key)}
              >
                <span className="candidate-type">{candidate.type}</span>
                <strong>{candidate.name_entered}</strong>
                <small>{candidate.candidate_key}</small>
                <span className={`candidate-status ${statusClass(candidate.status)}`}>{statusLabel(candidate.status)}</span>
              </button>
            ))}
            {!loading && candidates.length === 0 ? <p className="empty-copy">No profile candidates need review.</p> : null}
          </div>
        </aside>

        <div className="admin-detail-stack">
        {selected ? (
          <>
            <section className="panel admin-detail-panel">
              <div className="panel-heading">
                <div>
                  <h2>{selected.name_entered}</h2>
                  <p>{selected.candidate_key}</p>
                </div>
                <span className={`candidate-status ${statusClass(selected.status)}`}>{statusLabel(selected.status)}</span>
              </div>

              <div className="admin-meta-grid">
                <div className="metric">
                  <span>Type</span>
                  <strong>{selected.type}</strong>
                </div>
                <div className="metric">
                  <span>Seen</span>
                  <strong>{selected.seen_count ?? 1}x</strong>
                </div>
                <div className="metric">
                  <span>Last seen</span>
                  <strong>{selected.last_seen_at?.slice(0, 10) ?? "unknown"}</strong>
                </div>
                <div className="metric">
                  <span>Evidence</span>
                  <strong>{evidenceCount}</strong>
                </div>
              </div>

              {selected.draft_validation ? (
                <div className="explanation-block">
                  <h3>Validation</h3>
                  <ul>
                    <li>{selected.draft_validation.is_valid ? "Draft shape is valid." : "Draft needs review."}</li>
                    {(selected.draft_validation.missing_fields ?? []).map((field) => <li key={field}>Missing: {field}</li>)}
                    {(selected.draft_validation.warnings ?? []).map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                </div>
              ) : null}
            </section>

            <section className="panel admin-editor-panel">
              <div className="field">
                <label htmlFor="draft-json">Draft profile JSON</label>
                <textarea id="draft-json" className="json-editor" value={draftText} onChange={(event) => setDraftText(event.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="review-notes">Review notes</label>
                <textarea
                  id="review-notes"
                  value={notesText}
                  onChange={(event) => setNotesText(event.target.value)}
                  placeholder="Add one review note per line before promoting."
                />
              </div>

              <div className="admin-actions">
                <button className="secondary-button" onClick={saveCandidate} disabled={Boolean(busy)}>
                  {busy === "save" ? "Saving" : "Save edits"}
                </button>
                <button className="secondary-button" onClick={rerunResearch} disabled={Boolean(busy)}>
                  {busy === "research" ? "Researching" : "Rerun research"}
                </button>
                <button className="danger-button" onClick={deleteCandidate} disabled={Boolean(busy)}>
                  {busy === "delete" ? "Deleting" : "Delete candidate"}
                </button>
                <button className="primary-button" onClick={promoteCandidate} disabled={Boolean(busy) || !selected.draft_profile}>
                  {busy === "promote" ? "Promoting" : "Promote profile"}
                </button>
              </div>

              {message ? <div className="notice">{message}</div> : null}
              {error ? <div className="alert">{error}</div> : null}
            </section>

            <section className="panel evidence-panel">
              <div className="panel-heading">
                <div>
                  <h2>Source Evidence</h2>
                  <p>Use these links and snippets before trusting the draft.</p>
                </div>
              </div>
              <div className="evidence-list">
                {(selected.research_evidence?.sources ?? []).map((source, index) => (
                  <article className="evidence-item" key={`${source.url ?? "source"}-${index}`}>
                    <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url || `Source ${index + 1}`}</a>
                    <p>{source.snippet || source.text || "No snippet stored."}</p>
                  </article>
                ))}
                {(selected.research_evidence?.sources ?? []).length === 0 ? (
                  <p className="empty-copy">No web evidence stored yet. Rerun research to collect sources.</p>
                ) : null}
              </div>
            </section>
          </>
        ) : (
          <section className="panel empty-state">
            <p>{loading ? "Loading candidates" : "No candidate selected."}</p>
          </section>
        )}
        </div>
      </section>
    </section>
  );
}
