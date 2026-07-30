# DialedIN Audio Shot Timing Agent Specification

## 1. Problem Statement

Home espresso users struggle to understand why a shot runs too fast, too slow, sour, bitter, watery, or inconsistent. A key diagnostic signal is total shot time, but users often measure it manually and inconsistently. DialedIN solves this by letting a user upload a video of an espresso shot and using the machine sound to estimate when the pump or machine starts and stops.

The first version focuses on the most important timing value for dial-in decisions: total shot time. It combines this timing with user-provided machine, grinder, dose, yield, beans, and grind setting to recommend the next adjustment.

## 2. MVP Goal

The MVP proves this core flow:

1. User uploads an espresso shot video.
2. The system extracts the audio track from the video.
3. Audio analysis detects the machine/pump start time.
4. Audio analysis detects the machine/pump stop time.
5. Timing logic calculates total shot time.
6. The agent asks for missing espresso context.
7. The agent calls MCP tools to analyze timing and recommend a grind adjustment.
8. The frontend shows total shot time, confidence, recommendation, and explanation.

The MVP does not train a visual model and does not promise a perfect grind setting. It recommends the next likely adjustment and explains what to keep fixed for the next test shot.

## 3. Audio Timing Model

The first timing system is audio-first and heuristic-based. It detects the change from quiet/background sound to active machine/pump sound, then detects when that sustained machine sound stops.

Audio analysis returns:

- `machine_start_time`
- `machine_stop_time`
- `total_shot_seconds`
- `start_confidence`
- `stop_confidence`
- `audio_method`: `heuristic` for the MVP
- `warnings`: human-readable notes when the signal is noisy or uncertain

A trained audio classifier can be added later using short audio windows labeled `pump_off` and `pump_on`, but it is not required for the MVP.

## 4. Timing Definitions

The system calculates:

- `machine_start_time`: first sustained pump/machine sound detected in the audio track.
- `machine_stop_time`: point where the sustained pump/machine sound ends.
- `total_shot_seconds`: `machine_stop_time - machine_start_time`.

The response reports whether timing came from automatic audio detection or manual correction. If confidence is low, the frontend lets the user correct `machine_start_time` and `machine_stop_time`.

The MVP does not calculate `first_flow_time`, `startup_delay_seconds`, or `visible_flow_seconds`. Those are future visual-analysis improvements.

## 5. Architecture

The system is split into small services:

- `frontend`: Next.js web UI for video upload, shot context form, timing correction, and results.
- `agent`: FastAPI service with LangGraph. It owns the user conversation, follows a system prompt, and calls MCP tools.
- `espresso-mcp`: custom MCP server exposing audio analysis, timing, machine profile, and grind recommendation tools.
- `modeling`: local scripts for audio extraction experiments, audio analysis tests, and future model research.
- `storage`: S3 for uploaded videos, extracted audio, analysis reports, and future model artifacts.
- `database`: DynamoDB for shot history, user sessions, and analysis results.
- `observability`: Prometheus, Grafana, and logs for metrics, dashboards, and debugging.

The MVP processes videos synchronously inside `espresso-mcp`. A separate async `video-worker` with SQS is a future improvement if processing becomes slow or concurrent uploads become a bottleneck.

## 6. Data Flow

1. User opens the frontend.
2. User uploads a shot video and enters known shot details.
3. Frontend sends the video and metadata to the agent API.
4. Agent stores the video in S3 or local development storage.
5. Agent calls `espresso-mcp.analyze_audio_timing`.
6. `espresso-mcp` extracts the audio track.
7. `espresso-mcp` computes short-window audio energy or spectrogram-like features.
8. `espresso-mcp` detects machine/pump start and stop.
9. `espresso-mcp` calculates total shot time and confidence.
10. Agent asks the user for missing machine, grinder, dose, yield, grind setting, roast, or taste details.
11. Agent calls `espresso-mcp.recommend_grind_adjustment`.
12. Agent returns a final explanation with total shot time, confidence, recommendation, and next test instructions.
13. Result is saved to the database and shown in the frontend.

If audio confidence is low, the frontend lets the user correct the detected `machine_start_time` and `machine_stop_time` before the recommendation is finalized.

## 7. MCP Tools

The custom `espresso-mcp` server exposes:

- `extract_audio_track(video_s3_key)`: extracts the audio track from the uploaded video.
- `detect_machine_audio_window(audio_s3_key)`: detects machine/pump start and stop from audio.
- `calculate_total_shot_time(machine_start_time, machine_stop_time)`: returns total shot time.
- `analyze_audio_timing(video_s3_key)`: combines audio extraction, detection, confidence, and timing.
- `recommend_grind_adjustment(shot_context)`: returns a structured recommendation.
- `get_machine_profile(machine_name)`: returns machine-specific notes and target timing range.
- `save_shot_result(user_id, result)`: saves the analysis.
- `compare_previous_shots(user_id, current_result)`: compares current shot with previous attempts.

An optional `observability-mcp` can expose Prometheus and log-query tools for demo and debugging.

## 8. Machine Profiles

The recommendation engine uses machine profiles so it does not apply one generic rule to every espresso machine. The MVP supports 3-5 popular machines plus a generic fallback.

Initial profiles:

- Breville Barista Express
- Breville Bambino or Bambino Plus
- Gaggia Classic Pro
- Rancilio Silvia
- DeLonghi Dedica
- Generic Espresso Machine

