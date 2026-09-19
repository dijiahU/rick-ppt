# Feature pack verification — 2026-09-20

The implementation uses real libraries and local WASM, not display-only placeholders. The production smoke run uses the built `dist` and the Python `interactive_server` with its actual response Content Security Policy. Test scene/model bytes are in-memory fixtures; production-mode tests do not intercept or replace pack runtime assets.

Commands from `pptx-agent/runtime`:

```sh
npm run build
npx vitest run tests/feature-packs.test.ts
npx playwright test --config tests/feature-packs/production.config.ts
```

Observed result: TypeScript and production bundle build passed, 14 boundary/unit checks passed, and 8 production Chromium browser tests passed (6.4 seconds in the recorded run). The build manifest timestamp is 2026-09-19 21:06:08 UTC (2026-09-20 05:06:08 China time). A separate isolated copy with an empty Vite cache passed all 20 then-current development-server browser tests in 11.6 seconds, including simultaneous Pyodide and ONNX use. Test mode pre-optimizes the ONNX worker import and disables development hot reload; normal development retains hot reload. Production tests continue to use the actual built server/CSP.

| Pack | Verified behavior |
| --- | --- |
| core | Scene rendering with no optional JavaScript/WASM requests |
| code / JavaScript | Monaco mounting; input/stdout/return value; genuine keyboard source editing and rerun; state-bound whole-line/gutter highlights, ranges and invalid-line handling; run/reset; explicit stop; infinite-loop timeout; fetch denial and dynamic Internet import denial |
| code / Python | Real local Pyodide; stdin/stdout/return; blocked `js.fetch` |
| three | Real generated GLB loading, rendered triangle, pointer raycast selection, animated camera state, object-visibility binding |
| ml | Real ONNX Identity graph; named float input/output; exact output values; local single-threaded WASM inference |
| map | Actual MapLibre worker and renderer using local GeoJSON; rendered point and click selection |
| math / plugin | Real KaTeX state updates; same-origin SHA-verified plugin loading; plugin function available to initial derived state |

Boundary tests additionally cover: source/input/output/time limits, chunked fetch cancellation at the size bound, explicit plugin approval and capabilities, unsafe URL/traversal rejection, parser-based static/dynamic import denial, tensor shape and data-type ranges, separate YOLO preprocessing/class-aware NMS, untrusted KaTeX commands, bounded line/range normalization, and scene/plugin context on initialization errors. A learner's local `const input` declaration no longer collides with the injected input helper, because helper and learner lexical scopes are separate.

Production captures for the new walkthrough test live under `test-results/pack-production/2026-09-19T21-06-11-148Z-58569/`: initial line 1, active line 3 with actual returned output, and reset. The line-3 capture was visually inspected. Future test runs use unique output directories to retain previous evidence. These are engineering fixtures, not the pending CNN/YOLO acceptance presentations.

The latest build report lives at `dist/bundle-sizes.json`; optional local asset hashes and sizes live at `dist/packs/manifest.json` (11 static runtime/worker/WASM files, approximately 40.48 MiB). Large packs stay in dynamic chunks. The measured core gzip size is about 125 KiB, below the enforced 300,000-byte ceiling.

Not claimed by these results: PowerPoint desktop playback, hardware WebGPU performance, arbitrary external tile providers, Draco/KTX2 compressed model decoding, hostile-code process isolation, or a complete YOLO detector image pipeline. These need the separate host/case tests or additional adapters described in [feature-packs.md](feature-packs.md).
