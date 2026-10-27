# Native slides with composable interactive regions

Keep native OOXML authoritative for the slide. A Content Add-in region references
a versioned JSON scene and a matching static PNG. The same scene engine serves all
topics. Do not generate a topic-specific React app or put executable expressions
inside scene JSON. Prefer editable native titles, definitions, equations and a
short explanation outside each interactive region.

First read the executable examples under `runtime/examples/` at the plugin root.
The shared schema is `skills/pptx/schemas/interactive-slide.schema.json`.
The runtime docs describe exact supported properties and limits:

- [Rendering, coordinates, state and time](../../../runtime/docs/runtime-semantics.md)
- [Code, Three, ONNX, MapLibre, math and plugins](../../../runtime/docs/feature-packs.md)

## Authoring sequence

1. Plan which question learner input will answer. Pick representative initial,
   changed, intermediate and reset states. An animation should reveal a mechanism,
   rather than merely move decoration.
2. Unpack the native source or bundled blank. Author native slide context and
   readable fallback text with direct OOXML. Retain the workspace path returned
   by the CLI; do not hand-edit `original.pptx`.
3. Write a scene using the shared schema and existing components. Local asset paths
   are relative to the scene. Provide `requires` only for packs actually used.
4. Validate, attach and run its test plan. Use bounds in EMUs when the scene occupies
   part of a slide (914400 EMUs = 1 inch). All four bounds must be supplied together.
5. Inspect actual native slide renders and runtime captures. Fix content/layout and
   rerun tests. `interactive update` refreshes every attached instance of that scene
   and its fallback. Direct edits to copied sidecars alone are not enough: their
   hashes must agree with the OOXML instance.
6. Export to a new PPTX filename and build the interactive bundle. Website authors
   provide `delivery.json` with both `path` and `workspace`; the host independently
   retests scenes, reviews all audience surfaces and creates the final ZIP.

From the plugin root (substitute the returned workspace and your task paths):

```sh
.venv/bin/python skills/pptx/scripts/pptx.py interactive doctor
.venv/bin/python skills/pptx/scripts/pptx.py unpack lesson.pptx
.venv/bin/python skills/pptx/scripts/pptx.py interactive validate-spec scene.json
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE interactive attach --slide 1 --scene scene.json --x 457200 --y 1371600 --width 11277600 --height 5029200
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE interactive render --scene scene-id
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE interactive update --scene scene.json
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE validate --level 3
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE export lesson-v2.pptx
.venv/bin/python skills/pptx/scripts/pptx.py -w WORKSPACE interactive bundle lesson-interactive --zip
```

In hosted authoring, `PPTX_INTERACTIVE_PROXY` automatically routes attach/render/update
through the trusted host. Do not start a browser/server in the restricted author
process. Read task-local `INTERACTIVE.md`. Delivery format:

```json
{"path":"/task/lesson-v2.pptx","workspace":"/task/.pptx-agent/lesson/workspace"}
```

## Scene composition

Every scene has `schemaVersion: 1`, a stable `id`, logical `viewport`, `initialState`
and `nodes`. Derived state and bound properties use `{ "expr": "state.value * 2" }`.
Expressions are a bounded AST interpreter with registered pure functions, not
JavaScript eval: no arbitrary calls, assignments, prototype access or code loading.
Data sources and components share the centralized state store.

Use SVG primitives, Group/layout/repeat/when, native HTML inputs, and first-party
components such as matrix, heatmap, charts, table, comparison, stepper and GeoJSON.
Do not assume a guessed component/property exists: inspect the schema/examples or
registry first. Events carry `event.value`; matrix/plot/map values include useful
row/column/feature metadata. Gestures operate in logical parent/node coordinates,
including nested transformations, instead of raw screen pixels.

Timelines use milliseconds and bind to state paths. Provide learner-controlled
play/pause/seek/reset when steps matter. Maintain visible definitions and legends
while moving a convolution window, changing a box or displaying a gradient.
The renderer includes keyboard labels and honors reduced motion. Reset should
restore understandable initial state, stop computation and pause media.

## Editable code and result-driven diagrams

Declare `"requires": ["code"]`, then use a node with `"type": "component"` and
`"component": "CodeEditor"`. Props include `language` (`javascript` or `python`),
`code`, `fontSize`, `stdin`, `timeoutMs`, `valuePath` and `resultPath`. Size the editor
for readable code and console output, rather than shrinking a complete program to
fit. Use short commented experiments on mechanism pages and a complete runnable
implementation across clearly connected code views.

For a guided walkthrough, bind `highlightLines` to the current teaching step's
1-based line number, or use an array such as `[2,[4,6]]`. Set
`revealHighlightedLine` to scroll the selected statement into view. Keep the
diagram, active statement and explanation synchronized through shared state.
These are authored highlights, not a Python debugger or a trace of actual line
execution. Recompute or invalidate the walkthrough's line map after source edits.

The code pack includes Run/Stop/Reset controls and emits `codeChange`, `codeResult`
and `codeReset`. A declarative action can run a specific editor:

```json
{"type":"plugin","name":"code.run","target":"editor"}
```

JavaScript executes in a bounded dedicated worker; Python uses local Pyodide.
Use pure Python/JavaScript unless a dependency is actually present in that runtime.
Shell Python packages are not automatically available inside Pyodide. Network calls,
external imports and uncontrolled long-running work are not a lesson dependency.
Bind result values to visual explanations and explain numerical expectations.
ONNX is a separate `ml` pack with local model bytes and explicit tensor adapters;
do not describe a toy/synthetic model as a trained CNN/YOLO detector.

## Test plans

Each attached scene requires at least one real test with nonempty assertions.
Use actions `click`, `hover`, `input`, `slider`, `select`, `toggle`, `keyboard`
(`key` alias), `drag`, `pan`, `wheel`, `seekTimeline`, `dispatch`, `resize`, `wait`,
`snapshot`, `restore` and `media`. Test state, text, visibility, attributes, properties,
data counts and timeline values. Use a numerical tolerance for floating point.

```json
{"name":"stride-changes-output","reset":true,
 "actions":[{"type":"slider","target":"stride","value":2}],
 "assertions":[{"type":"state","path":"stride","equals":2},
               {"type":"text","target":"output-size","contains":"2"}],
 "capture":true}
```

For code tests, dispatch `code.run` and assert the resulting stdout/value state;
merely finding the editor in the DOM does not prove execution. For animations,
seek a meaningful intermediate time and assert geometry/state; check reset. Test
at least one input that changes the explanation, not only the default picture.
Capture files and reports are versioned and hash-bound. The host discards author
success claims and reruns the tests on the exact frozen sidecar.

## Presentation and compatibility

The portable bundle includes the PPTX, scene/assets, production runtime, manifests,
file hashes and platform launch/stop helpers. Run its `start.command` on macOS or
`start.ps1` on Windows and use the printed preview URL. The process controller
stops only the instance it started. For PowerPoint Content Add-ins, use trusted
local HTTPS and sideload the XML content manifest. The same stable add-in ID and
deck/scene/hash settings select each region. The unified manifest is an additional
current format; actual host support must be checked, not assumed.

Browser test pass means the standalone runtime works. LibreOffice verifies native
static rendering. Actual PowerPoint edit/slideshow interactions and save/reopen
settings round-trip are separate checks. Do not label Windows, Office web or desktop
playback verified when only Chromium or PNG captures were tested.

Custom extensions are explicit trusted code: same-origin, self-contained modules,
approved ID/hash and declared capabilities. They are not an untrusted-code security
sandbox and cannot be approved by an arbitrary uploaded scene. Ordinary teaching
examples should use the first-party engine and packs.
