# DialedIN Shot Timing Agent Specification

## 1. Problem Statement

Home espresso users struggle to understand why a shot runs too fast, too slow, sour, bitter, watery, or inconsistent. A key diagnostic signal is shot timing, but users often measure it manually and inconsistently. Some count from the first coffee drop, while others count from button press. Machines with pre-infusion or startup delay make this even more confusing.

DialedIN solves this by letting a user upload a video of an espresso shot. The system detects when the machine starts, when coffee first appears, and when flow ends. It then combines those timings with user-provided machine, grinder, beans, dose, yield, and grind setting to recommend the next adjustment.

## 2. MVP Goal

The MVP proves this core flow:

1. User uploads an espresso shot video.
2. The system extracts frames from the video.
3. A trained Ultralytics image-classification model classifies each frame into shot states.
4. Timing logic calculates machine start, first flow, flow end, startup delay, visible flow time, and total shot time.
5. The agent asks for missing espresso context.
6. The agent calls MCP tools to analyze timing and recommend a grind adjustment.
7. The frontend shows the timing breakdown, recommendation, confidence, and explanation.

The MVP does not promise a perfect grind setting. It recommends the next likely adjustment and explains what to keep fixed for the next test shot.

## 3. Shot State Model

The first trained model is an Ultralytics image-classification model. It classifies extracted video frames into four classes:

- `idle`: machine has not started.
- `machine_started_no_flow`: machine/pump appears active but coffee is not visible yet.
- `coffee_flowing`: visible espresso is flowing into the cup.
- `shot_finished`: flow has stopped or only insignificant dripping remains.

The first version should use a consistent camera angle where the button, light, lever, portafilter, cup, and espresso stream area are visible. Audio detection can be added later, but the MVP focuses on visual classification.

## 4. Timing Definitions

The system calculates:

- `machine_start_time`: first stable frame classified as `machine_started_no_flow` after `idle`.
- `first_flow_time`: first stable frame classified as `coffee_flowing`.
- `flow_end_time`: first stable frame classified as `shot_finished` after coffee has flowed.
- `startup_delay_seconds`: `first_flow_time - machine_start_time`.
- `visible_flow_seconds`: `flow_end_time - first_flow_time`.
- `total_shot_seconds`: `flow_end_time - machine_start_time`.

The agent reports both visible flow time and total shot time because machines differ in pre-infusion and startup behavior.

## 5. Architecture

The system is split into small services:

- `frontend`: Next.js web UI for video upload, shot context form, and results.
- `agent`: FastAPI service with LangGraph. It owns the user conversation and calls MCP tools.
- `espresso-mcp`: custom MCP server exposing video analysis, timing, machine profile, and grind recommendation tools.
- `video-worker`: optional worker for long video jobs. The first version may run video processing synchronously inside `espresso-mcp`, 'optional' 
- `model-training`: local scripts/notebooks for frame extraction, labeling support, training, and evaluation.
- `storage`: S3 for uploaded videos, extracted frames, prediction reports, and model artifacts.
- `database`: DynamoDB or Postgres for shot history and analysis results.
- `observability`: Prometheus, Grafana, and logs for metrics, dashboards, and debugging.

## 6. Data Flow

1. User opens the frontend. 
2. User uploads a shot video and enters known shot details.
3. Frontend sends the video and metadata to the agent API.
4. Agent stores the video in S3.
5. Agent calls `espresso-mcp.analyze_video`.
6. `espresso-mcp` extracts frames at a fixed FPS.
7. `espresso-mcp` runs the Ultralytics classifier on each frame.
8. `espresso-mcp` smooths frame predictions to avoid one-frame mistakes.
9. `espresso-mcp` calculates shot timing.
10. Agent asks the user for missing machine, grinder, bean, dose, yield, or taste details.
11. Agent calls `espresso-mcp.recommend_grind_adjustment`.
12. Agent returns a final explanation with timing, confidence, recommendation, and next test instructions.
13. Result is saved to the database and shown in the frontend.

## 7. MCP Tools

The custom `espresso-mcp` server exposes:

