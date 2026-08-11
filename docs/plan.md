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
- `infra/terraform/versions.tf`
- `infra/terraform/locals.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/s3.tf`
- `infra/terraform/database.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/dev.tfvars`
- `infra/terraform/prod.tfvars`
- `infra/terraform/tfvars/us-east-1.tfvars`

**Deliverable:** Persistent upload/result storage and a phone-safe way to send shot videos.

- [x] Add S3 bucket Terraform for raw videos, extracted audio, and analysis outputs.
- [x] Add backend endpoint to create presigned/local upload URLs.
- [x] Add backend endpoint/helper to register uploaded video metadata and return `video_s3_key`.
- [x] Update Expo native chat to upload selected videos before calling `/chat`; local mode uses FastAPI storage and S3 mode uses presigned PUT URLs.
- [x] Update Next.js local demo to support either local paths or uploaded S3 keys.
- [x] Add DynamoDB table Terraform for shot results/history.
- [x] Align Terraform layout with PolyAIFursa conventions: versions, locals, tags, outputs, and tfvars.
- [x] Store timing result, recommendation, confirmed corrections, and media key for compare/history when `DIALEDIN_SHOT_RESULTS_TABLE` is configured; memory remains the local fallback.
- [x] Keep local development fallback for `data/raw-videos/...` and add local uploaded media fallback under `data/uploads/`.
- [x] Add mocked storage tests for local upload/register, S3 presigned URL generation, S3 media download, and DynamoDB shot history.
- [x] Return user-readable S3 upload/download permission errors instead of generic 500 responses.
- [x] Configure narrow S3 CORS origins for browser/mobile presigned uploads.

## Checkpoint 19: Equipment Profile API

**Files:**
- `services/agent/app.py`
- `services/agent/schemas.py`
- `services/espresso_mcp/machine_profiles.py`
- `services/espresso_mcp/grinder_profiles.py`
- `services/agent/tests/test_profile_api.py`

**Deliverable:** Mobile and web can read trusted equipment profiles from the backend instead of duplicating profile data.

- [x] Add `GET /machines` and `GET /machines/{slug}`.
- [x] Add `GET /grinders` and `GET /grinders/{slug}`.
- [x] Return profile data plus UI-safe fields: `slug`, `display_name`, `image_url`, `has_image`, compact tags, specs, and short summary.
- [x] Keep JSON profile files as the source of truth for now.
- [x] Keep mobile local image fallback for existing Gaggia/Rancilio/Breville assets.
- [x] Add tests for list, slug lookup, alias lookup, and generic fallback behavior.

## Checkpoint 20: Mobile Machines And Grinders Pages

**Files:**
- Modify in sibling app: `DialedIn/dialedin-mobile/lib/api.ts`
- Modify in sibling app: `DialedIn/dialedin-mobile/app/select-machine.tsx`
- Create in sibling app: `DialedIn/dialedin-mobile/app/select-grinder.tsx`
- Modify/create in sibling app: machine/grinder profile components

**Deliverable:** DialedIn mobile equipment pages use backend profiles and expose grinders as first-class equipment.

- [x] Connect the machines page to `GET /machines` with local fallback and compact cards.
- [x] Add a grinders page connected to `GET /grinders`.
- [x] Sort machines and grinders alphabetically.
- [x] Show machine image when available, otherwise a clean placeholder.
- [x] Show grinder setting type, espresso range, finer direction, and confidence when available.
- [x] Let AI Shot Analysis launch with selected machine and optionally selected grinder.
- [x] Keep offline/local fallback from `data/machines.tsx` until database/API is stable for machines; grinder fallback can be added when we have local grinder fixtures.

## Checkpoint 21: Profile Image Curation

**Files:**
- `services/espresso_mcp/machine_profiles.json`
- `services/espresso_mcp/grinder_profiles.json`
- `services/espresso_mcp/profile_image_candidates.py`
- `services/agent/tests/test_profile_images.py`
- Modify in sibling app: `DialedIn/dialedin-mobile/assets/images/machines/*` as curated local assets are added

