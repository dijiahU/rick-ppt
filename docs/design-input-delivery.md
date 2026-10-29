# Current-page design inputs

The continuing author can call `pptx_page_design_context(page_id=...)` through
the existing app-server host-tool channel. This wraps the pinned plugin's
read-only `page_design.py context`; it does not choose a layout, acquire media,
change the content schema or start another model. Native drawing, templates,
source permissions, animation and independent review paths remain unchanged.

The context adds only explicitly applicable reference records, using the existing
`references[].applications[].pages` and stable outline ID. Identity, source,
declared inspection, observed/borrowed relationship and the current page action
stay together. Full phase documents remain available; the previous absence of
this projection did not prove that the author received no reference information.

Supported task-local images from that page's handoff materials, ready planned
assets and local-image reference evidence are returned as real `inputImage`
content. Files are read through the existing scoped reader, checked against their
context hash and verified as PNG/JPEG/WebP. The original registered bytes/pixels
are identified; thumbnails are not promoted to full-source inspection. No remote
fetch, file selection or asset-state mutation occurs. `material_prefetch.ready`
keeps its completion meaning, including evidence-only search results.

The existing trajectory records `design.visual_input_sent` only after the
transport successfully writes an image-bearing tool response. The event binds
thread/turn/call, page ID, file/hash/pixels and content index. It proves transport
delivery, not provider acceptance, model understanding, asset selection or visual
review. Same-thread repeats can reuse that real receipt; `repeat_images=true`
resupplies images when needed. A new thread receives fresh image content.

The CLI still returns text. The current DSH adapter cannot register these host
tools, so it retains the existing CLI plus native image viewer path. Authors are
directed to view current main assets/applicable visual references before committing
image-dependent composition. Missing/unsupported/oversized files stay unattached;
existing permitted image tools/fallbacks remain available. There is no mandatory
image/reference quota, whole-deck material wait or new delivery gate.

Offline tests exercise actual image-bearing stdio responses, byte/hash identity,
write-failure receipts, page filtering, unavailable evidence, scoped paths,
same-thread reuse, author-only registration, API image-history conversion and the
existing native group/connector/reveal/editable-chart cases. They establish the
delivery chain, not a measured improvement in first-generation design. Historical
cases with genuine image-view events still exhibited weak scale, crop or visual
explanation; image delivery alone is not their complete diagnosis. Outline-summary
ordering is unchanged without reliable evidence of systematic verbatim copying.

## Page-local rendered iteration

The same host tool accepts the existing task-local `workspace`. After `render N`,
it supplies this page's current preview ahead of supporting material, using the
existing immutable render and native-package fingerprint. It does not render,
pick a layout or edit files. Stale/missing/changed previews remain unattached.
The native context remains read-only and additive; CLI/DSH callers open the exact
preview with their existing image viewer. Changed-page previews are supplied
again even if their image bytes match a prior image; unrelated material still
reuses same-thread delivery receipts.

After a successful image-bearing write, `design.page_preview_sent` binds page ID,
workspace, native page/package hashes, render/source hashes and thread/turn/call
to any preceding preview actually supplied by this tool. These are input-delivery
facts, not model understanding or an improvement verdict. Earlier renders stay
immutable. A resumed phase may have no in-memory previous input; retained task
files and trajectory receipts remain the evidence, without an invented receipt.

Current native page context now carries the existing inspection's real object
IDs/text/transforms with its page hash; an oversized index explicitly defers to
the existing inspect command while preserving preview delivery. Tool preparation
diagnoses an invalid existing decision record with the current validator without
rewriting it or adding a gate. The same callable contract exposes glyph preflight,
numeric text-height requirements and a measured text example.

`compare_previous=true` requests the last supplied same-page/workspace/thread
preview beside the current image. It verifies saved bytes and labels the earlier
image historical; no previous receipt or intact file means no invented comparison.
Existing applicable references can be deliberately resupplied when comparing a
specific relationship. Otherwise authors use attached pixels without reopening
the same files by default.

The first current-page preview also reuses that page's registered local-image
references in the same image-bearing response, even when those exact files were
sent before composition. This puts the implementation and its applicable visual
evidence together at the existing rendered-design decision. Current preview
bytes keep transport priority; no acquisition, reference selection or new model
turn occurs. Existing file/call/image-index receipts prove this input arrangement,
not that a comparison, understanding or improvement occurred.
After a successful current-preview write, later calls keep ordinary same-thread
deduplication unless the author explicitly requests `repeat_images`. Missing,
stale or unsupported current previews do not trigger this resupply. A failed
write does not consume it. All existing file/scope/size checks still apply.

