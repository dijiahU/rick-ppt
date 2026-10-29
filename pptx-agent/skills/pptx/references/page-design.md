# Page evidence and consequential design observations

Use current source notes directly when they are sufficient. `page_design.py`
retrieves a selected page's material when notes are long or a visual/content gap
is unclear. It never selects a layout, researches sources, or approves a design.
The existing outline, v4 decisions and plain Markdown notes remain valid.

## Research handoff inside existing notes

For a material-rich page, an optional fenced object in `source-notes.md` can make
its evidence and actual material easy to retrieve. `page_id` is the existing stable
outline ID. All other fields are optional; include only useful information.

```pptx-handoff
{
  "page_id": "attention-example",
  "question": "How does the current position combine information from other positions?",
  "evidence": [{"source": "references/paper.pdf", "locator": "Actual section/figure", "claim": "The supported mechanism, including its conditions"}],
  "materials": [{"file": "assets/attention-reference.png", "role": "Actual inspected detail useful for this explanation"}],
  "preserve": ["Distinguish illustrative weights from reported measurements"],
  "uncertainties": ["Exact example values still need to be checked"],
  "visual_opportunity": "The alignment and aggregation relationship could be made inspectable"
}
```

This is a format example, not available evidence or a required diagram treatment.
Use actual task paths/locators. A simple quotation or summary may need no block.
Faithful recreation identifies source labels, regions, relationships and uncertainty;
it does not authorize adding a new narrative or decorative artwork. Scoped edits
retain the original meaning, objects and protected user changes.

The researcher supplies facts, useful examples, actual material, qualifiers and
gaps. Leave final wording, composition and scale to the continuing designer.
Use visual_opportunity for the audience's visible task (recognize, compare, trace
or inspect) rather than a fixed layout. A factually supported schematic does not
automatically close a missing scene/detail needed for that task; retain that gap
in existing uncertainties/plain notes and seek a permitted useful alternative
where consequential. This adds no required field, image count or waiting stage.
Selected later material may still be pending through the existing prefetch route;
do not wait for unrelated pages or pretend a missing file has been inspected.
The tool reports local file availability/hash and image dimensions. It does not
authenticate a photograph, verify a claim, fetch links or establish inspection.
Duplicate/malformed optional records are diagnosed without invalidating planning.

```sh
HOST_PYTHON PLUGIN/skills/pptx/scripts/page_design.py context --task-root TASK --page-id ACTUAL_ID --workspace PARTS_DIR
```

The result includes the original page summary, optional handoff, selected asset
records, file checks, note location and recent author observations. It also projects
only references whose existing `applications[].pages` explicitly names this stable
page ID: identity/source, declared inspection, observed/borrowed relationship and
the current application action. A local-image evidence file is checked without
upgrading missing/unavailable evidence or claiming a new inspection. `--workspace`
is optional for content lookup. When notes are too long for an excerpt, read the
relevant original section; the tool does not invent a shortened factual account.

When exposed by the host, `pptx_page_design_context(page_id=...)` wraps this same
lookup and supplies supported local material/reference files as actual image
content in its tool response. Use it before settling a main composition that
depends on those images. It includes this page's handoff materials and ready
planned assets, not every prefetch result or the whole reference register. Exact
file hashes, pixels and image content positions identify what was supplied; a
small reference image stays that image, not proof of seeing its full-size source.
The host logs a send only after writing the image-bearing response. This proves
transport delivery, not model understanding, selection or visual approval.
Unchanged files already supplied through this tool in the same thread reuse their
delivery receipt, including across pages; each page still gets its own application
action. `repeat_images=true` can resupply a picture lost from context. New threads
receive the bytes again. No images are acquired again or silently promoted to an
inspected/selected state by this reuse.

The CLI remains read-only text. In a harness without this host callback (including
the current DSH adapter), open the relevant files through its existing image viewer
before choosing their crop/scale and image/type relationship. Newly acquired main
assets need the same actual viewing. Paths, Markdown links, ready states and
search summaries are not image input. Missing, unsupported or transport-oversized
images remain unattached; use an available image tool or the existing permitted
fallback. Do not add an image/reference to every page or wait for unrelated pages.

## Respond to the actual page while making it

