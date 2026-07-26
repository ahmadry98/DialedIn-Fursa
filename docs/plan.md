# DialedIN Shot Timing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI espresso shot timing agent that analyzes an uploaded espresso video, detects machine start/first flow/flow end, and recommends the next grind adjustment.

**Architecture:** A Next.js frontend uploads videos to a FastAPI agent. The agent stores videos in S3 and calls a custom `espresso-mcp` server. The MCP server extracts frames, runs an Ultralytics classification model, calculates timing, and returns structured data for the agent to explain.

**Tech Stack:** Python, FastAPI, LangGraph, MCP, Ultralytics, OpenCV, Next.js, S3, DynamoDB, Docker, Kubernetes on AWS EC2, Terraform, Prometheus, Grafana, GitHub Actions.

## Global Constraints

- The trained model detects shot states, not perfect grind settings.
- The MVP uses visual frame classification first; audio detection is optional after the visual pipeline works.
- The LLM must not invent timestamps. It must use MCP tool results.
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

- [ ] Review `docs/spec.md` and confirm the MVP scope.
- [ ] Review `docs/plan.md` and confirm checkpoint order.
- [ ] Confirm the final stack choices: LangGraph for the agent and DynamoDB for shot history.
- [ ] Commit both documents before coding.
- [ ] Open a PR for staff approval if required by the course.

## Checkpoint 2: Collect First Dataset

**Files:**
- Create: `data/raw-videos/README.md`
- Add manually: `data/raw-videos/*.mp4`
- Create: `data/labels/shot_labels.csv`

**Deliverable:** 10-20 controlled espresso videos with basic timestamp labels.

- [ ] Record videos from before button press until after coffee stops.
- [ ] Keep the first dataset angle consistent.
- [ ] Make sure button/light/lever, portafilter, cup, and stream are visible.
- [ ] Label each video with `machine_start_time`, `first_flow_time`, and `flow_end_time`.
- [ ] Store metadata: machine, grinder, dose, yield, grind setting, roast level, taste notes.
- [ ] Use this CSV header exactly:

```text
video_id,machine_start_time,first_flow_time,flow_end_time,machine,grinder,dose_g,yield_g,grind_setting,roast_level,taste
```

## Checkpoint 3: Frame Extraction

**Files:**
- Create: `modeling/extract_frames.py`
- Create: `modeling/tests/test_extract_frames.py`

**Deliverable:** A repeatable script that converts video into timestamped frames.

- [ ] Write a test that verifies frame filenames include timestamps.
- [ ] Implement frame extraction with OpenCV.
- [ ] Default to 2 FPS for labeling.
- [ ] Save frames under `data/frames/<video_id>/`.
- [ ] Run the script on the first dataset.

## Checkpoint 4: Build Classification Dataset

**Files:**
- Create folders under `data/classification-dataset/`
- Create: `modeling/build_classification_dataset.py`
- Create: `modeling/tests/test_build_classification_dataset.py`

**Deliverable:** Ultralytics-compatible classification dataset.

Use this folder structure:

```text
data/classification-dataset/
  train/
    idle/
    machine_started_no_flow/
    coffee_flowing/
    shot_finished/
  val/
    idle/
    machine_started_no_flow/
    coffee_flowing/
    shot_finished/
```

- [ ] Convert timestamp labels into frame-level labels.
- [ ] Split frames into train and validation sets.
- [ ] Keep validation videos separate from training videos when possible.
- [ ] Confirm every class has examples.

## Checkpoint 5: Train Ultralytics Classifier

**Files:**
- Create: `modeling/train_classifier.py`
- Create: `modeling/evaluate_classifier.py`
- Output: `models/shot_state_classifier.pt`
- Create: `docs/model-results.md`

**Deliverable:** First trained shot-state classifier.

- [ ] Install Ultralytics in the model environment.
- [ ] Train a small classification model on the dataset.
- [ ] Save the best model artifact.
- [ ] Evaluate validation accuracy and per-class confidence.
- [ ] Record results in `docs/model-results.md`.
- [ ] Document how `espresso-mcp` will load `models/shot_state_classifier.pt` locally and inside Docker.

