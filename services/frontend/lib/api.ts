export type ShotFormValues = {
  user_id: string;
  video_s3_key?: string;
  machine?: string;
  grinder?: string;
  uses_built_in_grinder?: boolean;
  dose_g?: number;
  yield_g?: number;
  grind_setting?: string;
  roast_level?: string;
  taste?: string;
  total_shot_seconds?: number;
  timing_confidence?: number;
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
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== "")
  ) as ShotFormValues;
}
