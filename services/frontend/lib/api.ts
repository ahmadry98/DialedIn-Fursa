export type ShotFormValues = {
  user_id: string;
  pending_gear_type?: string | null;
  pending_gear_name?: string | null;
  pending_gear_confidence?: string | null;
  video_s3_key?: string | null;
  machine?: string | null;
  grinder?: string | null;
  uses_built_in_grinder?: boolean;
  dose_g?: number | null;
  yield_g?: number | null;
  grind_setting?: string | null;
  roast_level?: string | null;
  taste?: string | null;
  total_shot_seconds?: number | null;
  timing_confidence?: number | null;
  requires_manual_confirmation?: boolean;
};

export type TimingResult = {
  source_path?: string;
  machine_start_time: number | null;
  machine_stop_time: number | null;
  total_shot_seconds: number | null;
  start_confidence?: number;
  stop_confidence?: number;
  audio_method?: string;
  requires_manual_confirmation?: boolean;
  confirmation_reason?: string | null;
  warnings?: string[];
};

export type AnalyzeShotResponse = {
  timing: TimingResult;
  machine_profile: Record<string, unknown>;
  recommendation: {
    recommendation: string;
    adjustment: string;
    reason: string;
    confidence: string;
    keep_fixed: string[];
    needs_more_info: string[];
    target_range_seconds: [number, number];
    calculation_explanation?: string[];
    confidence_reasons?: string[];
    exact_grind_setting?: {
      grinder_profile?: { grinder_name?: string };
      current_setting?: string | number | null;
      suggested_setting?: string | number | null;
      setting_label?: string | null;
      adjustment_size?: string | null;
      seconds_gap?: number | null;
      estimated_small_steps?: number | null;
      seconds_per_small_step_estimate?: number | null;
      notes?: string | null;
    } | null;
  };
  missing_fields: string[];
  profile_candidates?: Array<{
    type: string;
    name_entered: string;
    status: string;
    seen_count: number;
  }>;
  saved_result: Record<string, unknown>;
  previous_comparison: Record<string, unknown>;
  message: string;
};


export type MediaUploadTarget = {
  media_key: string;
  upload_url: string;
  method: string;
  headers: Record<string, string>;
  storage_mode: "local" | "s3" | string;
  expires_in_seconds: number;
};

export type MediaRegisterResponse = {
  media_key: string;
  video_s3_key?: string | null;
  media_kind: string;
  storage_mode: string;
  content_type?: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  image_base64?: string | null;
  image_media_type?: string | null;
  image_kind?: "machine" | "grinder" | null;
};

export type ChatResponse = {
  response: string;
  needs_shot_analysis: boolean;
  system_prompt: string;
  shot_context?: ShotFormValues | null;
  analysis_result?: AnalyzeShotResponse | null;
  next_field?: string | null;
  missing_fields: string[];
  image_guess?: {
    gear_type?: string;
    name?: string | null;
    confidence?: string;
    reason?: string;
  } | null;
};

export type MachineSummary = {
  slug: string;
  display_name: string;
  name?: string;
  has_image?: boolean;
  image?: Record<string, unknown> | null;
  image_url?: string | null;
};

export type MachinesResponse = {
  count: number;
  machines: MachineSummary[];
};

export type ProfileCandidate = {
  candidate_key: string;
  type: "machine" | "grinder" | string;
  name_entered: string;
  status: string;
  created_at?: string;
  last_seen_at?: string;
  seen_count?: number;
  user_ids?: string[];
  latest_context?: Record<string, unknown>;
  research_prompt?: string;
  draft_profile?: Record<string, unknown> | null;
  draft_validation?: {
    is_valid?: boolean;
    missing_fields?: string[];
    warnings?: string[];
  } | null;
  research_quality?: {
    score?: number;
    status?: string;
    threshold?: number;
    reasons?: string[];
    warnings?: string[];
  } | null;
  research_evidence?: {
    sources?: Array<{ url?: string; title?: string; snippet?: string; text?: string }>;
    text?: string;
  } | null;
  review_notes?: string[];
};

export type ProfileCandidatesResponse = {
  count: number;
  candidates: ProfileCandidate[];
};
export async function listMachines(): Promise<MachinesResponse> {
  const response = await fetch(`${API_BASE_URL}/machines`, { cache: "no-store" });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Machine request failed" }));
    throw new Error(error.detail ?? "Machine request failed");
  }

  return response.json();
}

