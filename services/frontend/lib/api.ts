export type ShotFormValues = {
  user_id: string;
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

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type ChatResponse = {
  response: string;
  needs_shot_analysis: boolean;
  system_prompt: string;
  shot_context?: ShotFormValues | null;
  analysis_result?: AnalyzeShotResponse | null;
  next_field?: string | null;
  missing_fields: string[];
};

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

const API_BASE_URL = process.env.NEXT_PUBLIC_AGENT_API_URL ?? "http://127.0.0.1:8000";

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
