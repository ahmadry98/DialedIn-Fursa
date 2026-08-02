# DialedIN Espresso Shot Review Specification

## 1. Problem Statement

Home espresso users struggle to understand why a shot runs too fast, too slow, sour, bitter, watery, or inconsistent. A key diagnostic signal is total shot time, but users often measure it manually and inconsistently. DialedIN acts as a guided espresso coach: it asks for the machine, grinder, dose, grind setting, roast, taste, and shot video or manual timing, estimates the machine/pump start and stop from audio, combines that timing with espresso context, and recommends the next grind adjustment.

The product also learns from unknown equipment. When the user enters a machine or grinder that is not in the curated profiles, DialedIN captures it as a research candidate, gathers source evidence, asks Bedrock to draft a profile, and keeps that draft pending human review before it becomes trusted data.

## 2. MVP Goal

The MVP proves this core flow:

1. User chats with DialedIN instead of filling a large form.
2. The coach asks for missing context one step at a time: machine, grinder or built-in grinder choice, dose, optional yield, grind setting, roast level, taste notes, and shot video or manual timing.
3. The system extracts/analyzes audio to detect machine start and stop when a video path is provided.
4. Timing logic calculates total shot time and confidence.
5. The backend uses curated machine and grinder profiles when available.
6. Recommendation rules return one next action, including exact next grinder setting when the grinder profile supports it.
7. Unknown gear is captured into a candidate queue.
8. Bedrock can research unknown gear using web evidence and create a draft profile.
9. Human review promotes approved drafts into trusted profile JSON.
10. The frontend shows timing, confidence, recommendation, missing fields, and unknown gear candidate state inside the chat.

The MVP does not train a visual model. It is audio-first, rule-based for recommendation decisions, and LLM-assisted for profile research/drafting and, later, natural chat or image recognition. Chat wording must not override deterministic timing or grind-adjustment logic.

## 3. Audio Timing Model

The first timing system is audio-first and heuristic-based. It detects the change from quiet/background sound to active machine/pump sound, then detects when that sustained machine sound stops.

Audio analysis returns:

- `machine_start_time`
- `machine_stop_time`
- `total_shot_seconds`
- `start_confidence`
- `stop_confidence`
- `audio_method`
- `requires_manual_confirmation`
- `confirmation_reason`
- `warnings`

A trained audio classifier can be added later using short audio windows labeled `pump_off` and `pump_on`, but it is not required for the MVP.

## 4. Timing Definitions

The system calculates:

- `machine_start_time`: first sustained pump/machine sound detected in the audio track.
- `machine_stop_time`: point where sustained pump/machine sound ends.
- `total_shot_seconds`: `machine_stop_time - machine_start_time`.

The response reports whether timing came from automatic audio detection, manual total-time entry, or manual correction. If confidence is low, the frontend shows a clear warning, lets the user correct start and stop times, and re-runs recommendation from confirmed timing.

The MVP does not calculate `first_flow_time`, `startup_delay_seconds`, or `visible_flow_seconds`. Those are future visual-analysis improvements.

## 5. Current Architecture

The system is split into small services/modules:

- `services/frontend`: Next.js web UI. The current form proves the analysis workflow; the next UX layer is a chat-first coach for guided data collection, timing correction, and results.
- `services/agent`: FastAPI service exposing `/analyze-shot`, `/chat`, `/health`, and `/metrics`.
- `services/espresso_mcp`: MCP-compatible tool layer for audio timing, recommendations, machine profiles, grinder profiles, unknown gear capture, profile research, and profile promotion helpers.
- `modeling`: local scripts/tests for audio experiments and evaluation.
- `docs`: project specification, implementation plan, and test plan.

Planned deployment components remain:

- S3 for uploaded videos, extracted audio, and analysis artifacts.
- DynamoDB for persistent shot history and user analysis results.
- Docker/Kubernetes on AWS EC2 for course deployment.
- Prometheus/Grafana for metrics and debugging.

The current MVP processes videos synchronously. A separate async worker/SQS flow is future work if jobs become slow or concurrent. The chat-first coach uses LangGraph to orchestrate context loading, message parsing, missing-field routing, shot analysis, and response assembly. The underlying shot analysis still calls deterministic `espresso_mcp` functions directly for timing, profile lookup, recommendation, unknown gear capture, save, and comparison.

