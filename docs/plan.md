# DialedIN Espresso Shot Review Implementation Plan

> **For agentic workers:** Use the superpowers workflow when available for checkpoint implementation and review. Keep each checkpoint small, branch-based, tested, and reviewable.

**Goal:** Build a chat-first espresso coach that can guide a user through machine/grinder context, shot timing, video analysis, and exact grind recommendations while growing equipment profiles through a human-reviewed Bedrock research workflow.

**Current architecture:** Next.js frontend -> FastAPI agent -> `espresso_mcp` tool layer. Audio timing and recommendations run synchronously for the MVP. The current form UI proves the core workflow; Checkpoint 12 turns it into a guided chat experience. Unknown gear research uses web evidence plus Bedrock, then a human promotion step.

**Tech stack:** Python, FastAPI, MCP-compatible tool layer, ffmpeg/audio heuristics, Next.js, Expo/React Native, Bedrock, LangGraph orchestration, S3/DynamoDB, Docker, Kubernetes on AWS EC2, Terraform, Prometheus/Grafana, GitHub Actions.

## Global Constraints

- Audio timing is the MVP source of truth; visual detection is future work.
- The LLM must not invent timestamps or machine facts.
- Recommendation decisions are deterministic/rule-based, not LLM-based.
- Chat UX may use an LLM for natural conversation and value extraction, but timing and grind math must come from existing tools.
- Image-based machine/grinder recognition must ask the user to confirm before trusting the guess.
- LangGraph orchestrates the chat-first coach flow; deterministic espresso tools remain the source of truth.
- Bedrock is used for profile research drafts only.
- Profile drafts require human review before promotion to trusted JSON.
- Built-in grinders must not create fake separate grinder candidates.
- Dose and yield are optional because many users do not use a scale; recommendations improve when provided.
- Do not push changes unless the user explicitly asks.

---

## Checkpoint 1: Project Documents

**Files:**
- `docs/spec.md`
- `docs/plan.md`

**Deliverable:** Course-ready spec and checkpoint plan.

- [x] Define audio-first MVP.
- [x] Define machine/grinder profile strategy.
- [x] Define Bedrock-assisted unknown gear research.
- [x] Define reviewed profile promotion workflow.
- [x] Update docs after implementation changes.

## Checkpoint 2: Initial Dataset

**Files:**
- `data/raw-videos/README.md`
- `data/raw-videos/*.mp4`
- `data/labels/shot_labels.csv`

**Deliverable:** Controlled espresso videos with manual machine start/stop labels.

- [x] Add first local videos.
- [x] Label `machine_start_time` and `machine_stop_time`.
- [x] Keep optional metadata columns for machine, grinder, dose, yield, grind setting, roast, taste, and notes.
- [x] Exclude raw videos from git.

## Checkpoint 3: Audio Extraction And Timing Detection

**Files:**
- `modeling/audio_analysis.py`
- `modeling/evaluate_audio_timing.py`
- `modeling/tests/test_audio_analysis.py`
- `modeling/requirements.txt`

**Deliverable:** Local audio timing baseline.

- [x] Extract audio with ffmpeg/OpenCV-free path.
- [x] Detect sustained machine/pump sound.
- [x] Calculate total shot time.
- [x] Add confidence/warnings.
- [x] Evaluate against labeled videos.

## Checkpoint 4: Audio Timing Evaluation

**Files:**
- `docs/audio-results.md`
- `modeling/evaluate_audio_timing.py`

**Deliverable:** Timing quality report and known failure notes.

- [x] Compare detected start/stop/total against labels.
- [x] Identify noisy/talking videos.
- [x] Tune heuristic to avoid short loud spikes.
- [x] Keep manual correction path for low confidence.

## Checkpoint 5: Recommendation Engine

**Files:**
- `services/espresso_mcp/recommendations.py`
- `services/espresso_mcp/tests/test_recommendations.py`

**Deliverable:** Rule-based espresso recommendation engine.

- [x] Fast shot -> grind finer unless channeling signs dominate.
- [x] Slow shot -> grind coarser.
- [x] In-range shot -> use taste/context.
- [x] Yield optional.
- [x] Return one next action, explanation, confidence, and keep-fixed fields.

## Checkpoint 6: Machine Profiles

**Files:**
- `services/espresso_mcp/machine_profiles.json`
- `services/espresso_mcp/machine_profiles.py`
- `services/espresso_mcp/tests/test_machine_profiles.py`

