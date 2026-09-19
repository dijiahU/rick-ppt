# Interactive Runtime implementation plan

Source baseline: `702336fa6afe3bd1cdf71ee0b972b98bd52165ea`.
Native source files, references, hooks and read-only review workflow were read before edits.

1. Define a versioned, bounded JSON DSL and a shared schema. Implement an isolated
   store, safe expressions, events/actions, behaviors, data transforms, timeline,
   compute and SVG/HTML primitives. Test the semantics and malicious inputs.
2. Add thin OOXML helpers based on the official Microsoft content fixture. Preserve
   unrelated parts and originals. Add v1→v2 workspace migration, sidecar snapshots,
   validators, CLI, Playwright captures, TLS server and non-overwriting deck bundles.
3. Add lazy Three/Monaco/Pyodide/ONNX/MapLibre/KaTeX packs, registries, examples,
   integration tests and bundle-size guards. Review the CNN test deck independently,
   run its interactions, inspect static fallbacks, attempt actual desktop playback.
4. Commit and publish each tested version to GitHub; retain execution reports and
   private CNN artifacts locally. Do not modify the existing running website job.

Native OOXML remains authoritative for native slides. Scene JSON describes only
explicit interactive regions. Native export remains independently validated and
rendered. Browser tests, LibreOffice rendering and desktop playback have distinct
verification statuses. No native slide is flattened to implement interaction.

Dependencies: React/TypeScript/Vite for the web runtime; jsep for parsing (no eval),
Ajv for the shared schema, Vitest/Playwright for behavior tests. Python jsonschema
and aiohttp add bounded validation and loopback HTTPS/static/WebSocket serving.
Large dependencies are dynamic imports in opt-in feature packs only.

Official sources read and pinned before implementation:
- OfficeDev/Office-Addin-Scripts `02e062b75a2e8a79a4a720f73403f0e004e4988f`:
  `packages/office-addin-dev-settings/templates/PowerPointPresentationWithContent.pptx`
  and `src/sideload.ts`.
- OfficeDev/Office-Add-in-samples `43c823f8ed2bc5fc71f484dc6677155a8c1c9570`:
  `Samples/hello-world/powerpoint-content-hello-world` README, manifest and JS.

The XML path uses `ppt/slides/udata/data.xml`, a webextension relationship, an
AlternateContent graphicFrame, image fallback, and webextension snapshot image.
The official template reuses shape ID 2 outside AlternateContent; generated IDs
will instead be unique. The current unified sample uses manifest 1.27 and
`extensions[].contentRuntimes`, scope `presentation`.

Milestone 1 executed: 26 Vitest checks passed; TypeScript and production build
passed; core JS gzip 98,798 bytes. Scene validation is precompiled at build time,
so production schema validation does not require dynamic code generation/CSP eval.

Updated acceptance: after full smoke, author CNN and YOLO teaching cases using
JSON-first interactions, in-slide editable code, meaningful animations and fewer
pages where interaction explains more. Preserve the website's original task.
