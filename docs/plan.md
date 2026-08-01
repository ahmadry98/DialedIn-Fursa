# DialedIN Audio Shot Timing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI espresso shot timing agent that analyzes the audio from an uploaded espresso video, detects machine start/stop, calculates total shot time, and recommends the next grind adjustment.

**Architecture:** A Next.js frontend uploads videos to a FastAPI agent. The agent stores videos in S3 and calls a custom `espresso-mcp` server. The MCP server extracts audio, detects the sustained machine/pump sound window, calculates total shot time, and returns structured data for the agent to explain.

**Tech Stack:** Python, FastAPI, LangGraph, MCP, audio processing with ffmpeg/moviepy or Python audio libraries, Next.js, S3, DynamoDB, Docker, Kubernetes on AWS EC2, Terraform, Prometheus, Grafana, GitHub Actions.

## Global Constraints

- The MVP detects total shot time from audio; it does not train a visual model.
- The MVP uses a heuristic audio detector first; a trained audio classifier is future work.
- The LLM must not invent timestamps. It must use MCP tool results or user-corrected times.
- Recommendations must be next-step adjustments, not guaranteed perfect settings.
- The final deployment must use Kubernetes on AWS EC2, not EKS.
- Dev and prod must be separated by Kubernetes namespaces.
- AWS resources must be provisioned with Terraform.
- Automated tests must include unit tests and MCP integration tests.
- Video processing runs synchronously inside `espresso-mcp` for the MVP; an async worker/SQS flow is future work.

---

## Checkpoint 1: Finalize Project Documents

**Files:**
- Create/modify: `docs/spec.md`
- Create/modify: `docs/plan.md`

**Deliverable:** Course-ready project specification and implementation plan.

- [ ] Review `docs/spec.md` and confirm the audio-only MVP scope.
- [ ] Review `docs/plan.md` and confirm checkpoint order.
- [ ] Confirm the final stack choices: LangGraph for the agent and DynamoDB for shot history.
- [ ] Commit both documents before coding.
- [ ] Open a PR for staff approval if required by the course.

## Checkpoint 2: Collect First Dataset

**Files:**
- Create: `data/raw-videos/README.md`
- Add manually: `data/raw-videos/*.mp4`
- Create: `data/labels/shot_labels.csv`

**Deliverable:** 10-20 controlled espresso videos with basic audio timing labels.

- [ ] Record videos from before button press until after the machine stops.
- [ ] Confirm each video has usable audio where the pump/machine sound is audible.
- [ ] Label each video with `machine_start_time` and `machine_stop_time`.
- [ ] Store metadata when available: machine, grinder, dose, yield, grind setting, roast level, taste notes.
- [ ] Use this CSV header for the audio-only MVP:

```text
video_id,machine_start_time,machine_stop_time,machine,grinder,dose_g,yield_g,grind_setting,roast_level,taste
```

- [ ] If the current CSV still contains `first_flow_time`, keep it for future visual work but treat `flow_end_time` as `machine_stop_time` for the audio baseline until the file is migrated.

## Checkpoint 3: Audio Extraction And Pump Window Detection

**Files:**
- Create: `modeling/audio_analysis.py`
- Create: `modeling/tests/test_audio_analysis.py`
- Create/modify: `modeling/requirements.txt`

**Deliverable:** Local proof that audio can estimate machine start, machine stop, and total shot time.

- [ ] Extract audio from a video into a temporary WAV file.
- [ ] Compute short-window audio energy or simple spectrogram features.
- [ ] Detect the first sustained machine/pump sound increase.
- [ ] Detect when the sustained machine/pump sound ends.
- [ ] Return `machine_start_time`, `machine_stop_time`, `total_shot_seconds`, `start_confidence`, `stop_confidence`, and `audio_method`.
- [ ] Fall back gracefully when the video has no audio track.
- [ ] Test with synthetic audio where start and stop are known.
- [ ] Run the detector against the first 13 videos and compare against the CSV labels.

## Checkpoint 4: Timing Evaluation Report

**Files:**
- Create: `modeling/evaluate_audio_timing.py`
- Create: `docs/audio-results.md`

**Deliverable:** Measured accuracy of audio timing on the first dataset.

- [ ] Load labels from `data/labels/shot_labels.csv`.
- [ ] Run audio timing on every local video.
- [ ] Compare detected start/stop/total time with manual labels.
- [ ] Report per-video errors and average error.
- [ ] Record which videos have noisy or unreliable audio.
- [ ] Decide confidence thresholds for automatic timing versus manual correction.

## Checkpoint 5: Recommendation Rules

**Files:**
- Create: `services/espresso_mcp/recommendations.py`
- Create: `services/espresso_mcp/tests/test_recommendations.py`