**Deliverable:** Trusted machine profile lookup with generic fallback.

- [x] Add common home espresso machines.
- [x] Use structured `specs`, `brew_defaults`, and field-level `sources`.
- [x] Add alias matching.
- [x] Add generic fallback.
- [x] Add Meraki as reviewed trusted profile.

## Checkpoint 7: Grinder Profiles And Exact Settings

**Files:**
- `services/espresso_mcp/grinder_profiles.json`
- `services/espresso_mcp/grinder_profiles.py`
- `services/espresso_mcp/tests/test_grinder_profiles.py`

**Deliverable:** Grinder lookup and exact next setting calculation.

- [x] Add curated grinder profiles.
- [x] Add generic numeric grinder fallback.
- [x] Validate known grinder settings.
- [x] Calculate exact next setting based on direction and step size.
- [x] Use conservative seconds-per-small-step estimates to scale adjustment size from shot-time gap.
- [x] Support integer and decimal grinders.

## Checkpoint 8: MCP Tool Layer

**Files:**
- `services/espresso_mcp/app.py`
- `services/espresso_mcp/audio_analysis.py`
- `services/espresso_mcp/requirements.txt`
- `services/espresso_mcp/tests/test_mcp_tools.py`

**Deliverable:** MCP-compatible espresso tool layer.

Tools:

```text
extract_audio_track(video_s3_key)
detect_machine_audio_window(audio_s3_key)
calculate_total_shot_time(machine_start_time, machine_stop_time)
analyze_audio_timing(video_s3_key)
recommend_grind_adjustment(shot_context)
get_machine_profile(machine_name)
save_shot_result(user_id, result)
compare_previous_shots(user_id, current_result)
capture_unknown_gear(user_id, machine, grinder, shot_context)
list_profile_candidates()
prepare_profile_research(candidate_key)
attach_draft_profile(candidate_key, draft_profile)
```

- [x] Register tool names/schemas.
- [x] Connect tools to audio, recommendation, profiles, and profile candidates.
- [x] Add tests for direct tool responses.
- [ ] Add real MCP transport integration test.

## Checkpoint 9: Agent API

**Files:**
- `services/agent/app.py`
- `services/agent/agent_runner.py`
- `services/agent/config.py`
- `services/agent/schemas.py`
- `services/agent/prompts.py`
- `services/agent/tests/test_agent.py`

**Deliverable:** FastAPI agent API for shot analysis and chat.

- [x] Add `/analyze-shot`.
- [x] Add `/chat`.
- [x] Add `/health`.
- [x] Add `/metrics`.
- [x] Add CORS for local frontend.
- [x] Add missing-field handling.
- [x] Add optional dose/yield handling.
- [x] Add background profile research autorun.
- [x] Protect shot analysis from background research failures.

## Checkpoint 10: Frontend

**Files:**
- `services/frontend/app/page.tsx`
- `services/frontend/components/shot-upload.tsx`
- `services/frontend/components/shot-result.tsx`
- `services/frontend/components/timing-correction.tsx`
- `services/frontend/lib/api.ts`
- `services/frontend/lib/gear-options.ts`

**Deliverable:** Usable local shot review interface.

- [x] Add video/path input.
- [x] Add machine and grinder datalist inputs.
- [x] Add built-in grinder checkbox.
- [x] Add optional dose/yield, grind setting, roast, and taste inputs.
- [x] Validate known grinder settings client-side.
- [x] Submit to agent.
- [x] Show timing, confidence, warnings, recommendation, exact setting, missing fields, and unknown gear candidates.
- [x] Add manual timing correction.

## Checkpoint 11: Unknown Gear Research Workflow

**Files:**
- `services/espresso_mcp/profile_candidates.py`
- `services/espresso_mcp/profile_research.py`
- `services/espresso_mcp/profile_research_worker.py`
- `services/espresso_mcp/profile_web_evidence.py`
- `services/espresso_mcp/profile_promoter.py`
- related tests

**Deliverable:** Human-reviewed equipment profile learning loop.

- [x] Capture unknown machines/grinders.
- [x] Avoid separate grinder candidates for built-in grinder machines.
- [x] Prepare research packets and expected schemas.
- [x] Collect web evidence from official/manual-like pages.
- [x] Call Bedrock for draft JSON.
- [x] Store `research_evidence`, `draft_profile`, and `draft_validation`.
- [x] Add local `.env.example` for Bedrock and autorun flags.
- [x] Add promotion helper for reviewed drafts.
- [x] Prove the loop with Meraki.

