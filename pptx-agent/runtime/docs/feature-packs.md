# Optional interactive feature packs

Declare only the required pack names in a scene, for example `"requires": ["core", "code", "math"]`. `loadFeaturePacks(runtime)` resolves those dynamic chunks before initial derived state and data sources run. The core has no static Three, Monaco, Pyodide, ONNX, MapLibre or KaTeX imports. `scripts/pack-assets.mjs` copies the pinned local Python and ONNX WASM resources and writes their sizes and SHA-256 hashes to `dist/packs/manifest.json`. These files ship inside the portable bundle; the runtime does not use a public CDN for them.

Each component uses the normal `{ "type": "component", "component": "CodeEditor", "props": { ... }, "bind": { ... } }` node, with width/height and normal runtime state bindings. Feature events enter the same event/action system. Feature actions use `{"type":"plugin","name":"code.run","target":"editor"}`; an optional `result` stores the returned value into a state path. `args` accepts normal expressions.

## Code pack

`CodeEditor` is a real Monaco editor with `language` (`javascript` or `python`), initial `code` or controlled `value`, optional `valuePath`, `resultPath`, `stdin` (array of lines), `timeoutMs` (100–30,000, default 5,000), and `outputLimit` (up to 256 KiB). It exposes Run, Stop and Reset. Actions are `code.run`, `code.stop`, `code.reset`, `code.getCode`, `code.setCode` (`args.code`). Events are `codeChange`, `codeResult`, and `codeReset`.

For guided walkthroughs, `highlightLines` accepts a 1-based line number or an array of numbers and inclusive `[start,end]` pairs, e.g. `[2,[4,6]]`. Bind it with `"highlightLines":{"expr":"state.lesson.codeLine"}`. Monaco displays actual whole-line and gutter decorations; duplicate/adjacent ranges merge, invalid/out-of-range entries are ignored, and at most 128 references are processed. `revealHighlightedLine: true` scrolls the first highlighted line into view when the binding changes. Source edits revalidate line bounds. These are authored teaching highlights, not runtime breakpoints or a Python debugger; invalidate a source map when learner edits make it stale.

Monaco content notifications from one edit are coalesced before publishing the final `valuePath`/`codeChange` value. Highlight decorations refresh after those notifications, and identical ranges and model versions do not cause another decoration update. This keeps large multiline edits and automatic indentation outside reentrant editor events and preserves the runtime's action limit. A following `code.setCode` → `code.run` action sequence observes the edited program; Reset restores the original source and its mapped highlights. Use an actual clipboard paste for complete Python programs: synthetic composition-style multiline typing can invoke Monaco's automatic indentation and change whitespace.

Each run gets a new dedicated worker. JavaScript supports `input()`, `print()`, `console.log/error`, top-level `await` and `return`. Python uses local Pyodide and standard-library imports, `input()` and normal stdout/stderr. Reset restores original source and clears output; it does not reuse interpreter globals. Python's separate cold-start limit is 60 seconds, after which the execution timeout begins. Installing extra Python packages at runtime is intentionally unavailable: package dependencies must be made local and explicitly supported before execution.

The worker response has its own restrictive CSP. Only this isolated code worker permits `unsafe-eval`; the slide and expression evaluator do not. Browser networking APIs, nested workers and importscripts are disabled before user code runs; CSP permits only local bootstrap resources and blocks arbitrary Internet imports. Source, input and output sizes are bounded and termination enforces a wall-clock limit. Browsers do not offer a portable hard memory quota for workers, so very large allocations can still exhaust a tab. This is a teaching-code execution boundary, not a replacement for a process-level hostile-code service.

## Three pack

`ThreeScene` accepts a model asset `src` containing GLB or glTF, or an `objects` array of named procedural `box`, `sphere`, or `cylinder` meshes. Model dependencies must be local or explicitly HTTPS-origin-allowlisted. Draco/KTX2 decoders are not bundled; compressed models must be predecoded. Controls support orbit, zoom, raycast selection and emissive highlighting. Bind `rotation` (three radians), `visibility` (object-name to boolean), `selected`, `explode`, or `camera: {position:[x,y,z],target:[x,y,z]}` to normal runtime state. Explode scales each object's original local position; models whose child positions are all zero need author-supplied grouped transforms. `selectionPath` receives a selected object name. `threeSelect` and `threeReady` events expose results.

`three.camera` accepts a target position/target and bounded `duration`, while `three.select` accepts `name`. `three.inspect` returns current camera/object state for test assertions. WebGL absence produces a visible capability error; the PowerPoint native snapshot remains the fallback. All geometry/materials/textures, event listeners, controls and animation frames are disposed on unmount.

## ML pack

`ModelRunner` accepts local `model`/`src`, `inputs`, `adapter` (default `tensors`), `adapterOptions`, `resultPath`, `timeoutMs`, and `preferWebGPU`. It runs ONNX in a separate worker and prefers WebGPU when available, falling back to single-threaded WASM. No SharedArrayBuffer or cross-origin isolation is required. All WASM comes from the installed local pack. The UI reports the configured execution path (`webgpu+wasm` permits per-operator fallback; `wasm` uses the CPU runtime). Loading has a 60-second bound; inference has a 100–60,000 ms bound. Stop terminates the worker; Run reloads the model if needed.