**Deliverable:** Every machine profile can expose a reviewed image reference without guessing or hotlinking unreliable images. Grinder profiles remain image-free for now.

- [x] Add optional machine `image` metadata to profile JSON: `url`, `local_asset_key`, `source_url`, `license_or_source_type`, `status`, and `review_notes`.
- [ ] Use existing local images for Gaggia Classic Pro, Rancilio Silvia, and Breville Barista Express.
- [ ] Add admin/research workflow for missing images: find manufacturer/official product image first, then reputable retailer image if needed.
- [x] Only reviewed machine images become app-visible; missing/unreviewed images return `has_image=false`.
- [ ] Prefer curated local mobile assets for core machines now, and S3-hosted reviewed images for expanded/admin-added profiles later; do not hotlink unreliable images in production.
- [x] Require a reviewed image before an admin can promote a new machine profile.
- [x] Add tests that profile API exposes reviewed machine image metadata and hides unreviewed/missing images cleanly.

## Checkpoint 22: Profile Database Migration

**Files:**
- `services/espresso_mcp/profile_repository.py`
- `scripts/profile_repository_cli.py`
- `infra/terraform/database.tf`
- `infra/terraform/outputs.tf`
- `services/espresso_mcp/tests/test_profile_repository.py`

**Deliverable:** Move trusted machine/grinder/profile image data toward persistent storage after the API and UI shape are stable, while keeping JSON as the safe local default.

- [x] Choose DynamoDB as the first persistent backend because current AWS infrastructure already uses DynamoDB/S3 and profile reads are simple key/list lookups.
- [x] Import existing machine and grinder JSON into the dev DynamoDB equipment profiles table. Repeat the import for prod when a prod table is created.
- [x] Keep JSON seed/export scripts for reproducibility.
- [x] Sync trusted profile saves/promotions to JSON seed files when DynamoDB is enabled, unless `DIALEDIN_PROFILE_SYNC_JSON=false`.
- [x] Update machine/grinder loaders and profile promoter to go through a repository abstraction with DynamoDB default when a profile table is configured and explicit JSON fallback for local fixtures.
- [x] Add indexes for profile type and slug in Terraform. Alias/review-status search can stay application-side until admin search needs grow.
- [x] Keep tests able to run without AWS by using local fixtures/mocks.

## Checkpoint 23: Faster Mobile Media Pipeline

**Files:**
- Modify in sibling app: `DialedIn/dialedin-mobile/components/AIShotChat.tsx`
- Modify/create in sibling app: media compression/upload helpers as needed
- Modify/create later: `services/agent/media_jobs.py`
- Modify/create later: `services/espresso_mcp/audio_jobs.py`

**Deliverable:** Make phone video upload and shot analysis feel fast enough for a publishable DialedIn app.

- [x] Ask iOS/Expo to export selected shot videos as smaller H.264 media before upload.
- [x] Reject very long shot videos before upload and ask the user to trim them.
- [x] Show clearer upload/analyze stages in the chat.
- [x] Show the attached shot video inline in the chat instead of a fake preview box.
- [x] Use cached mobile image rendering for machine list/detail cards so S3-backed machine pictures load faster while browsing.
- [x] Return stable reviewed-machine image URLs from the API so mobile image caching can reuse S3-backed machine photos.
- [ ] Measure selected file size and uploaded file size so speed improvements are visible.
- [ ] Add stronger client-side compression/trimming if Expo export is not enough.
- [ ] Investigate uploading extracted audio instead of full video for the analysis path.
- [ ] Add async analysis jobs: upload returns quickly, backend processes in background, app polls result.
- [ ] Persist media-processing status/results in DynamoDB for production reliability.

## Checkpoint 24: Docker Compose

**Files:**
- `compose.yaml`
- `services/frontend/Dockerfile`
- `services/agent/Dockerfile`
- `services/espresso_mcp/Dockerfile`
- `../backend/Dockerfile`
- `../backend/requirements.txt`
- `../dialedin-landing/Dockerfile`
- `monitoring/prometheus.yml`
- `monitoring/grafana/provisioning/datasources/prometheus.yml`

