# Requirements audit — 2026-09-20

Source: the complete 65 numbered sections (0–64) in Rick's `需求文档`, plus the
subsequent requests for a checked execution plan, GitHub milestones, recovery,
live task conversation/attachments, and CNN/YOLO acceptance cases. Audit baseline:
commit `b57d469`, followed through the final runtime build at
2026-09-19 21:11:48 UTC. The resolution ledger records the subsequent fixes and
actual checks. Release/teaching cases and desktop verification remain separate
gates; this audit is not a release certificate.

I read the whole requirement and inspected the runtime, schemas, OOXML/sidecar
helpers, hooks, bundle assembly, review inventory, host broker, runner recovery
entry point and outline contract. Existing evidence was compared with the actual
assertions, not just test filenames. Two discovered core defects were then fixed
at the parent's explicit request; their targeted checks are listed below. No
website history or original presentation was modified for this audit.

## Evidence vocabulary

- **Implemented / exercised** means the implementation exists and relevant real
  assertions have run. It does not imply every possible composition is tested.
- **Partial** means a required part or its evidence is missing; the gap is named.
- **Pending integration** means independently tested parts exist but the complete
  released path has not passed its final gate.
- **Not desktop-verified** means no actual PowerPoint host proof exists.

Primary existing evidence:

- `pptx-agent/runtime/docs/runtime-semantics.md`: core browser semantics and the
  representative component/gallery scenes. Final combined runtime checks:
  **54 Vitest and 23 Chromium tests passed**, including 12 core semantics,
  three diagnostics/performance and eight feature-pack cases.
- `pptx-agent/runtime/docs/feature-pack-verification.md`: 14 extension boundary
  tests and eight production-CSP Chromium checks using real Monaco, JS/Pyodide,
  GLB/raycast, ONNX WASM, MapLibre and KaTeX/custom plugin execution.
- `pptx-agent/runtime/docs/diagnostics-performance.md`: final build and size
  inventory, production structured-error checks and a measured 504-node scene.
- `pptx-agent/runtime/docs/technical-showcase.md`: four native slides, six
  interactive regions, 18 test cases and 34 assertions through attach, reopen,
  portable bundle and served preview.
- `pptx-agent/runtime/docs/bundle-verification.md`: original seven real bundle
  checks and five real-workspace relocation checks; later strict-receipt work
  expanded the bundle suite to 13 passing tests as recorded by its owner.
- `docs/interactive-runtime-plan.md`: Python, Office fixture, server/TLS, journal,
  actual app-server steering/restart and portal evidence maintained by their owners.
- `runner/INTERACTIVE.md`: 15 host broker tests, including real rendering and
  native export plus rejection of forged receipts and changed frozen bytes.

These records have different scopes. A browser PNG, native LibreOffice render,
schema comparison and desktop PowerPoint playback are four distinct observations.

## Priority gaps and resolution ledger