The generic tensor format is `{ "inputName": { "type": "float32", "dims": [1,2], "data": [3,4] } }`. Supported input types are float32, float64, int32, int64 (decimal strings), uint8 and bool. Inputs total at most 64 MiB, a model at most 256 MiB, and returned outputs at most 16 million elements. Outputs preserve names, data types and dimensions. Actions are `ml.load`, `ml.run` (optional `args.inputs`) and `ml.stop`; events are `modelReady` and `modelResult`.

Application integrations can `registerModelAdapter(runtime, name, {preprocess, postprocess})` before mounting. The included `yolo` example is a separate adapter, not core logic: it normalizes already-resized RGBA pixels into NCHW float32, decodes YOLOv8/YOLO11 raw `[1, 4+classes, candidates]` outputs, and applies class-aware NMS. Image letterboxing, coordinate unmapping and other YOLO output families require their own adapter; a supplied model must match the declared format.

## Map and math packs

`AdvancedMap` renders local inline `geojson` or a JSON asset `src` with MapLibre, without requiring a tile service. It accepts `center`, `zoom`, `pitch` and a full optional MapLibre `style`. Every style/source/tile/sprite/font request goes through an origin check, and external HTTPS origins must appear in `runtimeOptions.networkAllowlist`. The document CSP repeats that restriction. `selectionPath` and `viewPath` save click and view information; events are `mapReady`, `mapSelect`, `mapMove`. `map.flyTo` accepts center/zoom/pitch/bearing/duration. Third-party map styles may require attribution and credentials; supply these explicitly and retain MapLibre attribution.

`Math` (alias `Formula`) accepts `tex`/`value`, `displayMode`, fontSize/color and ariaLabel. KaTeX uses MathML accessibility output, no trusted HTML/URLs, bounded expansion and formula size. This pack affects only interactive content; native PPTX formulas retain the existing Office Math requirements.

## Explicit custom plugins

A scene plugin manifest requires `id`, semantic `version`, a relative same-origin `path`, SHA-256, and an explicit `capabilities` array drawn from `functions`, `actions`, `components`, `dataSources`. Its ID must also appear in `runtimeOptions.allowedPlugins`. The runtime fetches and validates the exact bytes (maximum 2 MiB), rejects all static/dynamic imports and `import.meta` using an ES module lexer, then loads those verified bytes. Build the plugin as one self-contained ES module with default export:

```js
export default {
  id: 'teaching', version: '1.0.0',
  functions: { twice: x => x * 2 },
  actions: { update: (args, event, api) => api.setState(args.path, args.value) },
  components: { Badge: props => [{id:'text', type:'Text', props}] },
  dataSources: { rows: async source => source.value },
  init(api) {}, dispose() {}
};
```

Functions are namespaced as `teaching_twice` for the bounded expression language; actions/components/data adapters use `teaching.update` / `teaching.Badge` / `teaching.rows`. A custom source is `{"type":"plugin","adapter":"teaching.rows",...}`. API state writes and event emission require the `actions` capability. Registration rejects undeclared capabilities and duplicate names. Approved plugins execute in the slide realm and must be reviewed as executable code: capability declarations constrain the supported registration API, not arbitrary malicious JavaScript. They must never be auto-approved from a fetched brief or uploaded document.

Official reference APIs: [Pyodide JS API](https://pyodide.org/en/stable/usage/api/js-api.html), [ONNX runtime flags](https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html), [MapLibre API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/), [Three GLTFLoader](https://threejs.org/docs/#examples/en/loaders/GLTFLoader), [Monaco editor](https://microsoft.github.io/monaco-editor/docs.html), [KaTeX options](https://katex.org/docs/options.html).

## Multiline editing regression — 2026-09-20

The real 2,781-character commented convolution program is retained in
`tests/feature-packs/fixtures/highlighted-convolution.py` (SHA-256
`fcd27b4538cb20db86a8d5aa0306f1594b32fa84c27c473ca0bd4493ed69d539`).
With line 28 highlighted, composition-style multiline `insertText` invokes
automatic indentation. The previous production build failed on this fixture:
decoration changes reentered Monaco's content event delivery; its content-change
burst also exhausted the unchanged 2,000-action transaction limit.

The regression now verifies one final `codeChange` for that edit, zero page
errors, an exact real clipboard paste followed by Python execution, an ordinary
single-character coefficient edit, contained syntax errors, a combined
`code.setCode` → `code.run` action sequence, and Reset restoring source, result
and highlights. The production test checks the actual server CSP: `unsafe-eval`
remains confined to the isolated teaching-code worker.

The single production build completed at **2026-09-19 23:01:52 UTC**, with runtime
fingerprint `be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
TypeScript/build, all **79 unit tests**, **24 main browser tests**, **9 production
pack tests**, and **3 production diagnostic/performance tests** passed. An
independent replay against immutable draft scenes passed 197 learner UI/numeric
assertions and recorded 24 captures, including JavaScript and Python editing,
error/Stop/Reset, zero-epoch CNN training, and a compact reduced-motion viewport.
The exact formerly failing auto-indented buffer was reproduced with zero page
errors; real paste preserved the source byte for byte. These draft checks are
runtime regression evidence, not final CNN content/visual acceptance or native
PowerPoint playback.
