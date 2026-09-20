# Interactive PPT + resumable, conversational authoring: execution checklist

Updated 2026-09-20. This is the authoritative implementation checklist. A checked
item means its stated acceptance evidence exists; a source file alone is not a
pass. Each completed numbered work item is committed and pushed before the next
milestone is called complete. Existing user files, website jobs, artifacts and
trajectory originals are retained. Work is on `interactive-runtime` in
https://github.com/dijiahU/rick-ppt.

## Scope and decisions

The requested upgrade has three cooperating systems:

1. **Native + interactive deck authoring.** Direct OOXML remains authoritative for
   native slides. Versioned JSON scenes describe only interactive Content Add-in
   regions. JSON is the normal authoring surface; the agent does not generate
   React for each teaching topic. Native text/equations/charts remain editable.
2. **Recoverable execution.** Keep a durable, host-owned workflow journal and
   checkpoints. Resume the same Codex thread when available and restore a verified
   file checkpoint when necessary. Recovered content is inspected, not executed
   as archived shell commands. Recovery never overwrites the old attempt.
3. **Conversation during creation.** A task-scoped website chat accepts normal
   messages and supported attachments. The running agent receives accepted
   instructions through Codex turn steering; idle or recovered threads receive
   a new turn. Show delivery/acknowledgement and assistant responses. A user
   correction invalidates affected previews and old review/export receipts.

The CNN brief is source material for the first acceptance case. The website saved
language is English. The user subsequently allowed fewer pages when interaction
improves teaching. A separate YOLO case must also use the new capabilities,
including editable executable code in the slide, visual animation and meaningful
learner input. Both cases need actual tests and independent reviews.

## Research findings and unresolved questions

- Read the native README, SKILL, all references/technical references, native
  helpers, every pptx_core module and hooks before implementation.
- Existing native workspace state is v1; package dirty detection excludes any
  external scene files. v2 must track package and sidecar changes separately.
- Native validation used a broad `ppt/slides/` XML test that would misclassify
  `ppt/slides/udata/*.xml`. Limit slide-root checks to actual slide parts.
- Microsoft's official fixture confirms the graph: slide → webextension under
  `ppt/slides/udata/` → snapshot image. `mc:Choice` holds the graphicFrame;
  `mc:Fallback` holds a native picture. Allocate fresh IDs rather than copying
  the fixture's existing duplicate shape ID.
- The official current unified sample uses manifest version 1.27,
  `extensions[].contentRuntimes`, and `presentation` scope. XML compatibility
  manifest uses `ContentApp`. Content and task pane runtimes must be separate.
- Microsoft documents per-instance Office document settings and explicit
  `saveAsync`. Whether injected property values round-trip into settings must be
  tested in desktop PowerPoint, not inferred from the documentation.
- Mac has PowerPoint and LibreOffice installed. Browser, static renderer and
  desktop playback will receive separate verification statuses.
- Current runner uses one-shot `codex exec`, closes stdin after the prompt, and
  records fresh thread IDs per phase. It cannot receive real-time messages through
  that closed pipe. The app-server protocol exposes `turn/steer` with
  `expectedTurnId`, `thread/resume`, streaming assistant messages and interruption.
- Existing trajectory v2 records file bytes, snapshots, phase prompts and thread
  receipts. Its replay tool restores files but explicitly does not resume the
  model or pipeline. Add recovery orchestration, not merely another restore tool.
- Existing portal has owner-authenticated jobs, D1, R2, restricted uploads and
  leased workers. Extend those boundaries for messages/checkpoints rather than
  exposing the local app-server or worker credential to browsers.

