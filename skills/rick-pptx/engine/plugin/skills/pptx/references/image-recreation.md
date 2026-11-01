# Faithful image recreation tools

Use for a supplied diagram/image, not as a template for new deck design. Keep
one author and the existing content, native-editability, rendering and review
flow. The source defines the visual relationships; a tool does not interpret it.

## Inspect once, reuse exact regions

Open the actual source with the host's image tool. Keep its original bytes and
identify the right version/dimensions before taking coordinates. Select useful
regions in source pixels, for example:

```json
{"regions":[{"id":"trajectory","box":[1120,85,1370,225]},
            {"id":"matrix","box":[735,978,845,1078]}]}
```

Boxes are `[left,top,right,bottom]`, right/bottom exclusive, after EXIF orientation.
Use the prepared interpreter and tool path, not a new crop script for every region:

```sh
HOST_PYTHON SCRIPTS/recreation_tools.py inspect --task-root TASK --source reference.png --regions regions.json --grid 200 --out source-inspection
HOST_PYTHON SCRIPTS/recreation_tools.py compare --task-root TASK --source reference.png --render rendered.png --regions source-inspection/receipt.json --out comparison-v1
```

Regions and grid are optional. Outputs are PNGs and a receipt with exact source
SHA, dimensions and region boxes. Reusing the receipt on different source bytes
is rejected. Compare makes source-left/render-right pairs, 50% overlays, a full
difference image, and selected-region pairs. It uniformly rescales the actual
render to the source pixel frame. Different aspect ratios require an explicit
`--render-box left top right bottom` for the render's content region; do not
silently stretch or crop away missing content. Every output directory is fresh.
The tool uses task-local PNG/JPEG/WebP only and preserves source files.

Open the useful output images through the supported visual channel; neither a
receipt nor a filename means anyone has viewed them. Difference images include
font antialiasing/rendering variation and are not fidelity or aesthetic scores.
Use the existing frozen candidate/render packet for independent reviews. A crop
receipt binds image bytes, not a PPTX revision or a final delivery approval.

## Implement geometry without rebuilding the plumbing

Use existing `native_batch` with optional `source_frame` to express object
positions in original image pixels, while retaining font/line sizes in points.
Batch defaults reuse selected colors/fonts. A page can use several bounded
batches; don't require one enormous code response. Inspect committed receipts
before retrying so interrupted work isn't duplicated.

Use native `path` for Bezier curves, feedback loops, trapezoids and explicit
hatching strokes. M/L/Q/C/Z commands stay editable in PPTX. Use native bound
connectors for topology that should follow moved nodes; fixed paths do not gain
endpoint binding. Group related objects with existing helpers where useful.
True photographs may be cropped and embedded; analytical text, lines, symbols
and cells stay native. Never replace the diagram with a whole-page image.

## Preserve what the shapes mean

Repeated tokens/cells are evidence: keep order, count, empty/filled state,
crosses, slash direction, colors and matrix positions. Trace branch destinations,
feedback loops and arrow direction against the relevant source crop, rather than
guessing from the diagram's topic. A screenshot's geometry is not a scientific
correction opportunity. Reviewers should compare the exact region before making
a required replacement, and keep genuine source ambiguity as a suggestion.

Use the existing Times New Roman / SimSun policy unless explicit source-font
requirements or verified exceptions apply. Don't spend repeated calls hunting a
decorative font or make an uncertain font match a required replacement. Measure
actual faces and inspect reading-scale renders. Preserve syntax color roles and
proper native sub/superscript runs or equations; literal underscores and missing
glyph fallback do not preserve mathematical notation. Existing low-level OOXML
editing remains available when a helper cannot express a detail.

Fix the largest source mismatch visible in the actual render, then re-render
the changed candidate. Reuse earlier regions, source files and provenance. No
extra model, mandatory crop count, review stage or auto-pass is introduced.