**Deliverable:** Rule-based grind recommendation engine based on total shot time and user context.

- [ ] Implement fast-shot recommendation.
- [ ] Implement slow-shot recommendation.
- [ ] Implement normal-time recommendation using taste/context.
- [ ] Return one primary next action and one explanation.
- [ ] Include confidence and what to keep fixed.

## Checkpoint 6: Machine Profiles

**Files:**
- Create: `services/espresso_mcp/machine_profiles.json`
- Create: `services/espresso_mcp/machine_profiles.py`
- Create: `services/espresso_mcp/tests/test_machine_profiles.py`

**Deliverable:** Curated machine profile lookup with a generic fallback.

- [ ] Add profiles for Breville Barista Express, Breville Bambino/Bambino Plus, Gaggia Classic Pro, Rancilio Silvia, DeLonghi Dedica, and Generic Espresso Machine.
- [ ] Include `machine_name`, `aliases`, `target_total_shot_seconds`, `has_preinfusion`, `pump_type`, `portafilter_mm`, `grind_adjustment_notes`, and `source_urls`.
- [ ] Implement alias matching so `BES870` can resolve to Breville Barista Express.
- [ ] Return the generic profile when the machine is unknown.
- [ ] Add tests for exact match, alias match, and fallback.

## Checkpoint 7: Wrap Audio Timing Logic In MCP

**Files:**
- Create: `services/espresso_mcp/app.py`
- Create: `services/espresso_mcp/audio_analysis.py`
- Create: `services/espresso_mcp/requirements.txt`
- Create: `services/espresso_mcp/tests/test_mcp_tools.py`

**Deliverable:** MCP server that exposes the already-built audio timing, recommendation, and machine-profile logic as agent-callable tools.

Expose these tools:

```text
extract_audio_track(video_s3_key)
detect_machine_audio_window(audio_s3_key)
calculate_total_shot_time(machine_start_time, machine_stop_time)
analyze_audio_timing(video_s3_key)
recommend_grind_adjustment(shot_context)
get_machine_profile(machine_name)
save_shot_result(user_id, result)
compare_previous_shots(user_id, current_result)
```

- [ ] Build MCP tool schemas.
- [ ] Connect tools to audio, timing, recommendation, and machine-profile modules.
- [ ] Add tests for tool responses.
- [ ] Run an integration test using real MCP transport.

## Checkpoint 8: Agent API

**Files:**
- Create: `services/agent/app.py`
- Create: `services/agent/agent_runner.py`
- Create: `services/agent/config.py`
- Create: `services/agent/schemas.py`
- Create: `services/agent/prompts.py`
- Create: `services/agent/tests/test_agent.py`

**Deliverable:** FastAPI agent that calls MCP tools and returns espresso coaching responses.

- [ ] Add `POST /analyze-shot`.
- [ ] Add `POST /chat`.
- [ ] Add `GET /health`.
- [ ] Add `GET /metrics`.
- [ ] Add a system prompt that defines DialedIN as an espresso coach, requires MCP tool results for timing, and forbids invented timestamps.
- [ ] Store uploaded video in S3 or local storage in development.
- [ ] Call `espresso-mcp.analyze_audio_timing`.
- [ ] Ask for missing machine/grinder/dose/yield details.
- [ ] Call `espresso-mcp.get_machine_profile`.
- [ ] Call `espresso-mcp.recommend_grind_adjustment`.
- [ ] Return final timing and recommendation.

## Checkpoint 9: Frontend

**Files:**
- Create: `services/frontend/app/page.tsx`
- Create: `services/frontend/components/shot-upload.tsx`
- Create: `services/frontend/components/shot-result.tsx`
- Create: `services/frontend/components/timing-correction.tsx`
- Create: `services/frontend/lib/api.ts`

**Deliverable:** User interface for video upload and result display.

- [ ] Add video upload control.
- [ ] Add machine, grinder, grind setting, dose, yield, roast, and taste inputs.
- [ ] Submit data to the agent.
- [ ] Show machine start, machine stop, total shot time, and confidence.
- [ ] Show recommendation card.
- [ ] Show low-confidence warning when needed.
- [ ] Add editable timestamp fields for low-confidence results: machine start and machine stop.

## Checkpoint 10: Test Plan

**Files:**
- Create: `docs/test-plan.md`

**Deliverable:** Course-ready test plan before implementation reaches deployment.

- [ ] Document unit tests for audio detection, timing calculation, recommendations, machine profiles, and agent missing-data behavior.
- [ ] Document integration tests for real MCP transport and agent-to-MCP calls.
- [ ] Document audio evaluation criteria: machine start within 2 seconds, machine stop within 2 seconds, and total shot time within 3 seconds on clear-audio videos.
- [ ] Document manual demo checks for fast, normal, and slow shot scenarios.