**Deliverable:** Local multi-service stack.

- [x] Containerize frontend.
- [x] Containerize agent.
- [x] Containerize espresso MCP with a health/tool metadata wrapper until MCP stdio transport is wired.
- [x] Add DialedIn Django backend to the compose stack.
- [x] Add DialedIn landing app to the compose stack.
- [x] Add Prometheus/Grafana with Grafana datasource provisioning.
- [x] Verify frontend, agent, espresso MCP, Prometheus, and Grafana run together in compose.
- [x] Verify Django backend and landing app run in compose.
- [ ] Run Expo mobile app against the composed backend stack.

## Checkpoint 25: Kubernetes On AWS EC2

**Files:**
- `infra/k8s/*.yaml`
- `infra/terraform/*.tf`

**Deliverable:** Kubernetes manifests and AWS infrastructure adapted from PolyAIFursa.

- [x] Use PolyAIFursa VPC/Kubernetes Terraform as the base and adapt naming, tags, IAM, ports, and services.
- [x] Add namespaces according to chosen branch/environment workflow.
- [x] Add deployments/services for frontend, agent, espresso MCP, DialedIn backend, and landing app.
- [x] Add readiness/liveness probes.
- [x] Add resource requests/limits.
- [x] Add HPA for agent and frontend.
- [x] Add Route 53/ALB ingress as an opt-in Terraform path.
- [x] Test with `kubectl port-forward` after the EC2 cluster is applied and kubeconfig is available.
- [x] Build and push Linux/AMD64 ECR images for agent, espresso MCP, and frontend.
- [x] Create ECR image pull secret for the dev namespace.
- [x] Verify `/health`, `/machines`, `/chat`, espresso MCP health, Django backend, landing app, and the Next.js frontend through local port-forwarding.
- [x] Set cloud chat/image extraction to a vision-capable Bedrock model for machine/grinder photo recognition.
- [ ] Automate ECR pull auth and deployment in CI/CD instead of manual dev commands.

## Checkpoint 26: Observability

**Files:**
- `monitoring/prometheus.yml`
- `infra/grafana/dashboards/shot-analysis.json`
- `monitoring/alerts.yml`

**Deliverable:** Metrics and dashboard.

- [x] Add request metrics.
- [x] Add audio processing metrics.
- [x] Add profile research metrics.
- [x] Add MCP/tool error metrics.
- [x] Build Grafana dashboard.

## Checkpoint 27: Deployment Automation

**Files:**
- `.github/workflows/ci.yml`
- `.github/workflows/build-images.yaml`
- `.github/workflows/deploy-dev.yaml`
- `.github/workflows/deploy-prod.yaml`

**Deliverable:** Extend the current CI safety net into Docker image build and deployment automation.

- [x] Run unit tests on PRs.
- [x] Run frontend build/type checks on PRs.
- [x] Build Docker images after merge.
- [x] Deploy to dev.
- [x] Add optional SES/SMTP email notification when new machine or grinder profile candidates are captured.
- [ ] Keep production/main deployment protected if used.

## Checkpoint 28: Personal AWS Account Migration Planning

**Files:**
- `infra/terraform/*.tf`
- `infra/terraform/dev.tfvars`
- `infra/terraform/prod.tfvars`
- `.github/workflows/*.yaml`
- `README.md`
- `docs/aws-migration.md`
- `docs/spec.md`
- `docs/plan.md`

**Deliverable:** Make the project ready to recreate the working course-AWS deployment in Ahmad's own AWS account without breaking the current course demo/dev environment.

- [x] Keep the course AWS account as the current demo/dev environment until the personal account deploy is verified.
- [x] Document the current dev deployment as the reference architecture: S3, DynamoDB, ECR, EC2 Kubernetes, Bedrock, email, monitoring, and GitHub Actions.
- [x] Identify every hardcoded account-specific value: AWS account ID, role ARN, bucket names, table names, ECR repos, kubeconfig secret, security group name, public domain, and mobile API URL.
- [x] Decide the personal account environment names, for example `personal-dev` first and `prod` later.
- [x] Add a migration checklist for creating IAM/GitHub OIDC, Terraform state/workspace, ECR repos, S3 buckets, DynamoDB tables, Bedrock access, SES/email, and monitoring in Ahmad's account.
- [x] Plan data migration: export reviewed DynamoDB equipment profiles, export/sync reviewed S3 machine photos, and import them into Ahmad's AWS account.
- [x] Keep `deploy-prod.yaml` protected and placeholder-only until prod infrastructure exists.
- [x] Do not change runtime infrastructure in this checkpoint; this is planning and documentation only.