## Checkpoint 6: Analyze A Full Video

**Files:**
- Create: `services/espresso_mcp/video_analysis.py`
- Create: `services/espresso_mcp/tests/test_video_analysis.py`

**Deliverable:** Code that runs the classifier over a full video and returns frame predictions.

- [ ] Load the trained model.
- [ ] Extract frames at prediction FPS.
- [ ] Predict class and confidence per frame.
- [ ] Return ordered predictions with timestamps.
- [ ] Test using a small fixture frame sequence.

## Checkpoint 7: Prediction Smoothing And Timing

**Files:**
- Create: `services/espresso_mcp/timing.py`
- Create: `services/espresso_mcp/tests/test_timing.py`

**Deliverable:** Stable machine start, first flow, and flow end timestamps.

- [ ] Add smoothing that requires repeated frames before changing state.
- [ ] Ignore one-frame prediction mistakes.
- [ ] Calculate `machine_start_time`.
- [ ] Calculate `first_flow_time`.
- [ ] Calculate `flow_end_time`.
- [ ] Calculate `startup_delay_seconds`, `visible_flow_seconds`, and `total_shot_seconds`.
- [ ] Return confidence and warnings when timestamps are uncertain.

## Checkpoint 8: Recommendation Rules

**Files:**
- Create: `services/espresso_mcp/recommendations.py`
- Create: `services/espresso_mcp/tests/test_recommendations.py`

**Deliverable:** Rule-based grind recommendation engine.

- [ ] Implement fast-shot recommendation.
- [ ] Implement slow-shot recommendation.
- [ ] Implement normal-time recommendation using taste/context.
- [ ] Handle long startup delay.
- [ ] Return one primary next action and one explanation.
- [ ] Include confidence and what to keep fixed.

## Checkpoint 9: Machine Profiles

**Files:**
- Create: `services/espresso_mcp/machine_profiles.json`
- Create: `services/espresso_mcp/machine_profiles.py`
- Create: `services/espresso_mcp/tests/test_machine_profiles.py`

**Deliverable:** Curated machine profile lookup with a generic fallback.

- [ ] Add profiles for Breville Barista Express, Breville Bambino/Bambino Plus, Gaggia Classic Pro, Rancilio Silvia, DeLonghi Dedica, and Generic Espresso Machine.
- [ ] Include `machine_name`, `aliases`, `has_preinfusion`, `typical_startup_delay_seconds`, `target_total_shot_seconds`, `target_visible_flow_seconds`, `portafilter_mm`, `pressure_type`, `grind_adjustment_notes`, and `source_urls`.
- [ ] Implement alias matching so `BES870` can resolve to Breville Barista Express.
- [ ] Return the generic profile when the machine is unknown.
- [ ] Add tests for exact match, alias match, and fallback.

## Checkpoint 10: Wrap Existing Analysis Logic In MCP

**Files:**
- Create: `services/espresso_mcp/app.py`
- Create: `services/espresso_mcp/requirements.txt`
- Create: `services/espresso_mcp/tests/test_mcp_tools.py`

**Deliverable:** MCP server that exposes the already-built video, timing, recommendation, and machine-profile logic as agent-callable tools.

Expose these tools:

```text
analyze_video(video_s3_key, fps)
calculate_shot_timing(predictions, fps)
recommend_grind_adjustment(shot_context)
get_machine_profile(machine_name)
save_shot_result(user_id, result)
compare_previous_shots(user_id, current_result)
```

- [ ] Build MCP tool schemas.
- [ ] Connect tools to timing and recommendation modules.
- [ ] Connect `get_machine_profile(machine_name)` to `machine_profiles.py`.
- [ ] Add tests for tool responses.
- [ ] Run an integration test using real MCP transport.

## Checkpoint 11: Agent API

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
- [ ] Call `espresso-mcp.analyze_video`.
- [ ] Ask for missing machine/grinder/dose/yield details.
- [ ] Call `espresso-mcp.get_machine_profile`.
- [ ] Call `espresso-mcp.recommend_grind_adjustment`.
- [ ] Return final timing and recommendation.