- `extract_video_frames(video_s3_key, fps)`: extracts frames from an uploaded video and stores them.
- `classify_shot_frames(frames_s3_prefix)`: runs the trained classifier on extracted frames.
- `calculate_shot_timing(predictions, fps)`: returns machine start, first flow, flow end, and durations.
- `analyze_video(video_s3_key, fps)`: combines extraction, classification, smoothing, and timing.
- `recommend_grind_adjustment(shot_context)`: returns a structured recommendation.
- `get_machine_profile(machine_name)`: returns machine-specific notes, especially pre-infusion behavior.
- `save_shot_result(user_id, result)`: saves the analysis.
- `compare_previous_shots(user_id, current_result)`: compares current shot with previous attempts.

An optional `observability-mcp` can expose Prometheus and log-query tools for demo and debugging.

## 8. Recommendation Rules

The recommendation engine starts as rule-based:

- Total shot under 20 seconds: likely too fast; grind finer unless there are channeling signs.
- Total shot between 20 and 35 seconds: timing is plausible; use taste, yield, and visible behavior.
- Total shot over 35 seconds: likely too slow; grind coarser.
- Long startup delay plus very short visible flow: possible puck resistance, too fine grind, or machine pre-infusion behavior.
- Fast shot plus sour or watery taste: grind finer.
- Slow shot plus bitter or harsh taste: grind coarser.
- Normal timing plus spraying or uneven flow: focus on puck prep before changing grind.

The agent should recommend one next change and tell the user what to keep fixed.

## 9. Error Handling

The system handles:

- Unsupported file type: return a clear upload error.
- Video too long or too large: reject with size/duration guidance.
- Frame extraction failure: return a processing error and log details.
- Low model confidence: ask user to confirm or manually adjust detected timestamps.
- Missing machine/grinder/dose/yield: ask follow-up questions.
- MCP timeout: retry once, then return a graceful error.
- LLM failure: return the structured timing result with a basic rule-based recommendation.
- S3/database failure: report that analysis completed but saving failed, when possible.

## 10. Testing Strategy

Unit tests cover:

- Frame prediction smoothing.
- Timing calculation.
- Grind recommendation rules.
- MCP tool request/response schemas.
- Agent behavior when user metadata is missing.

Integration tests cover:

- Agent calling the MCP server through real MCP transport.
- A sample video or frame sequence producing a timing result.
- End-to-end API request returning a recommendation.

Model evaluation measures:

- Machine start timestamp error.
- First flow timestamp error.
- Flow end timestamp error.
- Average confidence by class.

Initial success criteria:

- First flow detected within 1.5 seconds on controlled-angle videos.
- Flow end detected within 2 seconds on controlled-angle videos.
- Machine start detected within 2 seconds when button/light/lever is visible.
- Agent returns a useful recommendation for at least three demo shot scenarios: fast, normal, and slow.

## 11. Deployment

The final course deployment uses:

- Docker images for each service.
- Kubernetes on AWS EC2.
- `dev` and `prod` namespaces.
- ClusterIP services for internal communication.
- Port-forward or ingress for demo access.
- Liveness and readiness probes.
- Resource requests and limits.
- HPA for frontend, agent, and video/MCP service.
- Terraform for AWS resources: EC2, S3, database, IAM, and optional SQS.

## 12. Observability

Metrics include:

- `shot_analysis_requests_total`
- `video_processing_duration_seconds`
- `model_prediction_confidence`
- `mcp_tool_errors_total`
- `agent_request_latency_seconds`
- `failed_video_analysis_total`

Grafana dashboard shows:

- analyzed shots over time
- average processing duration
- failed analysis count
- average confidence
- agent latency
- MCP error count

Healthy means the API is reachable, MCP tools respond, video analysis completes within the expected time, error rate stays low, and model confidence is high enough for recommendations.

## 13. Demo Scenario

The live demo uses a controlled espresso shot video. The user uploads the video, enters machine/grinder/shot details, and the system returns:

- machine start time
- first flow time
- flow end time
- startup delay
- visible flow time
- total shot time
- grind recommendation
- confidence and explanation

The presentation also shows the MCP tool call, Kubernetes services, CI pipeline, and Grafana dashboard.