## 6. Data Flow

1. User opens the frontend chat.
2. User can greet or ask general espresso questions.
3. Coach keeps a conversation state for machine, grinder, built-in grinder choice, dose, optional yield, grind setting, roast, taste, timing/video, and confirmations.
4. Coach asks the next missing question naturally.
5. User enters typed values, chooses known gear, or provides a video path/manual timing.
6. Frontend sends the accumulated shot context to the FastAPI agent when enough data exists.
7. Agent calls audio timing if a video path is provided, or uses manual total time.
8. Agent looks up the machine profile.
9. Agent builds recommendation context, including `uses_built_in_grinder` when relevant.
10. Agent calls deterministic recommendation logic.
11. Recommendation logic validates known grinder settings and calculates exact next settings when possible.
12. Unknown external machines/grinders are captured as profile candidates.
13. Built-in grinder machines do not create fake separate grinder candidates.
14. If profile research autorun is enabled, the agent starts a background Bedrock profile research worker.
15. Worker collects web evidence, calls Bedrock, and attaches a draft profile to the candidate.
16. Human reviewer edits/approves the draft.
17. Profile promoter copies the approved draft into trusted machine/grinder profiles.

## 7. MCP / Tool Layer

The custom `espresso_mcp` layer exposes:

- `extract_audio_track(video_s3_key)`
- `detect_machine_audio_window(audio_s3_key)`
- `calculate_total_shot_time(machine_start_time, machine_stop_time)`
- `analyze_audio_timing(video_s3_key)`
- `recommend_grind_adjustment(shot_context)`
- `get_machine_profile(machine_name)`
- `save_shot_result(user_id, result)`
- `compare_previous_shots(user_id, current_result)`
- `capture_unknown_gear(user_id, machine, grinder, shot_context)`
- `list_profile_candidates()`
- `prepare_profile_research(candidate_key)`
- `attach_draft_profile(candidate_key, draft_profile)`

The FastAPI agent calls these Python functions directly for shot analysis. The chat coach wraps the conversation flow in LangGraph and calls the same tool-backed analysis path when enough structured context is available. Future work can switch to real MCP transport without changing response shape.

## 8. Chat-First Coach UX

The current user experience turns the working analysis form into a guided espresso coach. The chat should feel natural, but it should still collect structured state and call the same deterministic analysis tools.

Conversation state includes:

- `machine`
- `grinder`
- `uses_built_in_grinder`
- `dose_g`
- `yield_g`
- `grind_setting`
- `roast_level`
- `taste`
- `video_s3_key` or local video path
- manual timing fields when the user does not want video/audio
- confirmation state for guessed gear or low-confidence timing

The chat layer may use an LLM for normal replies, extracting values from messy text, and eventually interpreting images. It must not invent shot timing, grinder math, or verified machine facts. The first implementation uses LangGraph with deterministic extraction plus an optional Claude Haiku/Bedrock extraction node for natural multi-field messages. If Bedrock is disabled or denied by IAM, the graph falls back to deterministic extraction. When enough structured context is collected, the graph calls the existing `/analyze-shot` flow and renders the result conversationally.


## 9. Machine Profiles

Machine profiles prevent the app from treating all machines the same. They include sourced technical facts and conservative brew defaults.

Profile shape:

```json
{
  "machine_name": "Meraki",
  "aliases": ["meraki", "meraki espresso machine"],
  "specs": {
    "portafilter_mm": 58,
    "pump_type": "rotary",
    "pressure_type": "9 bar rotary pump with dual boiler system",
    "has_preinfusion": true
  },
  "brew_defaults": {
    "target_total_shot_seconds": [25, 32],
    "target_visible_flow_seconds": [20, 28],
    "typical_startup_delay_seconds": null
  },
  "grind_adjustment_notes": "...",
  "sources": {
    "portafilter_mm": ["https://..."],
    "pump_type": ["https://..."],
    "pressure_type": ["https://..."],
    "has_preinfusion": ["https://..."]
  }
}
```

