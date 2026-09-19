# Runtime diagnostics and measured interaction performance

Final local runtime gate, 2026-09-20 (Asia/Shanghai): **54 Vitest tests, TypeScript
checking, production build/size gate, 23 combined browser cases, three production
diagnostic/performance cases and eight production feature-pack cases passed**.
These are browser/runtime results; they do not establish PowerPoint slideshow
performance or host settings persistence.

## Reproduction

Run from `pptx-agent/runtime` with the repository Python environment and Chromium
installed:

```sh
npm test -- --reporter=dot
npx tsc --noEmit
npm run build
npm run test:e2e
npx playwright test --config tests/browser/production.config.ts
npx playwright test --config tests/feature-packs/production.config.ts
```

The production configurations use the actual Python loopback server, the built
runtime and its CSP. The normal test server disables HMR only in Vite test mode
and explicitly preoptimizes the ONNX worker dependency, preventing a cold-cache
optimizer reload from destroying an in-progress Python worker test. Ordinary
development HMR is unchanged.

Final manifest write: **2026-09-19 21:11:48.414 UTC**. The strict runtime
fingerprint used by scene receipts is:

```json
{
  "sha256": "1f4b66baaf34bfd80dbf77dc29969cf43c8bfe1cb599d0b1644f6659e0575ae3",
  "files": 96,
  "configuration": "7653f243bdd5d4dc6f1b4ba6f4f3d2f7ebbddf009a759299ad15d1a6a779716a"
}
```

## Diagnostic behavior

The debug overlay counts **expanded visible DSL instances**, including repeated
and custom-component nodes, rather than counting only authored roots. It counts
their explicit bindings, expression-valued properties and visibility conditions;
it does not claim to count internal DOM elements or a pack's private GPU objects.
A real browser case renders 122 expanded nodes/80 bindings, then changes the
repeat source and verifies 61/40. Selective subscriptions still preserve unrelated
DOM during drag.

The overlay displays active timelines, measured rAF cadence, viewport dimensions,
core JS gzip and each pack's JS gzip/copied local asset size. Full CSS/font and
asset accounting is available in `dist/bundle-sizes.json`. The declared
`canvasThreshold` now issues a density advisory (default 1,000 nodes); it does not
silently change rendering or lose SVG keyboard/selection semantics. Explicit
Canvas remains an author choice requiring visual and accessibility review.

Errors retain a structured message/stack and available `sceneId`, `nodeId`,
`expression`, `asset`, `plugin` and `phase` through the core, renderer, boot,
feature-pack and plugin loader boundaries. Missing context is left absent.
Debug-mode production tests assert scene/node/expression context for an invalid
binding and scene/asset context for a missing image. Normal mode keeps the short
fallback message, while static native content remains available. Component-local
capability failures may remain local pack messages instead of replacing the
entire scene.

## Size gate

Core JS gzip is **126,626 bytes**, below the enforced **300,000-byte** ceiling.
The GitHub workflow runs this guard on every configured push/PR. Monaco's merged
anonymous build chunk is traced through its language entries, so it cannot be
reported as a zero-byte pack. A missing pack chunk fails the size report.

| Pack | JS gzip bytes | CSS gzip bytes | Bundled fonts/assets, raw bytes | Copied local assets, raw bytes |
| --- | ---: | ---: | ---: | ---: |
| code | 688,654 | 12,534 | 0 | 13,553,440 |
| three | 164,659 | 0 | 0 | 0 |
| ml | 3,835 | 0 | 0 | 28,358,879 |
| map | 276,230 | 10,573 | 0 | 532,905 |
| math | 77,932 | 8,096 | 1,072,948 | 0 |

JS accounting excludes the shared core, includes each pack's static dependency
closure and the code pack's lazy language entries. A small shared helper can
appear in more than one pack row, so rows should not be summed as an exact unique
download size. Raw asset bytes include bundled local engines/workers/model
support; the small ML JS wrapper is not the full ONNX engine size. The portable
ZIP contains all required local files and is much larger than the core.

## Representative 500-mark measurement

`tests/browser/diagnostics-performance.spec.ts` drives 500 repeated SVG marks
(**504 expanded scene nodes and 1,502 bindings**) using real pointer motion and
keyboard slider input. It asserts drag displacement 90, gain 70, opacity 0.79,
and a timeline endpoint of 100. A `MutationObserver` records capture-phase input
to the resulting SVG attribute mutation; rAF intervals are recorded separately.
Timeline samples are collected only while the timeline is playing, excluding
the final assertion's idle polling.

The final production sample at **2026-09-19 21:14:20 UTC** ran in headless Chromium
153.0.8010.12, viewport 1000×700, on macOS arm64. Browser-reported logical CPU
concurrency was 10. Playwright's Desktop Chrome profile supplies a Windows user
agent string; that string does not mean the test ran on Windows.

| Interaction | rAF samples | Median interval | p95 interval | Max interval | Intervals over 33.34 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Drag | 68 | 16.7 ms | 16.7 ms | 16.8 ms | 0 |
| Slider | 46 | 16.7 ms | 16.7 ms | 16.7 ms | 0 |
| Timeline, while playing | 61 | 16.7 ms | 16.8 ms | 16.8 ms | 0 |

| Input to observed DOM change | Samples | Median | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| Pointer drag | 30 | 3.9 ms | 4.5 ms | 6.0 ms |
| Keyboard slider | 20 | 7.4 ms | 8.8 ms | 10.2 ms |

Raw samples and the inspected final screenshot are retained under
`test-results/diagnostics-production/2026-09-19T21-14-14-233Z-68611/`.
This short, hardware-specific workload demonstrates responsive behavior for the
tested scene. It is not a universal 60fps guarantee, a GPU/presentation latency
measurement, a long-duration simulation soak, or a PowerPoint host benchmark.

## CI timeline regression

The first CI trace showed `Invalid timeline delta` after Play/Pause/Play. A newly
scheduled rAF timestamp can be slightly earlier than `performance.now()` captured
inside the same frame. The timeline and compute loops now clamp that initial
delta to zero and keep their previous timestamp monotonic. A deterministic
regression covers initial start and resume with this ordering, followed by real
positive progress. The real browser test still requires the original final
timeline value; its assertion was not weakened.