| ID | Priority / requirement | Finding and consequence | Resolution / remaining evidence |
| --- | --- | --- | --- |
| A1 | P1 · §§7, 11, 14, 15 | A registered declarative function called by an action lost state/data/event/locals. Read-only reproduction: `plus(2)` with `state.n=7` yielded 9 as an expression but `NaN` through `call`. | **Fixed.** `Expressions.call` scopes/restores the environment and actions use it. A regression checks nested functions with all four contexts and cleanup after an exception; the final 54-test suite passes. |
| A2 | P1 · §§4, 16, 20, 21 | Repeated feature components shared the authored node ID as controller key. Two editors could run the other's source; unmounting one could remove the other's controller. | **Fixed in this audit.** Qualified instance keys reach packs; runtime event mapping retains authored targets and supplies `instanceId` plus repeat locals. A real two-Monaco test passes independent run/source/result, addressed actions, event locals and surviving-controller behavior after one instance is removed. |
| A3 | P1 · §§3, 11, 20, 21 | Formal action schema originally allowed only array `args`, while documented pack actions consume named object arguments. | **Fixed.** Conditional schema accepts named object/array plugin arguments while keeping pure `call` positional. The showcase passes real CLI `validate-spec` → attach → authored Button actions `code.setCode`/`code.run` → export/reopen/bundle; results 7→14 and 12→24 are asserted through a custom plugin function. |
| A4 | P1 · §§33, 37 | `hooks.stop()` originally chose a destination that `assemble_bundle()` rejected; its success message omitted the separate PPTX and verification flags. | **Fixed by root in `b57d469`.** Safe output placement and explicit artifact/verification messages pass 28 targeted tests, including the actual dirty Stop path. |
| A5 | P1 · §§21, 29, 33 | Multi-file glTF URI dependencies and several bare component asset fields originally did not survive hash-based import. | **Fixed by root in `b75c2f7`.** Local dependency copying/URI rewriting and bare asset imports pass 24 unit tests. The technical showcase additionally loads/selects a real `.gltf` plus external `.bin` after attach/export/reopen/bundle and observes a successful served binary request; original assets are unchanged. |
| A6 | P1 · §§41, 42 | Outline normalization originally dropped `presentationMode` and `interaction`, excluding changes from the page revision. | **Fixed.** Runner `673832a` preserves fields/revisions and old outlines (five checks); website `612fcc8`, deployed v23, preserves the same fields (four checks). |
| A7 | P1 · §40 | Review packets originally omitted the declared behavioral inventory for each interactive region. | **Fixed in `d2b3bd3`.** Scene-derived events/actions/behaviors/timelines/data/packs and capture/test paths are included; eight tests pass with standalone-versus-desktop flags preserved. |
| A8 | P1 evidence · §52 | Separate browser fixtures did not constitute the required combined native technical showcase. | **Closed by actual showcase.** Four native slides/six interactive regions run 18 test cases with 34 assertions through attach/render, export/reopen/rerender, bundle/checksums and served preview. It includes controls/state/drag/keyboard, chart/GeoJSON, CSV, timeline/compute, media, editable code, custom plugin and external glTF. It is a synthetic engineering fixture, not a CNN/YOLO lesson. |
| A9 | P1 release · user additions, §§41, 62–64 | The initial audit identified installed plugin/worker handoff, the full smoke gate and two teaching cases as release milestones requiring integrated evidence. | **Smoke passed; release/cases separately tracked.** `docs/release-smoke-20260920.md` records the 134 Python, runtime, runner and website results, real 20-check workflow and final eight-check exact-candidate revalidation. The portal is deployed at v23. Installation/handoff remains in the execution plan, followed by CNN/YOLO artifacts. Neither teaching case is claimed complete by this audit. |
| A10 | P2 required · §§43, 44 | CI, expanded diagnostic counts, pack-size UI, a meaningful density threshold and representative timing evidence were missing. | **Fixed/exercised.** `.github/workflows/interactive.yml` runs build/300,000-byte gzip gate and actual suites. Debug counts expand repeat/components, display core/pack sizes, and use `canvasThreshold` only as an explicit Canvas advisory. A production 504-node/1,502-binding scene records actual drag/slider/timeline rAF intervals and input-to-DOM latency. See the performance report for measured values/limits. CI's negative initial rAF delta and test-server optimizer reload failures were diagnosed from traces and fixed; final local 23-browser suite passes. |
| A11 | P2 required · §47 | Errors lacked consistently structured scene/node/expression/asset/plugin/stack context. | **Fixed/exercised.** `diagnostics.ts` preserves structured context through expressions, bindings, actions, assets, renderer, pack/plugin loading and boot/runtime failures. Production-browser debug assertions verify scene/node/expression/asset and stack while the concise static-fallback message remains. Pack-local capability errors remain component-local UI messages; absent context is not fabricated. |
| A12 | P2 assurance · §§31, 32, 37, 38 | Local receipts originally did not bind capture existence, nonempty assertions or the tested runtime bytes. | **Fixed by root in `b75c2f7`.** Receipts now bind version, complete runtime/config hashes, scene/test-plan counts, all actual PNG hashes, and initial/reset captures. Changed paths or runtime invalidate them and require rerender. Owner reports 24 unit, 13 real bundle and 12 host tests passing; the showcase uses these strict receipts. The website still independently reruns frozen input. |
| A13 | P1 host proof · §§23, 25, 54, 55 | XML fixture equivalence and the standalone browser pass do not establish injected property-bag → `Office.context.document.settings`, slideshow input/focus or save/reopen persistence. PowerPoint exists locally but Browser/Sky automation is unavailable. | **Not desktop-verified.** Retain the manual checklist and explicit matrix status. Continue independent development; do not replace missing desktop proof with LibreOffice/browser claims. |