Render the current page once its main composition, actual material and key wording
are inspectable. Small decorative details can wait until the expression works.
Use the existing normal-size page preview first, then inspect uncertain detail.
Separate technical problems from expression problems. A text-fit or endpoint
defect calls for a local repair. A comparison that remains hidden inside prose may
need a change of focus, scale, grouping or representation. More decoration does
not itself reveal the comparison. Retain successful semantic encoding across pages;
change an ineffective provisional composition before repeating it.

After `render N`, call `pptx_page_design_context(page_id="ACTUAL_ID",
workspace="ACTUAL_PARTS_DIR")` when the host exposes this interface. It returns
the current page's rendered PNG/JPEG/WebP ahead of supporting images, bound to
native inputs and render hashes. Without the host callback, use the prepared CLI
context command with `--workspace`, then open `native.preview.image` through the
existing image viewer. The CLI's paths/status do not constitute visual delivery.
Neither route secretly renders or edits. A stale, missing or changed preview
cannot be delivered as current; render that page through the existing renderer
and try again. Retain unavailable-view limits honestly if viewing is unsupported.

Choose a concrete correction from the image: which region/relationship fails and
what change could address it? Make the scoped edit, render that page again and
view the changed image before proceeding. Compare the relevant before/after
regions, including content, qualifiers and any surrounding objects affected by the
edit. Earlier renders are immutable; use an existing native snapshot before a
substantial recomposition so an unsuccessful change can be reversed.

The host records `design.page_preview_sent` only after writing real image content,
with page/native/render identities and any prior preview actually supplied in this
thread. `previous_preview_input` identifies that earlier input; it does not claim
the model retained it. Even identical render bytes are supplied on a preview
request, so changed native inputs are never credited on a cached-image assumption.
These are transport facts, not evidence that a correction was understood or better.

With workspace, `native.objects` reuses the current page's existing native inspection,
bound to `page_sha256`; large indexes explicitly defer to the existing inspect
command rather than displacing the preview. Commands alone are not an object index.
For a consequential change, optional `compare_previous=true` attaches the last
successfully supplied preview of the same page/workspace/thread beside the current
one. It is labelled historical, checked against its saved file hash and never
reported as the current render. No previous input, unavailable current render or
changed old file means no such attachment. Use actual attached images directly;
open files again only for missing input or a useful detail. To compare a concrete
reference relationship, `repeat_images` can resupply existing applicable files.

A first result needs no manufactured change when supported meaning, the intended
visual task and audience-appropriate composition/craft are resolved at reading
scale within scope. Validity/readability alone does not prove that. Address the
main visual gap within existing task/repair bounds, keep the best verified result
at the limit and report unresolved design limits; no revision quota, score target
or per-page record requirement. Reuse saved unchanged pages for
sequence inspection and do not wait for unrelated later-page material.

The first substantive page testing a direction stays in normal presentation order.
No pilot pages, per-page alternative quota, extra reviewer or approval is added.
Useful artistic/design/scientific references can resolve a concrete expression
problem within the existing source scope; inspect real works and record their
actual application through the existing reference register.

Record only consequential observations, attempts or reversals worth retaining for
later pages/resume. An ordinary successful page needs no additional form. A small
task-local JSON object can bind such a note to the existing actual render:

```json
{
  "observation": "The supported aggregation relationship was still hidden in body text.",
  "actual_change": "Enlarged the actual input/output relationship and removed duplicate explanation.",
  "preserve": ["Original labels and evidence limits"],
  "outcome": "changed"
}
```

```sh
HOST_PYTHON PLUGIN/skills/pptx/scripts/page_design.py record --task-root TASK --page-id ACTUAL_ID --workspace PARTS_DIR --input observation.json
```

`outcome` is `changed`, `retained` or `unresolved`; describe the actual action, even
when an attempted design was reverted. The helper appends a
`pptx-design-observation` fence to the existing notes, preserving previous bytes.
It records native-input and preview hashes, plus the preceding observation when
available. It refuses to bind an observation to missing, changed or stale render
bytes. Recording remains optional and cannot become a delivery requirement.

Freshness is conservatively bound to the whole native package. Later-page/shared
resource changes can make an older preview stale without proving that its visible
page changed. Reuse saved images for sequence inspection; do not rerender unchanged
pages just to produce observation records. Legacy renders without fingerprints
remain available through the existing tools, with freshness unestablished here.

The author statement is unverified. Changed bytes do not establish an improvement,
a render does not prove the image was viewed, and this record never substitutes
for independent review, click-state checks or target-player playback. On resume,
consult current evidence and retained pages; preserve old observations as history
rather than treating them as an approved design direction.