## Checkpoint 11.5: Recommendation UX And Safety

**Files:**
- `services/espresso_mcp/recommendations.py`
- `services/frontend/components/shot-result.tsx`
- `services/frontend/components/shot-upload.tsx`
- related tests and API types

**Deliverable:** Safer, clearer user-facing recommendation flow before profile admin work.

- [x] Explain why an exact grinder setting was chosen.
- [x] Add recommendation confidence details.
- [x] Add clearer manual timing mode for users who do not want video/audio.
- [x] Improve timing result UI.
- [x] Add stronger low-confidence audio warning.


## Checkpoint 11.75: CI/CD Safety Net

**Files:**
- `.github/workflows/ci.yml`

**Deliverable:** GitHub Actions checks for every branch/PR.

- [x] Run Python tests for `modeling`, `espresso_mcp`, and agent services.
- [x] Run frontend TypeScript check.
- [x] Run frontend production build from `services/frontend`.
- [x] Disable profile research autorun during CI tests so Bedrock/network work does not run accidentally.
- [ ] Add deployment workflow after the deployment target is finalized.

## Checkpoint 12: Chat-First Espresso Coach UX

**Files:**
- Create/modify: `services/agent/conversation.py`
- Modify: `services/agent/app.py`
- Modify: `services/agent/schemas.py`
- Create: `services/agent/graph.py`
- Modify: `services/agent/requirements.txt`
- Create/modify: `services/agent/tests/test_conversation.py`
- Create: `services/agent/tests/test_graph.py`
- Create/modify: `services/frontend/app/page.tsx`
- Create: `services/frontend/components/chat-coach.tsx`
- Modify: `services/frontend/lib/api.ts`

**Deliverable:** Guided chat experience that uses the existing analysis engine instead of a large form.

- [x] Add a conversation state object for machine, grinder, built-in grinder, optional dose/yield, grind setting, roast, taste, timing/video, and confirmation state.
- [x] Use LangGraph to orchestrate context loading, parsing, missing-field routing, analysis, and response assembly.
- [x] Let users send normal messages such as greetings and questions.
- [x] Ask the next missing espresso question naturally.
- [x] Extract typed values from user replies where possible.
- [x] Accept machine/grinder names manually in chat.
- [x] Accept local development video path or manual timing in chat. Production/mobile should use uploaded video keys instead of local paths.
- [x] Call the existing `/analyze-shot` flow once required fields are available.
- [x] Show the same timing, warning, exact-setting, and recommendation output inside the chat.
- [x] Keep the old form logic reusable as the underlying engine.
- [x] Make the chat layout mobile-friendly from the start.

## Checkpoint 13: Image Recognition For Machine And Grinder

**Files:**
- Modify: `services/agent/conversation.py`
- Modify: `services/agent/app.py`
- Modify: `services/agent/schemas.py`
- Create/modify: `services/agent/tests/test_image_identification.py`
- Modify: `services/frontend/components/chat-coach.tsx`

**Deliverable:** Optional photo-assisted gear identification inside the chat flow.

- [x] Let the user upload a machine or grinder photo in chat.
- [x] Send image to a multimodal LLM for a best-guess model name.
- [x] Match the guess against trusted machine/grinder profiles and aliases.
- [x] Ask the user to confirm before using the guessed gear.
- [x] Route low-confidence or unknown photo results back to manual gear entry so the existing candidate workflow can capture them after analysis.
- [x] Never treat image recognition as verified machine facts.

## Checkpoint 14: Mobile/PWA Experience

**Files:**
- Modify: `services/frontend/app/page.tsx`
- Modify: `services/frontend/app/globals.css`
- Create/modify: `services/frontend/app/manifest.ts` or static manifest files
- Add mobile upload/camera affordances as needed

**Deliverable:** Phone-friendly DialedIN experience before any native desktop/mobile wrapper.