## Checkpoint 29: Personal AWS Dev Environment

**Files:**
- `infra/terraform/*.tf`
- `infra/terraform/personal-dev.tfvars`
- `.github/workflows/*.yaml`
- `README.md`

**Deliverable:** Run the same working cloud flow in Ahmad's personal AWS account as a new dev environment.

- [x] Document that the current local `default` AWS profile still points to the course account and must not be used for the personal migration.
- [x] Add `personal-dev.example.tfvars` as the safe template for Ahmad's own AWS account.
- [x] Add ECR repositories to Terraform so the personal account can create image repositories from code instead of manually.
- [x] Make GitHub Actions AWS account/role configuration reusable by account and role name, while keeping the course defaults working.
- [x] Create and verify the personal AWS CLI profile `dialedin-personal` for account `577208624033`.
- [x] Create GitHub OIDC role in Ahmad's AWS account for ECR image builds.
- [x] Run `terraform plan` against Ahmad's personal AWS account and confirm the target account ID before applying anything.
- [x] Apply Terraform to create the personal-dev storage/ECR layer: S3 media bucket, DynamoDB profile/history tables, and ECR repositories.
- [x] Import reviewed machine/grinder profiles into the personal-dev DynamoDB table.
- [x] Copy reviewed machine images into the personal-dev S3 bucket.
- [x] Update GitHub Actions vars/secrets in GitHub UI to support the personal-dev account without deleting course-account settings: `AWS_ACCOUNT_ID=577208624033`, `AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::577208624033:role/DialedInGitHubActionsRole`, `AWS_GITHUB_ACTIONS_ROLE_NAME=DialedInGitHubActionsRole`, personal S3/DynamoDB runtime vars, and `DIALEDIN_DEV_KUBE_CONFIG_B64`.
- [x] Build and push images to personal-dev ECR.
- [x] Deploy to personal-dev Kubernetes through manual port-forward-first cloud rollout. Personal-dev now has VPC, one control-plane EC2, one worker ASG, IAM, SGs, SNS alerts, Calico, ECR pull secret, and all five app services running in the `dev` namespace.
- [x] Verify full mobile simulator flow against personal-dev after GitHub vars/secrets are set. Cloud smoke passed for `/health`, `/machines`, S3-backed images, media upload URL generation, chat, espresso MCP, frontend, backend, landing, and Bedrock image recognition.

## Checkpoint 30: Public Personal Dev Ingress

**Files:**
- `infra/k8s/ingress.yaml`
- `infra/terraform/*.tf`
- `README.md`
- `docs/aws-migration.md`
- `docs/plan.md`

**Deliverable:** Expose personal-dev DialChat through a public dev API hostname without port-forwarding.

- [x] Install `ingress-nginx` in the personal-dev Kubernetes cluster.
- [x] Pin ingress-nginx HTTP NodePort to `30080` so the AWS ALB target group can forward traffic.
- [x] Add `dialedin.me` hostnames to the Kubernetes ingress manifest: `api-dev`, `ai-dev`, and `app-dev`.
- [x] Make Terraform ingress support external-DNS mode when the domain is managed outside Route 53.
- [x] Create the personal-dev public ALB and HTTP listener.
- [x] Smoke test `/health` and `/machines` through the ALB with `Host: api-dev.dialedin.me`.
- [x] Add GoDaddy CNAME records for `api-dev`, `ai-dev`, and `app-dev` pointing to the ALB DNS name.
- [x] After DNS resolves, run the mobile simulator against `http://api-dev.dialedin.me`.
- [ ] Add HTTPS/ACM after DNS validation is available.