P1 identifies a required functional or release/proof gap, not a suggestion to
block unrelated progress. P2 identifies a required assurance/detail gap that does
not invalidate the existing small-scene browser results. Parent-owned fixes must
be marked complete only after their own evidence is recorded.

## Section-by-section traceability

Paths below are relative to the repository. `R/` means `pptx-agent/runtime/`;
`P/` means `pptx-agent/skills/pptx/scripts/`; `S/` means
`pptx-agent/skills/pptx/schemas/`.

| Requirement section | Implementation and concrete evidence | Status / limit |
| --- | --- | --- |
| 0 · additive native authority | Native `P/pptx_core/package.py`, snapshots, manifest comparison and OOXML export remain; interactive DSL lives in sidecars. Bundle test checks original, native part and sidecar hashes unchanged. | Implemented / exercised; no python-pptx substitution or native-slide conversion observed. |
| 1 · shared composable runtime | `R/src/core/runtime.ts` composes store, safe expressions, data, events/actions, behaviors, timelines, compute and component registry. Core gallery and charts share it. | Implemented / exercised; CNN/YOLO teaching cases pending. |
| 2 · React/TS/Vite, lazy heavy packs | `R/package.json`, app, SVG/HTML/Canvas renderers, dynamic imports in feature-packs. Core-only production browser case observes no optional chunk/WASM requests. | Implemented / exercised. |
| 3 · versioned formal DSL | `S/interactive-slide.schema.json`, compiled JS validator, Python/TS explicit migration dispatch, bounded tree validation, logical viewport and ResizeObserver. | Implemented for v1; future migration dispatch is present. Conditional object plugin args pass formal CLI validation and actual authored actions in the showcase. |
| 4 · primitives/repeat/when | `R/src/renderer/NodeRenderer.tsx`, `HtmlRenderer.tsx`, `CanvasRenderer.tsx`; real vector/HTML/media gallery and repeat/budget checks. | Implemented / exercised; A2 fixes repeated feature instances. |
| 5 · layout | `layoutChildren` supports absolute/row/column/grid, padding/gap/align/justify/rows/columns; bound dimensions and expanded repeat are tested. | Implemented for documented scalar padding and start/center/end alignment. |
| 6 · independent centralized store | `R/src/core/store.ts`: path updates, atomic batch, rollback on derived failure, selective subscriptions, reset/snapshot/restore. DOM mutation test confirms unrelated node unchanged during drag. | Required features exercised. Undo/redo are optional; see optional scope below. |
| 7 · safe expressions | `expressions.ts` uses jsep AST evaluator, own-property reads, whitelisted functions/Math, no DSL eval/Function, depth/length/budget guards. Security tests present. | Implemented / exercised; A1 fixed action invocation context. |
| 8 · bindings | `bindings.ts` resolves props and `bind`, with state/data/derived/local context; per-node selectors and bound layout/visibility tests. | Implemented / exercised. Event values are captured through actions; event context is ephemeral. |
| 9 · data sources/transforms | `data.ts`: inline/local JSON/CSV; optional HTTP/SSE/WebSocket, transforms, dependency ordering, `_dataStatus`, stale-request cancellation and last-known rows. | Local/HTTP/transform cases exercised; real SSE/WebSocket streaming not separately demonstrated by browser tests. Server WebSocket nonce tests are a different surface. |
| 10 · events | Renderer emits pointer logical/local coordinates, modifiers/value/delta/IDs, native input/change/focus/blur, keyboard, hover and scene events; Runtime supplies timers/custom events. | Browser interaction coverage present; not every event kind independently asserted. |
| 11 · actions | `actions.ts` implements required state/data/timeline/loop/navigation/function actions, sequence/parallel/condition/delay, shared action limit and awaited plugin actions. | Exercised; A1 and A3 fixed and formally authored plugin actions pass the complete native/bundle chain. |
| 12 · behaviors | `behaviors.ts`: all nine named behaviors, local/parent coordinate transforms, bounds, axis, grid/scalar snap, min/max and constraints. | Real drag/resize/brush/pan/zoom/scrub/hover/select tests; touch-specific device run not required and not claimed. |
| 13 · timelines | rAF engine handles seek/play/pause/stop, delay, markers, loops/reverse, bound options, numbers/arrays/objects/hex colors, compatible path tokens; incompatible paths reject. | Unit/browser checks; semantic intermediate state and reduced-motion endpoints tested. CI negative initial rAF timestamps are clamped without changing end-state assertions. Color interpolation accepts documented hex forms. |
| 14 · compute | Derived state, event actions, seeded RNG and named tick loops with delta/elapsed time in `compute.ts`. Reset cancels loop frames. | Deterministic seed and real compute start/stop/tick/elapsed/reset assertions pass in the showcase. A10 measures a short representative timeline/drag/slider scene, not a long-running physics simulation. |
| 15 · function registry | Builtin math/stats/geometry/color/string/array/interpolation helpers plus declarative functions and capability-declared plugin functions. | Exercised; A1 fixed. Scene function imports remain prohibited. |
| 16 · first-party components | `components/registry.ts` implements the full named chart/table/KPI/progress/network/matrix/comparison/hotspot/tabs/carousel/tooltip/stepper set as primitives. | Representative data/selection/theme browser tests and gallery; not every parameter combination proved. |
| 17 · lightweight geo | GeoJSON Polygon/MultiPolygon/Point/LineString, holes, layers, projections, selection metadata; pan/zoom/hover composed through shared behaviors. | All four geometry types and actual selection/pan/zoom exercised. |
| 18 · media | Native audio/video elements, controlled rate/volume/mute/time, cue actions, timeline seek, posters and cleanup. Real local WAV and WebM fixtures. | Actual playback/time/cue/reset browser checks; PowerPoint autoplay/focus remains A13. |
| 19 · user/file input | Text/textarea/slider/select/toggle/FileInput; JSON/CSV parsing and session-owned image Blob URLs; 32 MiB upload bound, no filesystem API. | Browser input and JSON upload exercised; no persistence adapter claimed. |
| 20 · extension architecture | Lazy feature imports, extension components/actions/functions/data adapters, init/disposal registration, explicit scene `requires`. | Implemented / exercised; A2 and A3 close composition/authoring gaps. |
| 21 · five real optional packs | Three, Monaco worker/Pyodide, generic ONNX worker/WebGPU→WASM, MapLibre and KaTeX are actual libraries with local assets. | Eight production browser smokes pass; the combined showcase additionally proves external glTF dependency portability. Hardware WebGPU and arbitrary tile providers remain unverified. |
| 22 · deck plugin | `plugins/loader.ts`: same-origin relative path, semver, hash, approved ID/capabilities, parser rejects imports, bounded verified bytes, namespaced registration and lifecycle. | Real hashed plugin/derived-state case plus a bundled authored-code lesson fixture. Host separately approves exact bytes; authoring/runtime references document the build and declaration contract. Plugins are trusted code, not hostile-code isolation. |
| 23 · Content Add-in OOXML | `P/pptx_core/interactive_ooxml.py` discover/attach/update/remove/resize/clone; official fixture semantic comparisons and corruption tests, multiple instances/slides. | Package-level implemented / exercised; host playback is A13. |
| 24 · both manifests | Central `R/config.json`, generated XML ContentApp and unified manifest, stable ID/origin/port; official XML validator pass recorded. | XML validity tested; unified host support and sideload playback not desktop-verified. |
| 25 · per-instance identity/settings | Injected deck/scene/instance/schema/hash; `R/src/office/settings.ts` reads Office settings after onReady and exposes saveAsync. Runtime checks bundle/spec hash agreement. | Structural/browser proof only; property initialization and actual save/reopen are A13. |
| 26 · app + preview | `R/src/app/main.tsx`, content/preview entrypoints, identity/hash/schema validation, lazy packs before derived activation, ready/error reporting. | Standalone and pack initialization exercised; Office boot A13. |
| 27 · loopback server/doctor | aiohttp static/API/nonce WebSocket/TLS, scoped safe paths, origin/CSP headers; doctor lists runtime/dependencies/cert/port/manifests/packs/scene checks. | Tests plus HTTPS health recorded. Doctor presence flags alone are not full manifest/certificate-trust validation. |
| 28 · certificate | `scripts/certificates.mjs`, install/status CLI and TLS server use office-addin-dev-certs, no TLS-disable workaround. | Parent recorded trusted macOS HTTPS without ignore-certificate-errors. |
| 29 · local/offline assets | Vite bundles libraries; pack-assets copies local Python/ONNX/map worker; Office.js alone uses Microsoft's official URL. | Production standalone packs operate from local assets; multi-file glTF relocation also passes the complete attach/bundle/served-browser proof. |
| 30 · native static fallback | Attach renders initial PNG; OOXML includes Content Add-in above native picture/fallback; opaque default background. | Native export/LibreOffice tests show fallback. Transparent overlap policy must stay explicit. |
| 31 · interactive rendering | `P/interactive_render.py` executes testPlan and writes initial/test/reset captures plus status; click/drag/input/keyboard/slider/seek supported. | Real multi-region showcase and strict A12 receipt validation passed. Scene, runtime/config, captures and declared assertions must still match; stale receipts require rerender. |
| 32 · assertions | Renderer checks state, visible/text/attribute/property, data count and timeline values; host rejects empty assertion sets. | Actual numerical/state/text assertions present. Local formal schemas may describe empty plans, but neither strict runtime verification nor the website host certifies empty assertion sets. |
| 33 · portable bundle | `interactive_bundle.py` includes PPTX/runtime/deck/manifests/scripts/readme/checksums/ZIP; own-process authenticated lifecycle. | Thirteen bundle integration tests; no-overwrite, corruption rejection, live preview and unrelated-process survival tested. The showcase adds six served regions. Stop destination is fixed; Windows launchers are not executed. |
| 34 · CLI extension | `interactive.py` adds all requested subcommands plus update/clone/resize; old native CLI remains. | CLI/hooks/native tests plus real attach/bundle; no manual multi-part editing required. |
| 35 · inspect/list integration | Native inspect adds discovered Content Add-in metadata without replacing ordinary fields. | Unit/package checks; discovery carries IDs, bounds, relationships, parts and hash. |
| 36 · workspace v2 | Explicit v1→v2 migration; separate native/sidecar baselines, snapshots include sidecars; final bundle records durable output. | Migration/rollback and actual bundle dirty-baseline tests passed. Journal relocation helper adds verified absolute-path remapping. |
| 37 · hooks | Pre/post detect sidecars and snapshot high-risk edits; Stop validates/renders/exports with bounded retries. | A4 Stop closure passes its real path; A12 strictly validates runtime and capture receipts. The website host still reruns independently. |
| 38 · validator | Schema, scene/bundle/asset hashes, safe paths/symlinks, OOXML relationships/content types/identity/bounds/plugin declaration checks. | Malicious input and deliberately broken graph tests; A12 now validates actual receipt/capture/runtime integrity. Neither local receipts nor standalone browser tests assert desktop playback. |
| 39 · export separation | Native export stays in package.py; interactive distribution orchestration stays in bundle helper. | Single-scene integration and four-slide/six-region showcase export→reopen→bundle pass; originals, native parts and sidecars are retained. |
| 40 · review packet | Native inventory and interactive validation/captures/tests already included, desktop false. | A7 behavior inventory is implemented and eight tests pass, retaining capture/receipt paths and desktop false. |
| 41 · skill workflow | SKILL, authoring reference, runner prompt and host broker choose native/interactive; freeze/retest before independent review/export. | Source integrated; installed production flow/release remains A9. |
| 42 · optional outline fields | Desired contract documented; current normalizer originally dropped mode/interaction fields. | A6 is fixed in runner and deployed website v23, with preserved legacy outlines and revision-sensitive interaction metadata. |
| 43 · performance | rAF timelines/compute, batched store, memoized nodes/selective subscriptions and debug rAF counter. | A10 counts expanded nodes/bindings and provides density guidance; actual production 504-node drag/slider/timeline frame intervals and input-to-DOM latency are recorded. No blanket 60fps claim. |
| 44 · bundle sizes | Dynamic chunks, `dist/bundle-sizes.json`, `dist/packs/manifest.json`, 300,000-byte core gzip failure guard. Final core 126,626 B; per-pack JS/CSS gzip and local/bundled raw asset sizes are emitted. | Build guard and checked-in CI wiring pass locally. Monaco merged chunks and math fonts are included in the pack report. Overall ZIP is much larger than core, by design. |
| 45 · security | DSL bounds, AST allowlist, no raw HTML/SVG injection, bounded assets/code, safe same-origin/allowlisted URLs, loopback/CSP/origin/nonce, host token separation. | Unit/browser/host negative checks. Approved deck JS and teaching code worker boundaries are explicit; no hard worker memory quota claim. |
| 46 · accessibility | Native labels/focus, SVG Enter/Space activation, selected strokes/text, reduced motion, keyboard Reset. | Real Chromium keyboard checks; PowerPoint slideshow focus/input is A13. |
| 47 · errors/diagnostics | RuntimeErrorBoundary and asynchronous runtime.fail show native-fallback message; local pack errors visible. | A11 adds structured scene/node/expression/asset/plugin/phase and stack where available; production-browser failure checks pass. Concise fallback remains. |
| 48 · capability detection | Office requirement, WebGPU/WASM/WebGL2/Worker/OffscreenCanvas/audio/video inspection; ONNX fallback, pack visible errors. | WASM fallback exercised; unsupported-target combinations and hardware WebGPU not all tested. |
| 49 · Python suite | Native units/integrations/roundtrips, official interactive fixture/mutations, sidecars/hooks/path corruption, bundle integration. | Existing runs recorded; final combined smoke after new fixes still required. |
| 50 · TypeScript suite | Engine, security, schema, transforms, registry, pack contracts and semantic regressions. | Final 54 tests pass across the three engine/semantic/pack files; TypeScript checking and production build also pass. |
| 51 · real browser E2E | 12 core semantics cases plus three diagnostics/performance cases and eight real feature-pack cases exercise state, geometry, keyboard/pointer, media, timeline/data/reset, repeated Monaco and local libraries. | Final combined suite: 23 passed. Production additionally runs eight pack tests and three diagnostics/performance tests through the real loopback server/CSP. Assertions test numerical/state/behavior outcomes. |
| 52 · technical showcase deck | Technical showcase script generates four native slides/six interactive regions, numerical test plans and preserved original sources. | A8 passes formal validation, attach/render, native LibreOffice export, reopen/rerender, bundle verification and all six served scene test plans (18 cases/34 assertions). |
| 53 · official golden fixture | Official PowerPoint Content template plus source SHA/license and semantic OOXML tests. | Implemented / exercised; no byte-identical requirement assumed. |
| 54 · desktop verification | Manual checklist is supplied; local PowerPoint exists but available GUI connection is unavailable. | A13 not desktop-verified. No Windows/Web pass inferred. |
| 55 · compatibility matrix | Root/plugin docs now distinguish native/browser/fallback/host target status. | Review matrix against actual evidence; desktop/Web remain unverified. |
| 56 · documentation | Root/plugin README, SKILL, three interactive authoring/runtime/review references and three architecture/compatibility/manual documents are present. | Root owns the release consistency pass; evidence documents explicitly distinguish package, standalone browser and actual PowerPoint proof. |
| 57 · usability | Thin attach/render/bundle helpers accept workspace and region bounds; direct native editing remains. | Main CLI and Stop closure A4 are exercised. Installed release and teaching-case gates A9 remain. |
| 58 · compact examples | `R/examples/controls.scene.json`, `charts-map.scene.json`, `primitives.scene.json` cover composition, state/data/media; pack cases use focused fixtures. | The technical showcase generator adds compact discoverable time/data, code/custom-plugin and external glTF scenes to those reusable core examples. Requested filenames are organizational, not separate runtime features. |
| 59 · authoring priority | SKILL/reference prefer existing components→primitives→safe functions→existing packs→explicit custom plugin. Host prompt forbids topic-specific React replacement. | Implemented in author workflow; verify teaching cases actually follow it. |
| 60 · prohibited regressions | No observed python-pptx replacement, scene eval, CDN heavy-pack runtime, global flattening or native-vs-desktop proof conflation. Native regression tests retained. | Continue normal regression gate; approved code worker execution is the explicit code-pack exception, not DSL eval. |
| 61 · dependencies | Small core parser/runtime, jsonschema/aiohttp server, lazy heavy libraries and pinned lockfile; dependency rationale in implementation docs. | Build/splitting/audit evidence exists; package assets are local. |
| 62 · acceptance A–O | A–M have substantial independent evidence; the showcase, hook/schema/outline/review fixes and runtime diagnostics are complete. Installed release/teaching cases and actual PowerPoint proof remain separate gates. | Cannot mark all acceptance criteria complete yet. No critical TODO stub found by scan; actual integration gaps above matter more than `pass` text in exception handlers. |
| 63 · execute actual checks | Python/Vitest/Playwright/build/size/native/LibreOffice/scene/bundle commands have recorded real runs. | Final combined gate passed after fixes; exact commands/results are in `docs/release-smoke-20260920.md`. Desktop omissions remain explicitly NOT RUN. |
| 64 · final report/commands | Architecture and execution checklist exist; final result must include exact setup/sideload/author/attach/preview/validate/bundle/presentation commands, sizes and limits. | Final report and both teaching artifacts remain future milestone output, not present evidence. |

