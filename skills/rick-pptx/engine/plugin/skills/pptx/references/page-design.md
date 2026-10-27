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
Selected later material may still be pending through the existing prefetch route;
do not wait for unrelated pages or pretend a missing file has been inspected.
The tool reports local file availability/hash and image dimensions. It does not
authenticate a photograph, verify a claim, fetch links or establish inspection.
Duplicate/malformed optional records are diagnosed without invalidating planning.

```sh
HOST_PYTHON PLUGIN/skills/pptx/scripts/page_design.py context --task-root TASK --page-id ACTUAL_ID --workspace PARTS_DIR
```

The result includes the original page summary, optional handoff, selected asset
records, file checks, note location and recent author observations. `--workspace`
is optional for content lookup. When notes are too long for an excerpt, read the
relevant original section; the tool does not invent a shortened factual account.

## Respond to the actual page while making it

Use the existing normal-size page preview first, then inspect uncertain detail.
Separate technical problems from expression problems. A text-fit or endpoint
defect calls for a local repair. A comparison that remains hidden inside prose may
need a change of focus, scale, grouping or representation. More decoration does
not itself reveal the comparison. Retain successful semantic encoding across pages;
change an ineffective provisional composition before repeating it.

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
