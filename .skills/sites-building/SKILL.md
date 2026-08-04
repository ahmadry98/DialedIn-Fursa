---
name: sites-building
description: Use Sites to build websites, including landing pages, portfolios, dashboards, portals, trackers, hubs, and internal tools. Always use Sites when the project contains `.openai/hosting.json`.
---

# Sites building

Build the complete requested site, validate it, then use `sites-hosting`
unless the user explicitly asks to keep it local.

## Communicate clearly

Assume the user is a nontechnical knowledge worker. Talk about their site,
choices, progress, and results. Keep tools, commands, files, runtimes, browser
software, permissions, dependencies, source control, credentials, IDs, builds,
and deployment internals out of user-facing messages unless the user asks or
must take action.

Use no more than one short update for each user-visible phase: preparing design
options, building the selected option, and publishing. If a phase takes longer
than 60 seconds, give one plain-language update. Keep recoverable technical
problems private; say only that you hit a problem and are trying another method.

## Choose the execution path

Use the **one-shot fast path** only when all of these are true:

- this is a new site in an empty or projectless workspace;
- one route can satisfy the request;
- the request does not require D1, R2, uploads, app-owned authentication,
  external connectors, or browser UI QA; and
- the normal deliverable is a private deployed URL.

Use the **capability path** otherwise. This includes existing-site changes,
multi-route sites, persistent data, uploads, authentication, external data, and
requested browser testing.

## Use imagery purposefully

Avoid model-authored SVGs in finished sites, including inline SVG
illustrations. Prefer strong typography, color, layout, CSS shapes, and existing
icon components when imagery is unnecessary. When a site needs real imagery,
prefer suitable images found through web image search. Use `imagegen` if and
only if original imagery is important and a suitable existing image is
unavailable; generation adds latency, so keep it purposeful and limited.

## Start new projects immediately

For a new site in an empty or projectless workspace, make setup the first task
action. Run this plugin's root-level `scripts/init-site.sh` with `$PWD` as its
target and retain the session until installation completes. Do not run a second
initializer.

In a visible foreground thread, wait for setup to finish, then immediately start
`npm run dev` in a retained session. Use the exact Local URL printed by the
development server and call `open_in_codex` once. Complete these startup steps
before asking discovery questions, calling `request_user_input`, or showing a
design picker. The user should see the starter loading skeleton before
implementation begins; continue building the requested site through HMR and
keep the development server alive through build and hosting.

In a delegated, background, or invisible thread, initialize normally but do
not start a browser-only preview unless the task otherwise needs the server.

## One-shot design choices

This flow is unrelated to the Codex Apps `$one-shot` UI-regression skill. Use
one to four sequential design pickers before editing the site. Choose only
decisions that materially improve the result, stop when the design is clear,
and never exceed four pickers. Wait for each selection before preparing the
next picker so later options can build on earlier choices. Skip the flow if the
user wants to proceed without choosing an option.

Before generating previews, normally call `request_user_input` 1-3 times to
learn what matters most for this site. Ask short, tailored questions about
things such as the audience, purpose, content, tone, or desired feeling. Skip
questions the user has already answered, and skip this step only when the user
has given unusually complete direction or asks you to decide. Then use the
design picker for a visual choice that is easier to judge by seeing it.

1. Choose the next useful design decision to compare. It may be a color palette,
   layout, typography pair, visual density, component style, illustration
   language, or full-page direction. Create a temporary directory outside the
   site source for the options. Start project setup first. In a visible
   foreground thread, the starter loading view should already be open before
   asking the user to choose. Do not edit product files before the user chooses.