## Additional user requirements

| Request | Source and evidence | Remaining gate |
| --- | --- | --- |
| Detailed checked plan and milestone GitHub commits | `docs/interactive-runtime-plan.md` maintains 18 bounded items with evidence and completed commit references. | Keep new fixes and showcase separate reviewable commits; parent owns pushes. |
| Resume from previous trajectory without deleting originals | `workflow/journal.py` verifies immutable checkpoints, locks recovery and forks restored attempt; actual SIGKILL/restart tests. `runner/runner.py` now calls recovery → verified workspace relocation → support refresh → checkpoint. | Final integrated workflow interruption/resume still belongs to smoke/release; helper tests alone are insufficient. |
| Native workspace validity after relocation | `runner/recovery_workspace.py` checks protected hash, remaps known paths only, retains JSON backups/snapshots and invalidates missing capture/render/export fields. Five tests pass on actual native workspaces. | Old snapshots deliberately retain old absolute metadata; after rollback, relocation or a fresh rerender may be necessary. |
| Live feedback/chat with ordinary messages and files | Owner-scoped portal conversation, app-server steering, attachment download/hash, durable message cursor and acknowledgement; actual transport steering/restart and portal browser tests are recorded. | Complete installed worker/deployed portal path and delivery after late corrections must pass final gate. |
| CNN then YOLO with editable runnable code and intuitive animation | Shared core/pack capabilities are present; brief generation and cases are separate milestones. | Not run at audit time. Do not imply fixture ONNX identity is a trained detector or that a short gallery proves lesson completeness. |
| Keep existing data | Source hashes, no-overwrite bundles/exports, recovery copies and snapshot preservation tested. | Continue using new task/version outputs and immutable prior deliveries. |