**Skills/tools for this checkpoint:**
- `browser:control-in-app-browser`: test the app visually in desktop/mobile widths, click through chat, verify uploads, and capture screenshots.
- `sites:sites-building`: optional if the frontend becomes a hosted Sites deployment; not required for local-only PWA work.
- `sites-design-picker`: optional only if we generate three comparable design directions and need a design choice.
- `visualize:visualize`: optional for quick mobile-flow or layout prototypes.
- `imagegen`: optional for app icons, PWA splash assets, or polished visual assets.
- Next.js: app metadata, manifest support, routing, production build, and frontend app structure.
- React/TypeScript: chat state, attachment handling, typed API payloads, and component behavior.
- CSS: responsive layout, mobile safe areas, touch targets, sticky chat composer, and desktop compatibility.
- Browser file input APIs: camera/photo/video library selection and upload affordances.
- `npm run typecheck` and `npm run build`: required frontend verification.

- [x] Optimize chat layout for phone screens.
- [x] Show timing/recommendation conclusions as a separate mobile analysis panel instead of forcing right-side cards beside chat.
- [x] Make upload controls preview attached photo/video in chat.
- [ ] Add PWA manifest and app metadata.
- [x] Keep desktop web usable.
- [ ] Defer native desktop app wrapping until the web/PWA flow is stable.

## Checkpoint 14.5: Product Polish And Mobile Chat Review

**Files:**
- Modify: `services/frontend/components/chat-coach.tsx`
- Modify: `services/frontend/app/globals.css`
- Modify: `services/agent/conversation.py`
- Modify: `services/agent/graph.py`
- Modify: `services/agent/agent_runner.py`
- Modify: `services/agent/tests/test_graph.py`

**Deliverable:** Make the chat demo feel product-ready before native mobile work.

- [x] Hide internal context chips from the user-facing chat.
- [x] Rename page to AI Shot Analysis.
- [x] Use compact chat composer with attach/send icon buttons.
- [x] Show image/video previews inside chat bubbles.
- [x] Hide internal local video paths from the visible chat bubble when a preview exists.
- [x] Reject invalid field answers immediately instead of waiting until final analysis.
- [x] Treat common built-in grinder wording like `built it` as built-in grinder.
- [x] Ask for timing confirmation or cleaner video when video timing confidence is below 70%.
- [x] Open mobile shot conclusions in a separate analysis panel.

## Checkpoint 15: Review/Admin UI

**Files:**
- Create/modify: frontend review page/components
- Modify: agent endpoints for candidates/promotions

**Deliverable:** UI for reviewing profile candidates without opening JSON files manually.

- [x] Add endpoint to list candidates.
- [x] Add endpoint to rerun research for one candidate.
- [x] Add endpoint to promote a reviewed candidate.
- [x] Add frontend candidate review page.
- [x] Show source URLs/evidence snippets.
- [x] Allow editing draft notes before promotion.

## Checkpoint 16: Research Quality Gate

**Files:**
- Create: `services/espresso_mcp/research_quality.py`
- Modify: `services/espresso_mcp/profile_research.py`
- Modify: `services/espresso_mcp/profile_web_evidence.py`
- Modify: frontend/admin review UI
- Create/modify: quality gate tests

**Deliverable:** Prevent empty or weak researched drafts from being marked ready.

- [x] Extract useful text from PDF/manual sources.
- [x] Deduplicate regional/product-page source variants.
- [x] Prefer manufacturer and official asset/manual sources while still allowing reputable supporting sources.
- [x] Store `research_quality` with score, threshold, reasons, and warnings.
- [x] Mark drafts `draft_ready` only when schema is valid and score is above 55.
- [x] Mark no-source or mostly empty drafts as `research_failed`.
- [x] Show quality score and reasons in the admin review UI.


## Checkpoint 17: Native Expo AI Chat Integration

**Files:**
- Modify/create in sibling app: `DialedIn/dialedin-mobile/app/machine/[slug]/ai.tsx`
- Modify/create in sibling app: `DialedIn/dialedin-mobile/components/AIShotChat.tsx`
- Modify/create in sibling app: `DialedIn/dialedin-mobile/lib/aiShotApi.ts`
- Modify/create in sibling app: media picker/upload helpers as needed
- Modify: `services/agent/app.py` only if mobile-specific API affordances are needed

**Deliverable:** AI Shot Analysis runs inside the DialedIn Expo app instead of opening the Next.js site.

- [x] Replace the temporary open-browser/WebView bridge with native React Native chat components.
- [x] Render assistant/user bubbles, loading state, and errors natively. Photo/video upload previews move to Checkpoint 18 with S3 upload.
- [x] Call FastAPI `/chat` directly from the Expo app.
- [x] Keep conversation state in the Expo screen.
- [x] Show timing/recommendation as a native full-screen or bottom-sheet analysis view.
- [x] Support low-confidence timing confirmation inside the native screen through the chat response and analysis view.
- [x] Keep Next.js frontend available for desktop/admin/local demos.
- [x] Add native photo attachment for machine/grinder recognition using base64.
- [x] Link DialedIN mobile machine slugs to DialChat machine profiles where available.
- [ ] Test on iPhone simulator and a real phone using LAN or deployed API URLs.