Each profile includes:

- `machine_name`
- `aliases`
- `target_total_shot_seconds`
- `has_preinfusion`
- `pump_type`
- `portafilter_mm`
- `grind_adjustment_notes`
- `source_urls`

Machine profiles are manually curated from official manufacturer documentation first, then retailer specifications or community notes when official information is missing. User shot history can improve these profiles later.

## 9. Recommendation Rules

The recommendation engine starts as rule-based:

- Total shot under 20 seconds: likely too fast; grind finer unless there are channeling signs from the user.
- Total shot between 20 and 35 seconds: timing is plausible; use taste, yield, machine profile, and user context.
- Total shot over 35 seconds: likely too slow; grind coarser.
- Fast shot plus sour or watery taste: grind finer.
- Slow shot plus bitter or harsh taste: grind coarser.
- Normal timing plus bad taste: suggest one controlled change, such as adjusting yield, temperature, or puck prep depending on user context.

The agent should recommend one next change and tell the user what to keep fixed.

## 10. Agent System Prompt

The agent system prompt defines DialedIN as an espresso coach, not a generic chatbot. It must:

- Explain that recommendations are next-step guidance, not guaranteed perfect grind settings.
- Use MCP tool results for timestamps and recommendation data.
- Ask for missing machine, grinder, dose, yield, roast, grind setting, or taste details.
- Avoid inventing timing values or machine specifications.
- Recommend one main adjustment at a time.
- Tell the user what to keep fixed on the next shot.
- Mention low confidence and ask the user to confirm timing when needed.

## 11. Dataset Label Schema

The first dataset uses a CSV file with these columns:

```text
video_id,machine_start_time,machine_stop_time,machine,grinder,dose_g,yield_g,grind_setting,roast_level,taste
```

The timestamp values are seconds from the start of the video. The existing `first_flow_time` labels can remain in older files for future visual work, but the audio-only MVP only requires machine start and machine stop.

## 12. Future Visual Analysis

Visual analysis is explicitly out of MVP scope. Future versions can add:

- frame extraction
- first coffee flow detection
- flow end visual confirmation
- startup delay calculation
- channeling or spraying detection
- crema/blonding analysis
- Ultralytics image classification or object detection

These future features can improve explanation quality but are not required for the first working agent.

## 13. Error Handling

The system handles:

- Unsupported file type: return a clear upload error.
- Video too long or too large: reject with size/duration guidance.
- Missing audio track: ask the user to manually enter start and stop times.
- Noisy audio or low confidence: ask the user to confirm or manually adjust detected times.
- Missing machine/grinder/dose/yield: ask follow-up questions.
- MCP timeout: retry once, then return a graceful error.
- LLM failure: return the structured timing result with a basic rule-based recommendation.
- S3/database failure: report that analysis completed but saving failed, when possible.

## 14. Testing Strategy

Unit tests cover:

- Audio extraction interface.
- Audio start/stop detection heuristic.
- Total shot time calculation.
- Grind recommendation rules.
- Machine profile lookup.
- MCP tool request/response schemas.
- Agent behavior when user metadata is missing.

Integration tests cover:

- Agent calling the MCP server through real MCP transport.
- A sample audio fixture producing a timing result.
- End-to-end API request returning a recommendation.

Audio evaluation measures:

- Machine start timestamp error.
- Machine stop timestamp error.
- Total shot time error.
- Start/stop confidence.

Initial success criteria:

- Machine start detected within 2 seconds on videos where pump sound is clear.
- Machine stop detected within 2 seconds on videos where pump stop is clear.
- Total shot time within 3 seconds of manual labels for at least 10 of the first 13 videos.
- Agent returns a useful recommendation for at least three demo shot scenarios: fast, normal, and slow.

The repository also contains `docs/test-plan.md`, which describes test types, commands, success criteria, and manual demo checks.

## 15. Deployment

The final course deployment uses:

- Docker images for each service.
- Kubernetes on AWS EC2.
- `dev` and `prod` namespaces.
- ClusterIP services for internal communication.
- Port-forward or ingress for demo access.
- Liveness and readiness probes.
- Resource requests and limits.
- HPA for frontend, agent, and espresso MCP service.
- Terraform for AWS resources: EC2, S3, database, IAM, and optional SQS.

## 16. Observability

Metrics include:

- `shot_analysis_requests_total`
- `audio_processing_duration_seconds`
- `audio_start_confidence`
- `audio_stop_confidence`
- `total_shot_time_seconds`
- `mcp_tool_errors_total`
- `agent_request_latency_seconds`
- `failed_audio_analysis_total`

Grafana dashboard shows:

- analyzed shots over time
- average audio processing duration
- failed analysis count
- average start/stop confidence
- total shot time distribution
- agent latency
- MCP error count

Alerts include:

- high analysis failure rate
- low average audio confidence
- high MCP tool error rate
- high agent request latency
- audio processing duration above threshold

Healthy means the API is reachable, MCP tools respond, audio timing completes within the expected time, error rate stays low, and audio confidence is high enough for recommendations.

## 17. Demo Scenario

The live demo uses a controlled espresso shot video. The user uploads the video, enters machine/grinder/shot details, and the system returns:

- machine start time
- machine stop time
- total shot time
- grind recommendation
- confidence and explanation

The presentation also shows the MCP tool call, Kubernetes services, CI pipeline, and Grafana dashboard.
