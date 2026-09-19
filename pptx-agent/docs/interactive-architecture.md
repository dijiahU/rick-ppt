# Native and interactive presentation architecture

Native OOXML remains the source for the slide. A scene describes only a Content
Add-in region. Native titles, definitions, equations and context stay editable;
ordinary presentations continue through the native path without scene files.

## Authoring and Office package

The Python CLI retains a read-only original, a mutable OOXML workspace, snapshots,
render generations and independent native/sidecar hashes. Scene JSON has schema
version 1; workspace version 2 upgrades version 1 without discarding originals.
Snapshots and rollback cover both package and sidecar state and retain replaced
copies. Export validates original hashes, native relationships and scene identity,
runs actual LibreOffice rendering, and publishes a fresh output without overwrite.

The generated graph follows Microsoft's pinned Content Add-in fixture: a slide
relationship points to `ppt/slides/udata/` webextension XML; that extension points
to a snapshot image. `mc:Choice` contains the Content graphic frame and
`mc:Fallback` a native picture. IDs are unique per instance. A stable add-in ID
and deck/scene/schema/hash properties select the scene. Multiple regions may share
a scene while keeping separate instance identity. Both XML ContentApp and unified
presentation content manifests are generated from `runtime/config.json`.

## Shared browser engine

The React/TypeScript runtime interprets versioned JSON through an AST expression
interpreter, centralized state, declarative actions and a pure function registry.
There is no per-topic React generation and no JavaScript eval for scene expressions.
Bindings and data transforms feed SVG/HTML primitives and reusable components.
Logical coordinates include nested transforms; behavior controllers implement
drag, resize, scrub, pan/zoom, selection, brush and keyboard input. Timelines and
seeded compute update the same store. Reset, reduced motion, diagnostics and
bounded nesting/array/work limits are part of the runtime.

Heavy packs load only when declared: Three models, Monaco with bounded JS worker
or Pyodide execution, ONNX WebGPU/WASM with adapters, MapLibre and KaTeX. Local
asset bytes and hashes travel with the deck. Custom plugins require explicit
host approval of their ID and hash; they are trusted extensions, not an isolation
boundary for arbitrary uploaded code.

The loopback server serves built assets, deck data and a bounded WebSocket channel.
It enforces Host/Origin, rejects traversal and symlinks, and defaults to local HTTPS.
Only the code execution worker has the CSP exception needed by its engine; the
main runtime does not enable arbitrary expression eval. Remote assets require an
explicit allowlist. First-party lesson assets can run offline after installation.

## Rendering, verification and delivery

Playwright executes each scene's meaningful testPlan, asserts state/DOM/data/time,
and captures initial, intermediate, changed and reset states. Runtime receipts bind
the scene hash. Native renders plus those captures form the audience review packet.
Website authors call a task-local proxy; a host broker snapshots scoped inputs and
runs Chromium. The host freezes the exported deck and scene bytes, discards author
verification claims, reruns tests and creates the final bundle only from trusted
in-memory receipts. Mutation between validation and bundle publication is rejected.

Bundles contain a fresh PPTX, runtime, manifests, local assets, file hashes and
platform start/stop helpers. The process controller authenticates its own instance;
it does not kill unrelated processes. Browser, native static and Office desktop
verification are separate facts in all receipts.

## Website and durable execution

The website accepts owner-authenticated, CSRF-protected messages and bounded
attachments. Stable IDs deduplicate retries. A leased worker records each message
in a host-owned durable journal before sending it through Codex app-server. Active
turns receive steering; idle/resumed threads receive a new turn. Lost delivery
acknowledgements are reconciled using provider history before retrying.

Chat becomes applied after a successful response; a revision becomes applied only
after host artifact verification. New input invalidates stale reviews. An atomic
completion SQL condition rejects new/unapplied messages in the final upload window.
Versioned downloads keep earlier successful artifacts available.

Checkpoints contain file hashes, task/run/thread/turn, plugin version, phase,
revision, message cursor and completed-stage receipts. Recovery holds a per-task
lock, verifies bytes, restores a new attempt and retains the old attempt. Known
workspace paths are relocated; delivery receipts are resolved in memory against
host recovery history, preserving reusable hashes. Existing commands are never
blindly replayed. A compatible thread is resumed with only the new task grants;
otherwise the workflow rebuilds context from verified artifacts and pending input.