## Checkpoint 11: Storage

**Files:**
- Create: `services/agent/storage.py`
- Create: `services/espresso_mcp/storage.py`
- Create: `infra/terraform/s3.tf`
- Create: `infra/terraform/database.tf`

**Deliverable:** Persistent upload and shot-result storage.

- [ ] Add S3 bucket for videos, extracted audio, and analysis outputs.
- [ ] Add DynamoDB table for shot results.
- [ ] Add local development fallback.
- [ ] Add tests with mocked storage clients.

## Checkpoint 12: Docker Compose

**Files:**
- Create: `compose.yaml`
- Create: `services/agent/Dockerfile`
- Create: `services/espresso_mcp/Dockerfile`
- Create: `services/frontend/Dockerfile`

**Deliverable:** Local multi-service development stack.

- [ ] Containerize frontend.
- [ ] Containerize agent.
- [ ] Containerize espresso MCP.
- [ ] Add Prometheus and Grafana.
- [ ] Verify frontend can call agent.
- [ ] Verify agent can call MCP.

## Checkpoint 13: Kubernetes

**Files:**
- Create: `infra/k8s/00-namespaces.yaml`
- Create: `infra/k8s/frontend.yaml`
- Create: `infra/k8s/agent.yaml`
- Create: `infra/k8s/espresso-mcp.yaml`
- Create: `infra/k8s/prometheus.yaml`
- Create: `infra/k8s/grafana.yaml`
- Create: `infra/k8s/hpa.yaml`

**Deliverable:** Dev/prod Kubernetes manifests.

- [ ] Add `dev` and `prod` namespaces.
- [ ] Add ClusterIP services.
- [ ] Add readiness and liveness probes.
- [ ] Add resource requests and limits.
- [ ] Add HPA for frontend, agent, and espresso MCP.
- [ ] Test access with `kubectl port-forward`.

## Checkpoint 14: Terraform

**Files:**
- Create: `infra/terraform/main.tf`
- Create: `infra/terraform/ec2.tf`
- Create: `infra/terraform/iam.tf`
- Create: `infra/terraform/s3.tf`
- Create: `infra/terraform/database.tf`

**Deliverable:** Infrastructure as Code for AWS.

- [ ] Provision EC2 instances for Kubernetes.
- [ ] Provision S3 bucket.
- [ ] Provision DynamoDB table.
- [ ] Provision IAM permissions.
- [ ] Document apply/destroy commands.

## Checkpoint 15: Observability

**Files:**
- Create: `monitoring/prometheus.yml`
- Create: `infra/grafana/dashboards/shot-analysis.json`
- Create: `monitoring/alerts.yml`
- Modify: service metrics endpoints.

**Deliverable:** Health metrics and dashboard.

- [ ] Add agent request metrics.
- [ ] Add MCP tool metrics.
- [ ] Add audio processing duration metrics.
- [ ] Add audio start/stop confidence metrics.
- [ ] Add total shot time metrics.
- [ ] Add failed analysis metrics.
- [ ] Build Grafana dashboard.
- [ ] Add alerts for high analysis failure rate, low average audio confidence, MCP tool errors, high agent latency, and long audio processing duration.

## Checkpoint 16: CI/CD

**Files:**
- Create: `.github/workflows/test.yaml`
- Create: `.github/workflows/build-images.yaml`
- Create: `.github/workflows/deploy-dev.yaml`
- Create: `.github/workflows/deploy-prod.yaml`

**Deliverable:** Automated tests, image builds, and deployment workflow.

- [ ] Run unit tests on pull requests.
- [ ] Run MCP integration tests on pull requests.
- [ ] Build Docker images after merge.
- [ ] Deploy to dev.
- [ ] Keep prod deployment manual or protected.

## Checkpoint 17: Final Demo

**Files:**
- Create: `docs/demo-script.md`
- Create: presentation slides.

**Deliverable:** 15-minute presentation and live demo.

- [ ] Prepare one fast shot video.
- [ ] Prepare one slow or normal shot video.
- [ ] Show upload and audio timing analysis.
- [ ] Show MCP tool call.
- [ ] Show Kubernetes pods/services.
- [ ] Show Grafana dashboard.
- [ ] Show GitHub Actions pipeline.
- [ ] Explain limitations and future visual improvements.

## First Milestone To Build

Do not start with the full cloud system. Start with this local proof:

```text
video -> audio -> pump start/stop -> total shot time -> recommendation
```

Once this works, wrap it with MCP, agent, frontend, cloud, Kubernetes, and observability.