2. Spawn exactly three subagents in parallel to create three distinct options.
   Give them the same content, viewport, aspect ratio, and medium. Default to
   HTML whenever HTML and CSS can show the decision clearly. If unsure, use
   HTML.
   - Use HTML for palettes, typography, high-level layouts, spacing, navigation,
     component styles, and other interface choices. Create three simple page
     mockups or specimens with realistic shared content so the difference is
     easy to compare. For layout choices, use abstract wireframes with labeled
     regions, boxes, lines, and simple CSS shapes. Keep color, typography, and
     content neutral and consistent so the layout is the clear variable. Do not
     add decorative imagery, illustrations, or model-authored SVGs to layout
     previews. Reference `Visualize:visualize` for composition, responsive
     layout, typography, and accessibility. Each subagent creates one
     self-contained HTML file outside the site source. The parent renders all
     three files to images after they return; subagents do no browser work. Do
     not use the inline-visualization response directive.
   - For a Work image-picker decision, use `answers-image-picker` to
     generate exactly three comparable imagegen previews in the background.
     Start every preview prompt with the exact literal prefix
     `[image_picker_background_preview]`; do not alter, omit, or paraphrase it.
     Work uses that prefix to hide only these preview imagegen messages.
     Do not announce the skill, preview generation, or imagegen calls in
     user-visible commentary.
     Treat the final picker as the decision surface for this phase. Each
     direction uses realistic product content and no browser chrome, device
     frame, montage, unrelated logo, or watermark.
   Each subagent returns a unique id, short title, absolute artifact path, and
   implementation-ready brief. Include exact values when useful, such as
   colors, font families and weights, layout regions, spacing, imagery,
   interaction, and motion.
3. Wait for all three options. Retry missing or unusable options until all three
   are ready. When `answers-image-picker` is available, use the three returned
   absolute saved paths from its background imagegen previews and skip the HTML
   renderer. For Codex-app fallback HTML options on macOS, run the bundled root-level
   `scripts/render-html-previews.sh` once for all three files, with elevated
   permissions on the first attempt. It produces three consistent 1600×1000 PNG
   files. Never install or invoke standalone Playwright, Chromium, or other
   browser software. On another platform, or after one helper failure, use the
   in-app Browser once. If neither renderer is available, offer the briefs as
   text instead of installing software or retrying repeatedly. Keep renderer
   setup and recovery out of user-facing messages.
4. In Work, when the `answers-image-picker` answer skill is available,
   invoke `image_picker` with a question tailored to the decision and exactly
   three `{ id, title, image_path, selection_context }` options. Pass each
   background imagegen preview's returned absolute saved path as `image_path`;
   never invent, rename, shorten, or copy a path from an example. Work promotes
   those generated paths to Sediment URLs before the frontend renders them. Map each
   implementation-ready brief to `selection_context`.
   The final answer must contain the single `image_picker` genui citation;
   do not merely announce that the previews were rendered, and do not add
   prose before or after the citation. Then end the turn and wait for the
   user's choice.
   Use the selected context for that decision while preserving the user's
   other requirements. The follow-up turn includes the selected preview image;
   inspect it and treat its visual details as the source of truth when they
   differ from the prose brief. Continue with the Sites workflow instead of
   answering with standalone HTML.

   When the answer skill is unavailable, keep the Codex-app fallback: call
   `choose_site_design` with the same question and three
   `{ id, title, imagePath, designBrief }` options. If the user skips either
   picker, ask whether to retry, use the strongest option, or stop. If neither
   picker is available, offer the options as text. For the MCP fallback,
   continue in the same turn unless the user asks to stop. If another distinct
   visual decision would materially improve the site and fewer than four pickers
   have been shown, repeat this flow using every previous selection as a
   constraint. Never open multiple pickers at the same time.

## One-shot build

After the final selection, build and deploy the complete site in one focused
pass.

1. Reuse the retained setup, development server, and browser tab started above.
   Start or open anything here only when the corresponding earlier step did not
   happen. Preserve the package manager and lockfile.
2. Start by inspecting `app/page.tsx`, `app/layout.tsx`, `app/globals.css`, and
   `.openai/hosting.json`. Read other files only when the implementation needs
   them. Avoid broad scans and speculative research.
3. Make one complete product patch. Prefer one page component and one
   stylesheet. Include all requested content, interactions, responsive
   behavior, keyboard and touch behavior when relevant, and accessible labels.
   The starter loading skeleton is temporary infrastructure, not product UI.
   Once the requested first version replaces it, remove `app/_sites-preview`
   and its imports. If nothing else uses `react-loading-skeleton`, remove that
   dependency and refresh the lockfile. Remove the temporary `codex-preview`
   metadata marker, replace the starter title and description with the requested
   site's own values, and update starter icons when appropriate before the final
   build unless the user explicitly asked to work on the starter itself.