For edits with one checksum-bound original PPTX and equal page counts, the host
reuses native dependency fingerprints and the existing renderer to prepare changed
source-page previews. They enter the source/visual review's existing first-turn
image path and sealed input inventory, never the blind audience workspace. Page
positions are comparison candidates, not proof of semantic correspondence. Missing,
ambiguous, mismatched-count or failed previews keep an explicit unavailable state;
original attachments remain the existing fallback. New decks add no source render.

The continuing-author instructions now explicitly use a page-local
build-render-view-revise loop: test the main composition early, choose a concrete
correction from the image, then render/view the affected page after a meaningful
edit. Existing snapshots support reversal before substantial recomposition. A
finished first result can stand; correctness/readability/export alone do not
resolve the intended visual task or composition/craft. No fixed iteration count, additional model, score
loop, page approval, requirement to record every page or change to independent
review/delivery gates is added. Existing task budgets and unavailable-view limits
remain in force. Offline transport/renderer tests establish this chain; they do
not establish aesthetic improvement or Windows WPS playback.

The older common author prompt also prohibited a "second author review loop",
while the supplied design method requested same-author rendered refinement.
Both clauses were present in the recorded first-author input. The broad phrase
now prohibits a separate reviewer/approval stage instead, explicitly retaining
render/view/refine work inside authoring. This changes no call sequence, budget,
review independence or repair gate. Its behavioral effect is unverified; the
already-pinned reference-adjacency experiment retains the older wording.

The first real local Codex acceptance run exposed a separate continuity omission:
the researcher had saved a complete `planning-input.json` and acquired web media,
but the progress guard counted neither the planning-commit draft nor
`assets/web-index.json`. Research fingerprints now include those existing outputs;
the draft must contain a valid outline, decision object and nonempty source notes,
and formatting-only draft changes do not reset the counter. Resume points to the
saved draft/index. These are progress signals only: phase completion still requires
the canonical outline/decisions/notes, and the bounded guard remains enabled.

The rainwater local acceptance runs also exposed a distinction beyond transport:
the author received actual source images and rendered/revised native pages, yet
the delivered illustration remained basic. The continuing designer now owns
remaining design investigation when factual handoff material does not address
the actual expressive gap. Study finished work relevant to that gap, rather than
treating a factual schematic as complete craft guidance. Existing visual review
and bounded optional repair prioritize consequential subject/composition gaps
before peripheral polish; suggestion severity and delivery bounds are unchanged.
The existing native helper's five geometry choices are explicitly advertised,
with direct OOXML still available for other geometry. These changes are neither
aesthetic certification nor proof of improved default generations. A separately
recorded, reference-assisted scoped edit tests the intervention without confusing
it with an unseeded full-workflow comparison.

Observed acceptance limits: the second unseeded 5-page local Codex/Astra-high
run completed in 2,508 seconds, retained the exact independently reviewed author
artifact after the existing 360-second optional repair budget, and still produced
basic native illustration. Its author had no failed shell commands; this does not
support attributing the weak design solely to tool failures or missing image input.
A later same-author scoped page-3 edit received two task-local finished works and
specific regional feedback. Its continuous native cutaway, plant forms and attached
annotations visibly improved the host-assessed composition. Other four pages and
the click timing remained unchanged. The model exported its artifact and records
but timed out during the final reply; host recovery preserved that failure receipt,
completed the existing reference/notes register, verified exact parts/scope/fonts
and rendered the recovered bytes. This scoped example has no independent review
or target WPS playback certification and does not establish default-run gains.

The next iteration places a short host-owned design-improvement cue beside an
actually attached current-page preview. It asks the same author to locate the
highest-value unfinished region and decide local repair versus recomposition,
then render/view a useful edit during sequential authoring. It adds no judgment
to context-only, stale/missing-image or source-image-only responses, and creates
no score, required observation record, approval or extra model phase. Pixels have
priority at the existing frame-size limit; the entry guide is the fallback.
After the real tool-result write, the existing image-input event records the
cue hash beside exact file receipts. Neither the cue nor its successful delivery
establishes design understanding, an applied revision or improved craft. CLI-only
harnesses retain the guide/viewer route; the shared author guidance is consolidated.

Repeated material-prefetch timeouts exposed a diagnostic omission: auxiliary call
summaries were appended only after successful completion and asset import. An
empty failed-call list therefore could not establish that no search ran. Summaries
now retain observed usage and completed tool-event counts when the wait ends,
including failure; missing turn completion is `unconfirmed`, with partial usage
explicitly marked. Failure/cancellation still propagates through existing paths,
and no failed search becomes ready, inspected evidence or an acquired image.