## Checkpoint 18: Storage And S3 Video Upload

**Files:**
- `services/agent/storage.py`
- `services/espresso_mcp/storage.py`
- `infra/terraform/s3.tf`
- `infra/terraform/database.tf`

**Deliverable:** Persistent upload/result storage and a phone-safe way to send shot videos.

- [ ] Add S3 bucket for raw videos, extracted audio, and analysis outputs.
- [ ] Add backend endpoint to create presigned upload URLs.
- [ ] Add backend endpoint/helper to register uploaded video metadata and return `video_s3_key`.
- [ ] Update Expo native chat to upload selected/recorded videos to S3 before calling `/chat`; photo recognition already works with base64 for small images.
- [ ] Update Next.js local demo to support either local paths or uploaded S3 keys.
- [ ] Add DynamoDB table for shot results/history.
- [ ] Store timing result, recommendation, confirmed corrections, and media key for compare/history.
- [ ] Keep local development fallback for `data/raw-videos/...`.
- [ ] Add mocked storage tests for S3 upload registration and result persistence.

## Checkpoint 19: Docker Compose

**Files:**
- `compose.yaml`
- service Dockerfiles

**Deliverable:** Local multi-service stack.

- [ ] Containerize frontend.
- [ ] Containerize agent.
- [ ] Containerize espresso MCP.
- [ ] Add Prometheus/Grafana.
- [ ] Verify frontend can call agent in compose.

## Checkpoint 20: Kubernetes On AWS EC2

**Files:**
- `infra/k8s/*.yaml`

**Deliverable:** Kubernetes manifests for course deployment.

- [ ] Add namespaces according to chosen branch/environment workflow.
- [ ] Add deployments/services for frontend, agent, and espresso MCP.
- [ ] Add readiness/liveness probes.
- [ ] Add resource requests/limits.
- [ ] Add HPA if required.
- [ ] Test with `kubectl port-forward` or ingress.

## Checkpoint 21: Terraform

**Files:**
- `infra/terraform/*.tf`

**Deliverable:** AWS infrastructure as code.

- [ ] Provision EC2 for Kubernetes.
- [ ] Provision S3.
- [ ] Provision DynamoDB.
- [ ] Provision IAM permissions for Bedrock/S3/DynamoDB.
- [ ] Document apply/destroy commands.

## Checkpoint 22: Observability

**Files:**
- `monitoring/prometheus.yml`
- `infra/grafana/dashboards/shot-analysis.json`
- `monitoring/alerts.yml`

**Deliverable:** Metrics and dashboard.

- [ ] Add request metrics.
- [ ] Add audio processing metrics.
- [ ] Add profile research metrics.
- [ ] Add MCP/tool error metrics.
- [ ] Build Grafana dashboard.

## Checkpoint 23: Deployment Automation

**Files:**
- `.github/workflows/ci.yml`
- `.github/workflows/build-images.yaml`
- `.github/workflows/deploy-dev.yaml`
- `.github/workflows/deploy-prod.yaml`

**Deliverable:** Extend the current CI safety net into Docker image build and deployment automation.

- [x] Run unit tests on PRs.
- [x] Run frontend build/type checks on PRs.
- [ ] Build Docker images after merge.
- [ ] Deploy to dev.
- [ ] Keep production/main deployment protected if used.

## Checkpoint 24: Final Demo

**Files:**
- `docs/demo-script.md`
- presentation slides

**Deliverable:** 15-minute final project demo.

- [ ] Show normal shot analysis.
- [ ] Show manual timing correction.
- [ ] Show exact grinder setting recommendation.
- [ ] Show unknown gear capture.
- [ ] Show Bedrock research draft with evidence.
- [ ] Show reviewed promotion into trusted profiles.
- [ ] Explain future visual model path.

## Current Review Before Push

Run before pushing this checkpoint:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest modeling/tests services/espresso_mcp/tests services/agent/tests -q
cd services/frontend && npm run build
```

Expected current result:

```text
70 passed, 13 subtests passed
Next.js build passed
```