4. As soon as implementation is complete, run `npm run build` while the
   retained `npm run dev` process stays alive. Fix actual build failures, then
   rerun it. Run lint separately only if the build omits compilation or the user
   asks.
5. Follow the shared preview rules below.
6. Continue to `sites-hosting`. Avoid an unnecessary polish pass after the
   build succeeds.

## Capability path

### Project setup

- For a new site, use the setup flow in **Start new projects immediately** and
  preserve the bundled vinext structure.
- For an existing site, preserve its package manager, lockfile, scripts,
  architecture, and `.openai/hosting.json`. Install only when dependencies are
  absent. Do not replace a working structure merely to use the starter.
- Keep site code within the selected project surface.

### Shape the product

- Build the first viewport around the requested product, not generic dashboard
  chrome.
- For a new site, replace the starter loading skeleton completely and remove
  `app/_sites-preview` and its imports. Remove `react-loading-skeleton` and
  refresh the lockfile if the finished site no longer uses it. Remove the
  temporary `codex-preview` metadata marker, update `app/layout.tsx` with the
  finished site's title and description, and replace any other starter metadata
  before final validation. Preserve the skeleton only when the user explicitly
  asked to work on the starter itself.
- Use concrete, product-specific copy and realistic data.
- Once the site's visual direction, primary headline, and supporting copy are
  stable, freeze a compact social-preview brief and launch exactly one
  `imagegen` request in parallel with the remaining site implementation and
  validation. Ask imagegen to create the complete social card, including its
  typography, as one cohesive landscape image. The card must represent the
  actual finished site by reusing its content, brand palette, typography
  treatment, and distinctive visual motifs; optimize it for visual impact and
  legibility in X, Slack, iMessage, and other link unfurls.
- Inspect the returned image for incorrect, missing, or invented text. Retry
  once only when the card is unusable; do not generate multiple candidates in
  parallel. If validation succeeds, save the image as `public/og.png` and update
  `app/layout.tsx` with site-specific Open Graph and X metadata using an absolute
  URL derived from the incoming request host. Run the final build after wiring
  the asset. Never ship a generic or starter fallback image; if no bespoke card
  passes validation, omit `og:image` instead.
- Avoid speculative features and unnecessary client state.
- Use the starter's `sites()` Vite plugin and produce Cloudflare
  Worker-compatible ESM output.

### Add only requested capabilities

- For durable state, records, uploads, or other persistence, read
  [Persistence and storage](references/persistence-and-storage.md).
- For identity-aware or sign-in-gated behavior, read
  [Authentication](references/authentication.md).
- Use browser storage only for device-local preferences or explicitly local
  state.
- Keep logical D1 and R2 declarations in `.openai/hosting.json`; Sites owns the
  real Cloudflare resources and deployment wiring.
- Keep local `.env` and `.env.example` keys aligned. Manage hosted runtime
  values through Sites.

### Validate capability work

- Run the deployment build once after the complete implementation. If a D1
  schema changed, generate and inspect its migration. Fix real failures before
  hosting.

## Preview

- In a visible foreground thread, reuse the tab opened during startup. If no tab
  was opened, call `open_in_codex` once with the exact Local URL printed by the
  healthy development server. If it fails, report it and continue.
- For an existing site, preserve its normal package and development flow.
- In a delegated, background, or invisible thread, skip `open_in_codex` and say
  why.
- Perform no screenshots, DOM inspection, clicking, resizing, or visual QA
  unless the user explicitly requests browser testing.
- Do not scan ports or repeatedly open the browser.

## Hosting handoff

Use `sites-hosting` after validation. Do not finish with only a local build
unless the user requested local-only work. Return the deployed Sites URL as the
primary deliverable. Do not include file paths, commands, or validation jargon
unless the user asks. Keep the development server running until hosting
finishes, then stop it during final teardown.
