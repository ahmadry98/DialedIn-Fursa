"use client";

import { useEffect, useMemo, useState } from "react";
import {
  attachMachineProfileImage,
  createMediaUploadUrl,
  deleteProfileCandidate,
  listMachines,
  listProfileCandidates,
  promoteProfileCandidate,
  registerMediaUpload,
  rerunProfileCandidateResearch,
  type MachineSummary,
  type ProfileCandidate,
  updateProfileCandidate,
  uploadFileToMediaTarget,
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

function qualityClass(score?: number): string {
  if (score === undefined) return "unknown";
  if (score >= 75) return "strong";
  if (score >= 55) return "ok";
  return "weak";
}

function sourceHost(url?: string): string {
  if (!url) return "source";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
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
  const [machines, setMachines] = useState<MachineSummary[]>([]);
  const [selectedMachineSlug, setSelectedMachineSlug] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [copied, setCopied] = useState(false);

  async function refresh(nextSelectedKey?: string) {
    setLoading(true);
    setError(null);
    try {
      const [candidatePayload, machinePayload] = await Promise.all([listProfileCandidates(), listMachines()]);
      setCandidates(candidatePayload.candidates);
      setMachines(machinePayload.machines);
      setSelectedMachineSlug((current) => current || machinePayload.machines[0]?.slug || "");
      const nextKey = nextSelectedKey ?? selectedKey ?? candidatePayload.candidates[0]?.candidate_key ?? "";
      setSelectedKey(candidatePayload.candidates.some((candidate) => candidate.candidate_key === nextKey) ? nextKey : candidatePayload.candidates[0]?.candidate_key ?? "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load admin data");
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
  const evidenceSources = selected?.research_evidence?.sources ?? [];
  const evidenceCount = evidenceSources.length;
  const qualityScore = selected?.research_quality?.score;
  const qualityThreshold = selected?.research_quality?.threshold ?? 55;
  const isPromotable = Boolean(selected?.draft_profile) && (qualityScore === undefined || qualityScore >= qualityThreshold);
  const validationWarnings = selected?.draft_validation?.warnings ?? [];
  const validationMissing = selected?.draft_validation?.missing_fields ?? [];

  useEffect(() => {
    setDraftText(formatJson(selected?.draft_profile));
    setNotesText((selected?.review_notes ?? []).join("\n"));
    setMessage(null);
    setError(null);
    setCopied(false);
  }, [selected]);

  async function uploadMachineImage() {
    if (!selectedMachineSlug || !imageFile) return;
    setBusy("image");
    setError(null);
    setMessage(null);
    try {
      const extension = imageFile.name.split(".").pop()?.toLowerCase() || "jpg";
      const target = await createMediaUploadUrl({
        filename: `${selectedMachineSlug}.${extension}`,
        content_type: imageFile.type || "image/jpeg",
        media_kind: "machine_photo",
        user_id: "admin",
      });
      await uploadFileToMediaTarget(imageFile, target);
      const registered = await registerMediaUpload({
        media_key: target.media_key,
        media_kind: "machine_photo",
        storage_mode: target.storage_mode,
        content_type: imageFile.type || "image/jpeg",
      });
      await attachMachineProfileImage(selectedMachineSlug, {
        media_key: registered.media_key,
        storage_mode: registered.storage_mode,
        content_type: registered.content_type,
        source_url: `admin upload: ${imageFile.name}`,
        license_or_source_type: "admin_upload",
        status: "reviewed",
        review_notes: "Uploaded from Profile Candidate Review admin.",
      });
      setImageFile(null);
      setMessage("Machine image uploaded and saved.");
      await refresh(selectedKey);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not upload machine image");
    } finally {
      setBusy(null);
    }
  }

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

  async function copyDraftJson() {
    try {
      await navigator.clipboard.writeText(draftText);
      setCopied(true);
      setMessage("Draft JSON copied.");
    } catch {
      setError("Could not copy draft JSON from this browser.");
    }
  }

  function openAllEvidence() {
    evidenceSources
      .map((source) => source.url)
      .filter((url): url is string => Boolean(url))
      .slice(0, 6)
      .forEach((url) => window.open(url, "_blank", "noopener,noreferrer"));
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

              <div className="admin-review-grid">
                <div className={`quality-block ${qualityClass(qualityScore)}`}>
                  <div>
                    <span>Research quality</span>
                    <strong>{qualityScore ?? "--"}<small>/100</small></strong>
                    <small>Promote target: {qualityThreshold}+</small>
                  </div>
                  <div className="quality-meter" aria-label="Research quality score">
                    <span style={{ width: `${Math.min(Math.max(qualityScore ?? 0, 0), 100)}%` }} />
                  </div>
                  <p>{isPromotable ? "Looks ready for human review and promotion." : "Needs better evidence or manual edits before promotion."}</p>
                </div>

                <div className="validation-card">
                  <h3>Validation</h3>
                  {selected.draft_validation ? (
                    <ul>
                      <li>{selected.draft_validation.is_valid ? "Draft shape is valid." : "Draft needs review."}</li>
                      {validationMissing.map((field) => <li key={field}>Missing: {field}</li>)}
                      {validationWarnings.map((warning) => <li key={warning}>{warning}</li>)}
                    </ul>
                  ) : (
                    <p>No validation has run yet.</p>
                  )}
                </div>
              </div>

              {selected.research_quality ? (
                <div className="quality-reasons">
                  <h3>{statusLabel(selected.research_quality.status ?? selected.status)}</h3>
                  <ul>
                    {(selected.research_quality.reasons ?? []).map((reason) => <li key={reason}>{reason}</li>)}
                    {(selected.research_quality.warnings ?? []).map((warning) => <li key={warning}>Warning: {warning}</li>)}
                  </ul>
                </div>
              ) : null}
            </section>

            <section className="panel admin-editor-panel">
              <div className="editor-toolbar">
                <div>
                  <h2>Draft profile JSON</h2>
                  <p>Edit only fields you verified, then save or promote.</p>
                </div>
                <button className="secondary-button compact-button" onClick={() => void copyDraftJson()} disabled={!selected.draft_profile}>
                  {copied ? "Copied" : "Copy JSON"}
                </button>
              </div>
              <div className="field">
                <label htmlFor="draft-json" className="sr-only">Draft profile JSON</label>
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
                <button className="primary-button" onClick={promoteCandidate} disabled={Boolean(busy) || !isPromotable}>
                  {busy === "promote" ? "Promoting" : "Promote profile"}
                </button>
              </div>

              {message ? <div className="notice">{message}</div> : null}
              {error ? <div className="alert">{error}</div> : null}
            </section>

            <section className="panel evidence-panel">
              <div className="panel-heading evidence-heading">
                <div>
                  <h2>Source Evidence</h2>
                  <p>Use these links and snippets before trusting the draft.</p>
                </div>
                <button className="secondary-button compact-button" onClick={openAllEvidence} disabled={evidenceCount === 0}>
                  Open sources
                </button>
              </div>
              {evidenceCount > 0 ? (
                <div className="source-chip-row" aria-label="Evidence source domains">
                  {evidenceSources.slice(0, 8).map((source, index) => (
                    <a key={`${source.url ?? "source"}-${index}`} href={source.url} target="_blank" rel="noreferrer">
                      {sourceHost(source.url)}
                    </a>
                  ))}
                </div>
              ) : null}
              <div className="evidence-list">
                {evidenceSources.map((source, index) => (
                  <article className="evidence-item" key={`${source.url ?? "source"}-${index}`}>
                    <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url || `Source ${index + 1}`}</a>
                    <p>{source.snippet || source.text || "No snippet stored."}</p>
                  </article>
                ))}
                {evidenceCount === 0 ? (
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

      <section className="panel image-admin-panel">
        <div className="panel-heading">
          <div>
            <h2>Profile Images</h2>
            <p>Upload a reviewed machine picture and attach it to the trusted profile.</p>
          </div>
        </div>

        <div className="image-admin-grid">
          <label className="field">
            <span>Machine</span>
            <select value={selectedMachineSlug} onChange={(event) => setSelectedMachineSlug(event.target.value)}>
              {machines.map((machine) => (
                <option key={machine.slug} value={machine.slug}>
                  {machine.display_name}{machine.has_image ? " · has image" : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Image file</span>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => setImageFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <button className="primary-button" onClick={() => void uploadMachineImage()} disabled={Boolean(busy) || !selectedMachineSlug || !imageFile}>
            {busy === "image" ? "Uploading" : "Upload image"}
          </button>
        </div>
      </section>
    </section>
  );
}
