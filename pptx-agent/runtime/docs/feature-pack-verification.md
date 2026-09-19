# Feature pack verification — 2026-09-20

The implementation uses real libraries and local WASM, not display-only placeholders. The production smoke run uses the built `dist` and the Python `interactive_server` with its actual response Content Security Policy. Test scene/model bytes are in-memory fixtures; production-mode tests do not intercept or replace pack runtime assets.

Commands from `pptx-agent/runtime`:

```sh
npm run build
npx vitest run tests/feature-packs.test.ts
npx playwright test --config tests/feature-packs/production.config.ts
```

Observed result: TypeScript and production bundle build passed, 12 boundary/unit checks passed, and 7 production Chromium browser tests passed (6.4 seconds in the recorded run). The same six functional feature tests also passed through the Vite development server; the extra seventh test confirms a core-only scene requests no optional pack chunk or WASM.

| Pack | Verified behavior |
| --- | --- |
| core | Scene rendering with no optional JavaScript/WASM requests |
| code / JavaScript | Monaco mounting; input/stdout/return value; source updates; run/reset; explicit stop; infinite-loop timeout; fetch denial and dynamic Internet import denial |
| code / Python | Real local Pyodide; stdin/stdout/return; blocked `js.fetch` |
| three | Real generated GLB loading, rendered triangle, pointer raycast selection, animated camera state, object-visibility binding |
| ml | Real ONNX Identity graph; named float input/output; exact output values; local single-threaded WASM inference |
| map | Actual MapLibre worker and renderer using local GeoJSON; rendered point and click selection |
| math / plugin | Real KaTeX state updates; same-origin SHA-verified plugin loading; plugin function available to initial derived state |

Boundary tests additionally cover: source/input/output/time limits, chunked fetch cancellation at the size bound, explicit plugin approval and capabilities, unsafe URL/traversal rejection, parser-based static/dynamic import denial, tensor shape and data-type ranges, separate YOLO preprocessing/class-aware NMS, and untrusted KaTeX commands.

The latest build report lives at `dist/bundle-sizes.json`; optional local asset hashes and sizes live at `dist/packs/manifest.json` (11 static runtime/worker/WASM files, approximately 40.48 MiB). Large packs stay in dynamic chunks. The measured core gzip size is about 125 KiB, below the enforced 300,000-byte ceiling.

Not claimed by these results: PowerPoint desktop playback, hardware WebGPU performance, arbitrary external tile providers, Draco/KTX2 compressed model decoding, hostile-code process isolation, or a complete YOLO detector image pipeline. These need the separate host/case tests or additional adapters described in [feature-packs.md](feature-packs.md).