Primary sources:
- [Microsoft content add-ins](https://learn.microsoft.com/en-us/office/dev/add-ins/design/content-add-ins)
- [Settings persistence](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/persisting-add-in-state-and-settings)
- [Mac sideloading](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/sideload-an-office-add-in-on-mac)
- [Codex app-server](https://developers.openai.com/zh-Hans/docs/app-server)
- Official OOXML fixture commit: `02e062b75a2e8a79a4a720f73403f0e004e4988f`.
- Official PowerPoint sample commit: `43c823f8ed2bc5fc71f484dc6677155a8c1c9570`.
- Local protocol implementation: `codex-cli 0.155.1`; generated protocol schemas
  will be used to resolve fields instead of guessing from a different CLI version.

## Checklist and acceptance evidence

- [x] **01 — Source/Office research and isolated checkout.** Preserve the live
  queue and source originals; pin the golden fixture and license; record design
  and compatibility constraints. Evidence: implementation-plan.md, fixture source
  and license; commit `820aec1`.
- [x] **02 — Versioned DSL and bounded declarative engine.** JSON schemas,
  migrations entry point, centralized store, safe expression AST interpreter,
  pure registry, bindings, events/actions, transforms, coordinates, timeline and
  seeded compute. Evidence: 26 Vitest tests and production build passed;
  precompiled schema avoids eval in the browser; commit `820aec1`.
- [x] **03 — Complete rendering and interaction semantics.** All specified SVG,
  HTML/media/control primitives; repeat/when; nested row/column/grid layout;
  transform/clip/mask; drag/resize/pan/zoom/scrub/selection/brush; accessibility,
  reduced motion, selective subscriptions and diagnostics. Acceptance: browser
  tests change actual state/geometry, verify keyboard and scaled coordinates,
  restore/reset and capture meaningful states. Evidence: 11 real Chromium semantics tests and 49 Vitest tests passed, including scaled gestures, DOM isolation, media playback/cues, template limits and restored states; retained screenshots inspected.
- [x] **04 — OOXML helper + native regressions.** Discover/attach/update/detach/
  resize/clone; multiple instances per slide and across slides; stable manifest
  ID; snapshots and native underlays; actual golden semantic comparison.
  Acceptance: generated relationships/types match official structure; deliberately
  broken graph/hash/fallback is rejected; unrelated part bytes stay identical;
  native tests still pass. Evidence: 90 Python tests passed (2026-09-20), including official golden structural comparison, six graph corruption cases, clone/resize/detach and unchanged unrelated bytes.
- [x] **05 — Workspace v2, hooks and export safety.** v1 migration; independent
  native/sidecar dirty flags; snapshot and rollback include scenes and receipts;
  pre/post/Stop hooks detect invalid/stale scenes and missing test results; bounded
  Stop failure count remains. Acceptance: rollback restores both stores, export
  does not overwrite originals or existing outputs, no-scene behavior regresses. Evidence: 39 targeted scene/hook tests pass, including sidecar-only writes, preserved rollback copies and the three-attempt Stop cap; prior native regression suite passed.
- [x] **06 — Runtime app, HTTPS, manifests and CLI.** Office onReady/settings
  identity; standalone mode; loopback static/API/WebSocket server with TLS/CSP;
  certificate install/status and doctor; all requested interactive CLI commands.
  Acceptance: build/manifests/doctor run, loopback path/symlink/origin tests pass,
  actual runtime boot checks spec hash and identity. Evidence: doctor reports all dependencies/packs/manifests available; official XML ContentApp validator passes; macOS user-keychain certificate is trusted and Chromium reached actual HTTPS health without bypassing certificate errors. Production pack/browser tests exercise runtime boot. Desktop round-trip remains item 18.
- [x] **07 — Interactive rendering, bundles and review evidence.** Execute JSON
  testPlan; state/visibility/text/property/data/timeline assertions; initial,
  intermediate and reset captures; complete portable directory/ZIP with hashes,
  start/stop scripts and retained native PPTX; review packet integration.
  Acceptance: blank → attach → render → validate → LibreOffice → export → reopen
  → bundle → served preview succeeds and corrupted bundles fail. Evidence: eight actual bundle integration tests plus twenty hook/CLI tests passed (28 total); dirty interactive Stop now creates a fresh bundle outside its workspace home, reports both native path and explicit desktop status. See runtime/docs/bundle-verification.md.
- [x] **08 — First-party components and lightweight maps.** Data/state/theme-aware
  bar/grouped/stacked, line/area/scatter, heatmap/table/KPI/progress/timeline/network/
  matrix/comparison/hotspots/tabs/carousel/tooltip/stepper; GeoJSON Polygon,
  MultiPolygon, Point, LineString with projections and interaction composition.
  Acceptance: representative component/browser tests and a technical showcase. Evidence: shared gallery and chart/map scene browser checks verify data-bearing clicks, tabs, slider, table, chart and GeoJSON selections; screenshots inspected.
- [x] **09 — Lazy extension packs and custom plugins.** Three GLB/orbit/select/
  camera/visibility/explode; Monaco + bounded JS worker/Pyodide execution;
  generic ONNX model runner with WebGPU/WASM fallback and adapters; MapLibre local
  map/allowlisted tiles; KaTeX; same-origin, hashed capability-declared plugins.
  Acceptance: real browser smoke for each pack, code run/reset/timeout/network
  denial, local WASM/assets, core never imports heavy chunks eagerly; size report. Evidence: 12 boundary tests and 7 production-CSP Chromium smokes passed real Monaco, JS/Pyodide, ONNX WASM, GLB/raycast, GeoJSON and KaTeX/plugin behavior. Core-only scene made no pack requests; core gzip 124,908 B; optional local runtime assets about 40.48 MiB; npm audit has 0 advisories.
- [x] **10 — Durable workflow journal and recovery engine.** Record task/run,
  phase/thread/turn, plugin version, revision, message cursor, workspace hashes,
  finished stages, next stage and output receipts atomically. Recover under a
  per-task lock; verify artifacts; fork a new attempt workspace for restoration;
  prefer same-thread resume; rebuild safe context if the thread is unavailable.
  Acceptance: kill/restart during authoring, resume after a finished phase, corrupt
  checkpoint rejection, duplicate recovery exclusion and original preservation. Evidence: 37 standard-library tests passed, including real SIGKILL, commit/projection crash window, uncertain inbox reconciliation and original preservation. Integration remains item 14.
- [x] **11 — Codex app-server transport and live steering.** Stdio JSON-RPC
  handshake; isolated task permissions and environment; streaming public messages;
  turn/start, steer with expected turn, resume and interrupt; maintain heartbeats,
  rendering/media brokers and trajectory recording. Store accepted message IDs
  durably; reconcile uncertain delivery before retrying. No private reasoning or
  host credentials enter website messages. Acceptance: actual small live Codex
  exercise receives an in-progress correction and resumes an interrupted thread. Evidence: 20 protocol tests and a real 49-second Codex 0.155.1 exercise passed outside read/write/network denial, same-turn steering, client-message reconciliation, interruption, server restart and same-thread context recovery. Public assistant messages exclude private reasoning.
- [x] **12 — Conversation/checkpoint backend.** Additive D1 migrations for
  task-owned messages, attachment metadata, worker acknowledgements and recovery
  state. Owner-only reads/writes; lease-checked worker delivery; bounded payloads;
  idempotent client message IDs; attachments hashed and downloaded into task scope;
  resume does not charge new quota or erase prior attempts. Acceptance: ownership,
  cross-user denial, races, upload limits, duplicate sends, lost response and
  stale-lease tests; old worker routes remain compatible. Evidence: isolated SQLite/R2 handler suite passes; upload, claim, language and worker recovery regressions pass. D1 migration is additive; source excludes local credentials.
- [x] **13 — Website conversation UI.** Live transcript beside previews; ordinary
  chat and modification requests; attach files with upload/error/progress state;
  sent/received/applied status; assistant replies; reconnect without duplicate
  messages; resume affordance and clear recovery status. Preserve existing design,
  language selection, task history and current execution. Acceptance: real browser
  submit/upload/reconnect/resume flows plus production build. Evidence: Playwright desktop/mobile suite passed actual local routes, upload and applied status, reload/dedup, ordinary chat and same-task resume; final production build passed. No production fixture or user quota was changed.
- [x] **14 — Workflow integration and release.** Planning chooses native versus
  interactive treatment; runner exposes the installed runtime and test broker;
  revisions invalidate affected output/review evidence; independent reviewers
  inspect interactive captures; deliver PPTX plus bundle. Update SKILL, README,
  references, architecture, compatibility and manual desktop instructions.
  Package/reinstall versioned plugin without deleting prior cache versions.
  Publish the validated site and drain/handoff workers without interrupting old
  tasks. Acceptance: deployment success and new-worker capability checks.
  Evidence: website v23 deployed successfully; installed and staged plugin
  `0.1.0+codex.20260919214127` preserves all 17 previous cache versions. Installed
  doctor and filesystem/network isolation checks passed; actual native Docker
  rendering passed on the same frozen runtime. With no queued/running jobs, old
  worker 12123 drained normally. After the installed-version and Office identity
  corrections, worker 4473 passed startup checks and began the real CNN research
  phase at 2026-09-19 21:42 UTC. Private `worker-handoff.json` and
  `worker-handoff-office.json` preserve both transitions. Website v25 retains the
  same new task and a visible explanation of the first pre-authoring failure.
- [x] **15 — Full smoke gate.** Python, Vitest, Playwright, production build,
  bundle-size guard, malicious input tests, native OOXML regression, LibreOffice,
  bundle boot, all optional packs, resumability and live feedback. Record exact
  commands/results. Only after this gate run both teaching cases. Evidence:
  [release-smoke-20260920.md](release-smoke-20260920.md) records 134 Python,
  79 Vitest after the Office identity correction, 23 combined browser, three production diagnostics, eight production
  pack checks, 30 website checks and the workflow/runner suites. A real 20m55s
  Codex/native/interactive/review/delivery exercise passed 20 checks; final frozen
  candidate revalidation passed eight checks with identical reviewed scene
  captures. Linux GitHub verification passed on `a2f1bce`. Desktop host behavior
  is explicitly unverified under item 18.
  Installed-cachebuster startup regression adds 70 passing workflow checks and
  a real create/reopen/recover preflight before queue polling. Initial case runtime
  fingerprint was `fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de`;
  fresh host/native/bundle revalidation again passed eight checks on that build.
  The subsequent CNN-discovered Monaco correction passed 79 unit, 24 browser,
  nine production-pack, three diagnostic and eight host/native/bundle checks.
  Its immutable Monaco release is `0.1.0+codex.20260919230549`, fingerprint
  `be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
  The same CNN task restored its saved work under that release; see the linked
  smoke report for scope and retained earlier evidence.
  The subsequent local-font correction passed nine production pack checks and
  eight fresh host/native/bundle checks; release `0.1.0+codex.20260919234350`
  is now installed and staged, fingerprint
  `8635c55584176218c6eadbc829d8796531bc99887469f24f6fc2345130222d37`.
  A real HTTP/2 checkpoint interruption also led to 13 passing transport and 37
  conversation checks for nonfatal transient publication and preserved identities.
- [ ] **16 — CNN case.** Write a reproducible prompt from the latest website
  brief, emphasizing first-principles computation, definitions, worked arithmetic,
  forward/backprop, training and annotated runnable code. Use composable scenes
  for convolution window movement, kernel/stride/padding, nonlinearities, pooling,
  gradients and learning; editable code runs inside the slide. Choose enough pages
  for depth. Test interactions, review content/visuals independently, export and
  verify an actual bundle. Keep the original website task unchanged.
  Progress: all 20 pages exported; the host independently passed 194 scene tests
  and 679 assertions. [Frozen-candidate checks](cases/cnn-frozen-review.md) add
  source/hash correlation and targeted learner-input evidence. A 900-second
  review timeout retained the completed author receipt; the same-version worker
  restored revision 9 for review with 2700-second phase budgets. Independent
  review approval and actual delivered-pair retrieval remain open.
- [ ] **17 — YOLO case.** Write a comparable prompt teaching detection, boxes,
  grid/head outputs, IoU, confidence thresholds, NMS, loss/training and inference.
  Distinguish versions precisely; demonstrate editable code and intuitive animation
  through the shared DSL/runtime/ML adapter. Test, independently review, export and
  verify the second bundle. Do not build a separate YOLO runtime. Preparation:
  the [pinned independent numerical reference](../examples/yolo-reference/README.md)
  passes 75 checks, including IoU/NMS/DFL, CIoU and toy-logit optimization. A
  [separate real-model probe](../examples/yolo-reference/real-model.md) passes
  11 browser and nine import checks with genuine pretrained YOLOv8n weights.
  Neither probe accepts a finished teaching deck.
  The [v003 admission preparation](cases/yolo-preparation.md) adds lessons from
  actual CNN edits and passes 14 executions over seven queue/identity boundaries;
  CNN generation, functional tests and native inspection now precede admission;
  its remaining independent audience reviews may overlap YOLO creation. Both
  final acceptance gates remain required.
- [ ] **18 — Desktop verification and final report.** Attempt real macOS
  PowerPoint open/load/click/drag/keyboard/slider/slideshow/save/reopen/settings
  persistence and code interaction. Windows/Web are only marked verified if
  actually tested. Report architecture, changed files, security, tests, sizes,
  limitations, exact setup/authoring/presentation commands and both case links.
  At 2026-09-20 00:52 UTC, replacing the standalone Computer Use helper with the
  newer, verified official bundled version restored its accessibility tree and
  screenshot API. The original signed application and all 167 inventory entries
  are retained. No security settings or Office license were changed. PowerPoint
  opened in its available read-only mode after skipping subscription offers;
  artifact playback and editing/save behavior still need actual checks.
  Subsequent official file-dialog actions exposed an independently confirmed
  helper crash; [the attempt record](desktop-verification-20260920.md) preserves
  the distinction between a visible native preview and actual document playback.

## Recovery semantics

Checkpoint boundaries are phase completion, successful exported version, accepted
user revision and stable file snapshots. A running phase records its thread ID
as soon as the app-server acknowledges it. Recovery validates the task identity,
runtime version, snapshot hashes and last applied message cursor. It does not
assume a sampled in-tool file snapshot is transactionally coherent: restore into
a new directory, validate native/scene state, and ask the resumed model to inspect
and repair before publishing. Already completed stages are skipped only when their
input revision and required artifacts still match. A previous delivered artifact
is immutable; later work becomes another version.

A website message first becomes durable, then is picked up by the leased worker.
An acknowledgement means the runtime accepted the instruction, not that the
requested edit is finished. Completion is attached to a new validated revision.
If turn steering races with turn completion, resynchronize the active turn and
start the next turn once. If the worker dies after acceptance but before website
acknowledgement, use the host inbox ledger/thread events to reconcile it. Never
blindly replay all old instructions or silently drop attachments.

## Release discipline

Each work item gets its own implementation/test commit and a checklist update.
Use additive database migrations and a new plugin version. Do not replace live
workers until the matching website protocol is deployed. Retain rollback source,
previous installed runtime, old manifests, trajectory originals and delivered
files. A real environment blocker is marked NOT RUN with a reason while all
independent work continues. No claims of desktop verification from browser PNGs.