## Checkpoint 31: Smarter Research Discovery

**Files:**
- `services/espresso_mcp/profile_source_discovery.py`
- `services/espresso_mcp/profile_web_evidence.py`
- `services/espresso_mcp/profile_research_worker.py`
- `services/espresso_mcp/profile_research.py`
- `services/espresso_mcp/tests/test_profile_source_discovery.py`
- `services/espresso_mcp/tests/test_profile_web_evidence.py`
- `services/agent/tests/test_profile_candidates.py`

**Deliverable:** Unknown machine/grinder research should discover likely official sources intelligently instead of depending on hard-coded brand domains or manual URLs.

- [x] Add a Bedrock source-discovery step before profile extraction.
- [x] Ask the LLM for likely manufacturer name, official domain candidates, product page queries, manual/support page queries, and confidence.
- [x] Use web search results to confirm the suggested official domain before trusting it.
- [x] Fetch official product/manual/support pages first, then reputable retailers only as fallback evidence.
- [x] Pass only confirmed evidence into the draft-profile Bedrock extraction prompt.
- [x] If source confidence is low or no official evidence is found, mark the candidate as `needs_manual_review`/`research_failed` with a clear admin reason instead of producing mostly empty JSON.
- [ ] Show source-discovery confidence and found/failed URLs in the admin page.
- [x] Keep manual URL entry as a fallback, not the normal workflow.
- [x] Add regression cases for Quick Mill Silvano Evo and Fellow Opus so future searches do not return zero evidence.

## Checkpoint 32: Production Infrastructure Preparation

**Files:**
- `infra/terraform/prod.tfvars`
- `.github/workflows/deploy-prod.yaml`
- `README.md`
- monitoring/alert docs

**Deliverable:** Prepare production safely, but keep deployment manual and protected until release is ready.

- [ ] Create separate prod resources; do not reuse dev S3 buckets, DynamoDB tables, kubeconfig, or security groups.
- [ ] Configure production domain/API URL.
- [ ] Configure production Bedrock/IAM access in Ahmad's AWS account.
- [ ] Configure production SES/SMTP for real profile-candidate email notifications. Personal-dev SES sender `support@dialedin.me` is verified.
- [ ] Add production rollback instructions.
- [ ] Add production smoke checks and monitoring checks.
- [ ] Require manual confirmation/environment approval for prod deploy.
- [ ] Keep App Store/Play Store builds pointed at dev until prod smoke tests pass.

## Checkpoint 33: Mobile Release Readiness

**Files:**
- sibling app: `DialedIn/dialedin-mobile/*`
- app config/store metadata docs
- `README.md`

**Deliverable:** Prepare DialedIn mobile for TestFlight/Android internal testing.

- [ ] Move API URLs into release-safe environment config.
- [ ] Confirm media upload performance on simulator and real phone.
- [ ] Confirm camera/photo/video permissions and user-facing error messages.
- [ ] Add app privacy notes for uploaded videos/photos and analysis data.
- [ ] Prepare icons/splash/screenshots if needed.
- [ ] Run full cloud smoke on a real device before store submission.

## Checkpoint 34: AI Recognition And UX Improvements

**Files:**
- `services/agent/*`
- `services/espresso_mcp/*`
- sibling app: `DialedIn/dialedin-mobile/*`

**Deliverable:** Improve user trust and reduce wrong machine/grinder recognition after infrastructure ownership is stable.

- [ ] Improve photo recognition prompts and validation so brand-only guesses like `Varia` are not accepted as full equipment models.
- [ ] Add clearer confirmation/correction loops for photo guesses.
- [ ] Track recognition confidence and failure reasons for future tuning.
- [ ] Improve chat recovery when the user sends random text, typos, or corrections.
- [ ] Consider richer image evidence using multiple photos or user-selected equipment type.
- [ ] Keep deterministic recommendation and timing logic unchanged unless separately validated.

## Checkpoint 35: Final Demo

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
- [ ] Show CI/CD dev deploy and cloud simulator flow.
- [ ] Explain personal AWS/prod release path.
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