Current profiles include common home machines plus a generic fallback. Newly promoted example: Meraki, with built-in grinder notes.

## 10. Grinder Profiles And Exact Settings

Grinder profiles allow the app to return exact next settings instead of vague advice like “1-2 steps finer.”

Each grinder profile includes:

- `grinder_name`
- `aliases`
- `setting_type`: `numeric_integer` or `numeric_decimal`
- `lower_is_finer`
- `small_step`, `medium_step`, `large_step`
- `min_setting`, `max_setting`
- `espresso_range`
- `data_confidence`
- `notes`
- `seconds_per_small_step_estimate`
- `max_recommended_small_steps`
- `source_urls`

When the grinder is known, the app validates settings and calculates the next setting. The exact-setting calculation uses the shot-time gap plus `seconds_per_small_step_estimate` when the grinder profile has one. For example, if a shot is 10 seconds fast and the grinder estimate is 2.5 seconds per small step, the app recommends about 4 small steps finer and converts that into the grinder's numeric setting. When unknown, it uses `Generic Numeric Grinder` as a conservative fallback. Built-in grinders are represented by `uses_built_in_grinder=true`; they use generic numeric logic until a machine-specific built-in grinder profile is verified.

## 11. Built-In Grinder Handling

Some machines, such as Meraki or Breville Barista Express, have built-in grinders. The frontend has a `Built-in` checkbox next to the grinder field.

When checked:

- The grinder input is disabled and displayed as `Built-in grinder`.
- The request sends `uses_built_in_grinder: true`.
- The backend removes `grinder` from missing fields if machine is provided.
- Unknown gear capture researches only the machine, not a fake separate grinder.
- Recommendation still uses the entered grind setting.

This prevents incorrect candidates like `grinder:meraki`.

## 12. Unknown Gear Research Workflow

Unknown equipment is handled through a reviewable learning loop:

1. `capture_unknown_gear` saves unknown machines/grinders to `profile_candidates.json`.
2. `profile_research_worker` selects candidates with `needs_research`.
3. `profile_web_evidence` searches/fetches official or likely official pages and extracts compact evidence.
4. Bedrock receives the expected schema, observed context for disambiguation only, and source evidence.
5. Bedrock returns JSON only.
6. `attach_draft_profile` validates the shape and stores `draft_profile`, `draft_validation`, and `research_evidence`.
7. Human reviewer edits or approves the draft.
8. `profile_promoter` promotes the reviewed draft into trusted profile JSON.

Important rule: observed app context, such as a user-entered grind setting, must not be treated as manufacturer data or a typical setting.

Local env controls:

```env
PROFILE_RESEARCH_AUTORUN=true
PROFILE_RESEARCH_AUTORUN_LIMIT=1
PROFILE_RESEARCH_WEB_EVIDENCE=true
MODEL=bedrock/openai.gpt-oss-20b-1:0
AWS_REGION=us-east-1
CHAT_LLM_EXTRACTION=true
CHAT_LLM_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

## 13. Recommendation Rules

The recommendation engine is deterministic and explainable:

- Shot faster than target: grind finer unless channeling/puck prep signs dominate.
- Shot slower than target: grind coarser.
- Shot inside target: use taste/context to decide whether to keep settings, increase extraction, or reduce extraction.
- Sour, watery, thin: usually under-extraction.
- Bitter, harsh, dry: usually over-extraction.
- Channeling/spraying: fix puck prep before changing grind.

The app recommends one primary next change and lists what to keep fixed. When it calculates an exact grinder setting, it also explains the timing gap, grinder sensitivity estimate, estimated number of small steps, and recommendation confidence reasons. Yield is optional because many users do not weigh output, but recommendations improve when yield is available.

## 14. Agent System Prompt

The agent system prompt defines DialedIN as an espresso coach. It must:

- Use tool results or user-confirmed timing, not invented timestamps.
- Explain recommendations as next-step guidance.
- Ask for missing context when needed.
- Avoid inventing machine or grinder specifications.
- Recommend one main adjustment at a time.
- Tell the user what to keep fixed.
- Mention low confidence and ask the user to confirm timing when needed.

## 15. Dataset Label Schema

The first dataset uses a CSV file with these columns:

```text
video_id,machine_start_time,machine_stop_time,machine,grinder,dose_g,yield_g,grind_setting,roast_level,taste,notes
```

The required fields for audio evaluation are `video_id`, `machine_start_time`, and `machine_stop_time`. Other fields can be empty if the video does not provide them.


## 16. CI/CD Workflow

GitHub Actions protects the branch workflow before review and merge. The current CI runs on pull requests to `main`/`dev`, pushes to `main`/`dev`, and manual workflow dispatch.

The CI workflow includes:

- Python dependency install for `modeling`, `services/agent`, and `services/espresso_mcp`.
- Python tests for audio timing, profiles, recommendations, profile research, and agent behavior.
- Frontend `npm ci`, TypeScript checking, and production build from `services/frontend`.
- `PROFILE_RESEARCH_AUTORUN=false` during tests so CI does not call Bedrock or mutate candidate research state.

Deployment/CD is future work and should be added after the deployment target is finalized. The profile research worker can later get a separate manual workflow using GitHub secrets for AWS credentials, but normal PR CI should remain deterministic and cheap.

## 17. Future LangGraph Enhancements

LangGraph is now part of the chat-first MVP. Future work can make the graph smarter, more persistent, and easier to inspect.

Future graph enhancements can use nodes such as:

1. Receive shot request.
2. Detect or accept timing.
3. Look up machine and grinder profiles.
4. Run deterministic recommendation logic.
5. Capture unknown gear candidates.
6. Optionally trigger Bedrock profile research.
7. Save result and compare previous shots.
8. Assemble final response.

These enhancements should reuse the existing `espresso_mcp` functions rather than replacing them. Recommendation decisions should remain deterministic unless the project intentionally changes that requirement.

## 18. Future Visual And Image Recognition

Visual analysis is out of current MVP scope. Future versions can add:

- Machine photo recognition.
- Grinder photo recognition.
- User confirmation before accepting image guesses.
- Frame extraction.
- First coffee flow detection.
- Flow end visual confirmation.
- Startup delay calculation.
- Channeling/spraying detection.
- Crema/blonding analysis.
- Ultralytics image classification or object detection.


## 19. Mobile And PWA Direction

DialedIN should become phone-friendly before becoming a native desktop or mobile app. The near-term target is a responsive web/PWA experience because users naturally record espresso videos on their phones.

Priorities:

- Mobile-first chat layout.
- Camera/photo/video upload affordances.
- PWA manifest and installable app metadata.
- Keep desktop web usable for development and demos.
- Defer desktop wrappers such as Electron/Tauri until the web/PWA experience is stable.

## 20. Error Handling

The system handles:

- Unsupported or missing file path.
- Video path pointing to a directory.
- Missing audio track.
- Noisy audio or low confidence.
- Missing machine/grinder/dose/grind setting/roast/taste.
- Invalid known grinder setting.
- Bedrock or AWS failure during background research.
- Web evidence failure.
- Save/compare failure in future persistent storage.

Background profile research failures should not break shot analysis.

## 21. Testing Strategy

Unit tests cover:

- Audio extraction/timing logic.
- Recommendation rules.
- Machine profile lookup.
- Grinder profile lookup and exact setting calculation.
- Unknown profile candidate capture.
- Web evidence collection with mocked search/fetch.
- Bedrock research worker with mocked Bedrock.
- Profile promotion.
- Agent API behavior.

Integration/manual checks cover:

- Frontend to agent request.
- Video/audio timing result.
- Manual timing correction.
- Unknown gear candidate creation.
- Bedrock draft generation.
- Reviewed profile promotion.

Current verified local checks include backend pytest suite and Next.js production build.

## 22. Deployment And Observability

Final course deployment target:

- Docker images for frontend, agent, and espresso MCP.
- Kubernetes on AWS EC2.
- `dev` and `prod` namespaces if required by the course workflow.
- S3 and DynamoDB via Terraform.
- Prometheus/Grafana for request, audio, MCP, and failure metrics.
- GitHub Actions for tests, build, and deployment.