## Checkpoint 12: Frontend

**Files:**
- Create: `services/frontend/app/page.tsx`
- Create: `services/frontend/components/shot-upload.tsx`
- Create: `services/frontend/components/shot-result.tsx`
- Create: `services/frontend/components/timestamp-correction.tsx`
- Create: `services/frontend/lib/api.ts`

**Deliverable:** User interface for video upload and result display.

- [ ] Add video upload control.
- [ ] Add machine, grinder, grind setting, dose, yield, roast, and taste inputs.
- [ ] Submit data to the agent.
- [ ] Show timing timeline.
- [ ] Show recommendation card.
- [ ] Show low-confidence warning when needed.
- [ ] Add editable timestamp fields for low-confidence results: machine start, first flow, and shot end.

## Checkpoint 13: Test Plan

**Files:**
- Create: `docs/test-plan.md`

**Deliverable:** Course-ready test plan before implementation reaches deployment.

- [ ] Document unit tests for timing, smoothing, recommendations, machine profiles, and agent missing-data behavior.
- [ ] Document integration tests for real MCP transport and agent-to-MCP calls.
- [ ] Document model evaluation criteria: machine start within 2 seconds, first flow within 1.5 seconds, and flow end within 2 seconds on controlled-angle videos.
- [ ] Document manual demo checks for fast, normal, and slow shot scenarios.

## Checkpoint 14: Storage

**Files:**
- Create: `services/agent/storage.py`
- Create: `services/espresso_mcp/storage.py`
- Create: `infra/terraform/s3.tf`
- Create: `infra/terraform/database.tf`

**Deliverable:** Persistent upload and shot-result storage.

- [ ] Add S3 bucket for videos, frames, and model outputs.
- [ ] Add DynamoDB table for shot results.
- [ ] Add local development fallback.
- [ ] Add tests with mocked storage clients.

## Checkpoint 15: Docker Compose

**Files:**
- Create: `compose.yaml`
- Create: `services/agent/Dockerfile`
- Create: `services/espresso_mcp/Dockerfile`
- Create: `services/frontend/Dockerfile`

**Deliverable:** Local multi-service development stack.

- [ ] Containerize frontend.
- [ ] Containerize agent.
- [ ] Containerize espresso MCP.
- [ ] Copy `models/shot_state_classifier.pt` into the `espresso-mcp` image for the first deployment.
- [ ] Add Prometheus and Grafana.
- [ ] Verify frontend can call agent.
- [ ] Verify agent can call MCP.

## Checkpoint 16: Kubernetes

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

## Checkpoint 17: Terraform

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

## Checkpoint 18: Observability

**Files:**
- Create: `monitoring/prometheus.yml`
- Create: `infra/grafana/dashboards/shot-analysis.json`
- Create: `monitoring/alerts.yml`
- Modify: service metrics endpoints.

**Deliverable:** Health metrics and dashboard.

- [ ] Add agent request metrics.
- [ ] Add MCP tool metrics.
- [ ] Add video processing duration metrics.
- [ ] Add model confidence metrics.
- [ ] Add failed analysis metrics.
- [ ] Build Grafana dashboard.
- [ ] Add alerts for high analysis failure rate, low average model confidence, MCP tool errors, high agent latency, and long video processing duration.

## Checkpoint 19: CI/CD

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

## Checkpoint 20: Final Demo

**Files:**
- Create: `docs/demo-script.md`
- Create: presentation slides.

**Deliverable:** 15-minute presentation and live demo.

- [ ] Prepare one fast shot video.
- [ ] Prepare one slow or normal shot video.
- [ ] Show upload and analysis.
- [ ] Show MCP tool call.
- [ ] Show Kubernetes pods/services.
- [ ] Show Grafana dashboard.
- [ ] Show GitHub Actions pipeline.
- [ ] Explain limitations and future improvements.

## First Milestone To Build

Do not start with the full cloud system. Start with this local proof:

```text
video -> frames -> classifier -> predictions -> timing -> recommendation
```

Once this works, wrap it with MCP, agent, frontend, cloud, Kubernetes, and observability.