export async function attachMachineProfileImage(
  machineSlug: string,
  payload: {
    media_key: string;
    storage_mode: string;
    content_type?: string | null;
    source_url?: string | null;
    license_or_source_type?: string;
    status?: string;
    review_notes?: string | null;
  }
): Promise<{ machine: MachineSummary }> {
  const response = await fetch(`${API_BASE_URL}/machines/${encodeURIComponent(machineSlug)}/image`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Machine image update failed" }));
    throw new Error(error.detail ?? "Machine image update failed");
  }

  return response.json();
}

export async function listProfileCandidates(): Promise<ProfileCandidatesResponse> {
  const response = await fetch(`${API_BASE_URL}/profile-candidates`, { cache: "no-store" });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Candidate request failed" }));
    throw new Error(error.detail ?? "Candidate request failed");
  }

  return response.json();
}

export async function updateProfileCandidate(
  candidateKey: string,
  payload: { draft_profile?: Record<string, unknown>; review_notes?: string[]; status?: string }
): Promise<{ candidate: ProfileCandidate }> {
  const response = await fetch(`${API_BASE_URL}/profile-candidates/${encodeURIComponent(candidateKey)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Candidate update failed" }));
    throw new Error(error.detail ?? "Candidate update failed");
  }

  return response.json();
}

export async function deleteProfileCandidate(candidateKey: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/profile-candidates/${encodeURIComponent(candidateKey)}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Candidate delete failed" }));
    throw new Error(error.detail ?? "Candidate delete failed");
  }

  return response.json();
}

export async function rerunProfileCandidateResearch(candidateKey: string): Promise<{ results: Record<string, unknown>[] }> {
  const response = await fetch(`${API_BASE_URL}/profile-candidates/${encodeURIComponent(candidateKey)}/research`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Candidate research failed" }));
    throw new Error(error.detail ?? "Candidate research failed");
  }

  return response.json();
}

export async function promoteProfileCandidate(candidateKey: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/profile-candidates/${encodeURIComponent(candidateKey)}/promote`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Candidate promotion failed" }));
    throw new Error(error.detail ?? "Candidate promotion failed");
  }

  return response.json();
}

export async function chatWithCoach(payload: {
  messages: ChatMessage[];
  shot_context?: ShotFormValues | null;
}): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      messages: payload.messages,
      shot_context: payload.shot_context ? cleanPayload(payload.shot_context) : undefined,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Coach request failed" }));
    throw new Error(error.detail ?? "Coach request failed");
  }

  return response.json();
}

const API_BASE_URL = process.env.NEXT_PUBLIC_AGENT_API_URL ?? defaultApiBaseUrl();

function defaultApiBaseUrl() {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host && host !== "localhost" && host !== "127.0.0.1") {
      return `http://${host}:8000`;
    }
  }
  return "http://127.0.0.1:8000";
}

export async function createMediaUploadUrl(payload: {
  filename: string;
  content_type: string;
  media_kind: "shot_video" | "machine_photo" | "grinder_photo";
  user_id: string;
}): Promise<MediaUploadTarget> {
  const response = await fetch(`${API_BASE_URL}/media/upload-url`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Could not prepare media upload" }));
    throw new Error(error.detail ?? "Could not prepare media upload");
  }

  return response.json();
}

export async function uploadFileToMediaTarget(file: File, target: MediaUploadTarget): Promise<void> {
  const response = await fetch(target.upload_url, {
    method: target.method || "PUT",
    headers: target.headers,
    body: file,
  });

  if (!response.ok) {
    throw new Error("Could not upload the video. Check S3/local upload permissions and try again.");
  }
}

export async function registerMediaUpload(payload: {
  media_key: string;
  media_kind: "shot_video" | "machine_photo" | "grinder_photo";
  storage_mode: string;
  content_type?: string | null;
}): Promise<MediaRegisterResponse> {
  const response = await fetch(`${API_BASE_URL}/media/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Could not register uploaded media" }));
    throw new Error(error.detail ?? "Could not register uploaded media");
  }

  return response.json();
}

export async function analyzeShot(payload: ShotFormValues): Promise<AnalyzeShotResponse> {
  const response = await fetch(`${API_BASE_URL}/analyze-shot`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(cleanPayload(payload)),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Agent request failed" }));
    throw new Error(error.detail ?? "Agent request failed");
  }

  return response.json();
}

function cleanPayload(payload: ShotFormValues): ShotFormValues {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ) as ShotFormValues;
}