Two bounded real retained-search diagnostics each reached the 150-second deadline
after nine completed web-tool operations. The caller combined image discovery,
provenance and conditional statistical follow-ups. Requests now emphasize their
primary material purpose. On timeout only, bounded URL/title breadcrumbs from
completed web-tool outputs also survive in failed-call diagnostics and the failed
synchronous tool response. They are explicitly unverified leads, not inspected
works, downloaded images, claims, selected assets or permission. The broker keeps
the failed state and normal input-basis/access rules; it never auto-retries.
Recorded-event replay and the real helper-to-broker test cover this recovery;
neither proves that a useful image has reached a designer or improved a page.

The first unseeded render-cue acceptance author delivered actual cue hashes and
current/previous native preview receipts. It found and embedded an authentic case
photo and made a useful conceptual hydrograph, but its initial mechanism page
remained a basic soil diagram with a side explanation. Cue delivery alone did
not establish the desired design gain. The following research handoff revision
restores task-relevant finished-work discovery to the existing researcher/editor
role and asks the continuing designer to describe intended visible finish in the
existing provisional direction. It adds no artist/reference quota or mandatory
layout, and retains scoped/offline/source limits. This next handoff revision still
requires its own real generation evidence; the ongoing pinned test is unchanged.

The next unseeded run delivered a full 475×583 built-landscape photograph to the
same author before page 3; its actual mechanism preview still used simple soil
blocks and repeated ellipse plants. This disproves neither native capability nor
the value of photography, but it does not establish the desired craft gain. The
research handoff also said simple native paths were sufficient and excluded
curves despite these not being user/source constraints. The author accepted that
direction; this is evidence of premature narrowing, not proof of sole causation.
Research/author guidance now explicitly separates source/user constraints from
advisory visual treatments. Existing reference guidance distinguishes a completed
physical project from a finished explanatory graphic and asks for a transferable
visible operation, beyond naming entities in the picture. Photos remain valid
references/assets, and no new source type, count, registry field, model stage or
acceptance gate is introduced. The run's pinned runtime is unchanged; these
instruction changes still need an unseeded behavioral test.

That next unseeded run acquired and supplied a complete NACTO bioswale graphic.
Its actual first author candidate improved real-case recognition using a site
overview and inlet close-up, while its mechanism remained basic. A later bounded
same-author diagnostic received the actual full-deck images and a general request
to choose a useful visual refinement, without a prescribed page/region, new
reference or specific repair. The author chose page 3 and added native roots,
material detail and recognizable drain components in 490.6 seconds after a
verified recovery. Only slide3.xml changed; text/run styles, timing and the other
four pages/dependencies were byte-identical. Host inspection found useful gains
in component recognition, with similar composition and still-limited artistic
finish. This is not an independent review, player test or unseeded first-draft gain.
The earlier diagnostic's terminal transport error and missing temporary workspace
remain recorded; recovery used a copy of the verified journal and frozen baseline,
without modifying the original journal or completed delivery.

The following small input experiment leaves the existing render cue's wording
and structured field intact and also emits it as plain inputText after the actual
images. Image indices/bytes stay unchanged; the existing frame bound still drops
only the optional cue when necessary. Successful writes record the plain-text
channel only if that exact block was in the response. This makes the current
author task explicit beside the render without adding a turn, review stage,
automatic critique, score or compulsory edit. The diagnostic does not establish
that metadata placement caused premature completion, or that this representation
change will reproduce its gain.

The fresh five-page local Codex/Astra-high test captured its first complete author
artifact before independent-review feedback (SHA-256
`1ae072772af2bf8c80332c1052fd2a174d47b325331a726a83d7f58e849f6ea7`).
Actual post-write receipts bind the 1083×794 teaching reference to the mechanism
page before authoring, and the current rendered page plus the plain-text cue to
its later tool calls. The following edit moved a condition label upward; the
complete first draft still has a broad flat soil mass and repeated primitive
plants. The case page does integrate an authentic, large entrance photograph.
Thus delivery is verified, but this run does not show the desired first-draft
craft improvement. Its case and references differ from the preceding run, so it
is neither a controlled causal estimate nor a stability measurement. Independent
review/final repair results must be reported separately from this frozen first
author artifact. More cue repetition is not justified by this negative result.
This full test subsequently completed in 2,317.97 seconds. Its existing bounded
optional repair finished in 352.16 seconds and the changed artifact was reviewed
again and received by the local delivery transport with matching SHA-256
`cf71eeb8c536f90c304fd70a1a7050ffaf5cd1b9568f0b2c2e5bafdc7fb12aaf`.
The visible changes complete the lower outlet, depict case stone separators/curb
openings and darken soil labels; they do not establish improved first-draft craft.
Native timing trees remain byte-identical, with the new outlet label in the
existing second-click group. Target-player playback remains unverified.