## Optional and future scope, not fabricated blockers

- Undo/redo was explicitly optional. `SceneStore` has history support through
  `batch(..., true)`, but normal action writes do not record it; advertised undo
  actions therefore have no ordinary author history yet. Do not market them as a
  completed user feature, but this is not a missing mandatory state requirement.
- Touch-specific gestures, compatible path morph, code stdin, alternate future
  schema migrations and hardware WebGPU optimizations are optional/preferred or
  future paths; assess their stated fallback rather than inventing requirements.
- Full GIS, every chart library option, arbitrary Python package installation,
  all YOLO output families, automatic visual-semantic changes to Canvas, and
  process-level isolation for hostile arbitrary code were not required as core.
- Monaco line highlighting materially helps synchronized teaching and the parent
  has approved it. It is an added teaching aid, not an originally mandatory code
  editor feature. Its state-bound Monaco decorations now pass a real production test, including inclusive ranges and actual edited source lines.

## Audit reproduction and proof discipline

The A1 probe bundled a tiny in-memory Runtime through esbuild with `write:false`;
it changed no scene files. It compared direct expression invocation and `call`
on exactly the same initialized store. After the fix:

```sh
cd pptx-agent/runtime
npx vitest run tests/browser/engine-regressions.test.ts
npx tsc --noEmit
npx playwright test tests/browser/semantics.spec.ts --grep 'repeated feature instances'
```

Observed: **14 regression tests passed, TypeScript passed, and the repeated-editor
Chromium test passed**. The final combined gate subsequently passed all **54
Vitest and 23 Chromium tests**, plus the production-specific checks recorded in
the diagnostic and pack reports. The first repeat-editor
test attempt falsely counted Monaco's own hidden ARIA alert containers as runtime
failures; the corrected assertion checks runtime error state and independent
execution after unmount instead.

No desktop PowerPoint experiment was possible in this audit. Its checklist is a
plan for actual host verification, not evidence that settings or playback passed.
