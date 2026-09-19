# Multi-region native technical showcase

The synthetic §52 showcase passes the complete author/attach/render/native
export/reopen/bundle/served-preview chain. It contains **four native slides, six
interactive regions, 18 test cases and 34 assertions**. The same test plans run
on initial attachment, after reopening/rerendering the exported PPTX, and from
the portable bundle. This is engineering acceptance, not either teaching lesson.

## Run it

Build the runtime first, then keep that build unchanged throughout the run.
From the repository root:

```sh
pptx-agent/.venv/bin/python pptx-agent/runtime/scripts/technical-showcase.py \
  --out /absolute/new/private-directory/technical-showcase
```

The destination must be new. The script preserves the bundled blank template,
generated source assets, prior outputs, and all native/sidecar bytes during bundle
assembly. It reuses the compact core gallery scenes rather than introducing a
topic-specific rendering application. Titles and explanatory context remain
native editable PowerPoint text.

| Slide/region | Actual test outcomes | Cases / assertions |
| --- | --- | ---: |
| 1 · controls/state | Increment and keyboard activation; slider gain 6; text input stored; transformed/snapped drag reaches (55,20); reset restores (25,20), count and gain | 6 / 12 |
| 2 · charts/geography | Chart selection, GeoJSON east selection and reset pan/zoom state | 3 / 4 |
| 2 · data/time | Local CSV sum 60; timeline at 250 ms has x=45; compute produces positive ticks/distance; reset preserves derived total | 3 / 7 |
| 3 · primitives/media | Shared vector/component gallery; actual local WebM playback then pause, video width 256 | 2 / 4 |
| 4 · code/custom plugin | Authored Button plugin actions set/run real Monaco JS; results 7 and 12 feed a hashed custom function to produce 14 and 24 | 2 / 5 |
| 4 · external glTF | Real triangle glTF and separate binary load; raycast selects the named triangle | 2 / 2 |

Each generated scene passes the public `pptx.py interactive validate-spec` CLI
before attachment. The code fixture uses named object `args` in authored
`plugin` actions, so it exercises the conditional formal schema and event-action
path rather than relying on debug-only direct dispatch.

## Preserved evidence

Final private output:

`/Users/rick/Desktop/ppt/.work/interactive-runtime-20260920/proof/technical-showcase-20260920-0518`

Its `acceptance-evidence.json` records:

- Native package validation and actual LibreOffice PDF/four PNG rendering.
- Six instances discovered after reopening the exported PPTX. Every scene is
  rendered again in the new workspace, so strict receipt paths/hashes remain
  valid instead of reusing stale receipt paths from the old location.
- `nativePartsPreservedByBundle`, `sidecarsPreservedByBundle` and
  `sourceAssetsUnchanged` all true.
- Portable folder and ZIP; the ZIP is **22,606,239 bytes**. Bundle verification
  covers 132 files and the PPTX SHA-256 is
  `fa6e5fb34ecf42a52ede7b03cc43b10ed526fafb13889efda9b6eb47875f76f1`.
- Real start of the copied local server, all six served scene test plans and
  screenshots, a successful external `.bin` request, and authenticated stop of
  that bundle's own process.
- `runtime_verified: true` and **`powerpoint_playback_verified: false`**.

Every strict scene receipt binds the final frozen runtime:

```json
{
  "sha256": "1f4b66baaf34bfd80dbf77dc29969cf43c8bfe1cb599d0b1644f6659e0575ae3",
  "files": 96,
  "configuration": "7653f243bdd5d4dc6f1b4ba6f4f3d2f7ebbddf009a759299ad15d1a6a779716a"
}
```

The final native pages are in
`authoring/blank/renders/render-snbw6ofc/slide-1.png` through `slide-4.png`, with
`deck.pdf` alongside. Served interaction screenshots are in `served-preview/`.
All four final native PNGs were opened for visual inspection. Independent review
of the preceding complete render identified a wrapped/cropped “Stop compute”
label; the fixture now uses “Stop”. The fresh native slide 2 was inspected again
and the clipping is gone. No material overlap or clipped text was seen on the
other final pages.

The copied-runtime preview uses the production CSP. The browser harness waits
for the runtime's readiness attribute; it does not require adding `unsafe-eval`
to the scene policy. The retained earlier unsuccessful harness attempt was an
unsafe-eval-based polling mistake, fixed in the harness without weakening CSP.

Actual PowerPoint add-in startup, slideshow keyboard/focus and save/reopen
settings persistence remain unverified because the desktop automation connection
was unavailable. Native LibreOffice rendering, XML/package verification and
standalone browser success do not substitute for those host observations.
