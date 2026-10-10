# Workflow branches

The finite IDs are in [workflow-choices.json](../assets/workflow-choices.json).
They control consequential communication decisions, evidence, behavior and delivery.
The author owns visual direction and its concrete implementation. Branch labels,
artist names and object counts do not certify design quality. Keep content research
first, author in page order, and use the existing independent bounded reviews.

## Task entry and direction

Task entry is only `create` or `edit`, taken from the user request (or host mode when supplied). Preserve templates,
source fidelity, small editing scopes, offline instructions and installed capability
limits. Handle ordinary missing material inside the research/asset route. There is
no mandatory completeness/conflict classification or extra task type.

| Decision | Choose and execute |
| --- | --- |
| Viewing | `live`, `self_reading`, `dual_use`, `unspecified`: use established purpose; do not invent live use. Essential explanations remain visible. |
| Research | `supplied_only`, `targeted_verification`, `topic_research`: read actual material and resolve the corresponding evidence gaps. |
| References | `preserve_supplied`: retain required source design; `use_available`: reuse inspected material or task-specific knowledge, explain the basis; `targeted_search`: inspect relevant actual works/teaching before settling direction, recording successes or unavailable access. |
| Style family | `editorial`, `analytical`, `image_led`, `expressive`, `supplied_system`: choose for purpose. This family does not prescribe page geometry or exclude images, expressive typography or another page's analytical needs. |
| Palette roles | `inherited`, `neutral`, `semantic`, `expressive`: select relationships and emphasis; no default low-saturation scheme or mandated vividness. |
| Typography basis | `inherited`, `installed_role_system`: retain required type or choose available fonts for real roles. Font sizes/weights/line breaks remain design decisions. |

Write a short `design_direction`: this subject's visual premise, intended emphasis,
and sequence rhythm. Decide deliberately instead of averaging references into a
safe generic component system. Serious content still needs hierarchy and composition;
a simple treatment is appropriate when it serves that specific purpose.

## Content → audience task → strategy

Research notes retain the detailed evidence. The outline identifies useful meaning,
conditions and reader questions; do not lock long paragraphs into boxes before
choosing how to explain. Select the existing intent and eligible primary/support
forms, then the strategy below. The `role` names the audience question/benefit.

| Strategy | Entry condition and action |
| --- | --- |
| `observe` | Readers must recognize an actual object, interface, place, state or output. Acquire/inspect real images, official demonstration frames or embedded media; use native short annotations as needed. A prose feature map or invented image does not satisfy observation. Faithful native source recreation preserves its authorized conversion scope. |
| `relate` | Readers must understand mechanism, direction, adjacency or dependencies. Use evidence-grounded native relationships with short labels; add real/contextual imagery when it supplies a different useful role. |
| `compare` | Readers must judge quantities, evidence or alternatives. Use accurate native charts, essential tables, direct labels or comparable views. Do not turn paragraphs into a grid and call it a visual comparison. |
| `envision` | Readers must understand an original proposed scene, possibility or idea. Select appropriate original illustration, sourced contextual imagery, native concept relationships or a purposeful typographic statement. Mark concepts as concepts; do not counterfeit real cases/screens. |
| `read` | Wording itself carries the argument, definition, quote or conclusion. Edit to essential visible meaning and create type hierarchy, scale, alignment and whitespace. This is not an automatic card grid. |
| `act` | Readers must follow a sequence or make a decision. Make actions, outputs, gates and responsibility visible in a suitable sequence/comparison; keep labels short and preserve necessary conditions. |

Do not infer that every page about a product/place needs a photograph. Determine
which question requires seeing its real form/use, which needs relationships, and
which needs quantitative evidence. One page can combine these roles. A budget chart
may need no image; a real-case page must not hide its visual evidence behind prose
when recognizing that case is part of the explanation.

## Select a canvas composition and implement it

| Composition | Actual treatment and check |
| --- | --- |
| `image_field` | A selected image occupies the main field or background. Choose focal crop, supporting editable text and contrast; preserve the subject and provenance. |
| `image_with_type` | Integrate image and editable type through deliberate scale/position: beside, below, partly overlapping or visually interwoven. Specify the relationship; avoid a default boxed split. |
| `type_statement` | A concise main phrase/number/quote establishes focus through scale, weight, meaningful breaks and whitespace. Remove duplicate headlines and conclusions. |
| `editorial` | Organize short argument/evidence through columns, margins, side notes and a clear reading path. Avoid equal visual weight for unequal claims. |
| `annotated_visual` | Use an actual selected image/detail with short native callouts to make relevant evidence inspectable. A caption cannot substitute for an unrecognizable or tiny subject. |
| `relational_map` | Native positions/connections express actual relations. Do not wrap every label in a filled rectangle; choose enclosure only for a real grouping/boundary. |
| `data_display` | Accurate native chart/table with direct units, comparison and emphasis. Paragraph-filled cells still require editing. Keep comparable variables consistently encoded. |
| `sequence` | Order, progression or meaningful state change is visible; use native steps, frames or typographic pacing. Avoid long explanatory panels repeating the title. |
| `independent_panels` | Distinct, equally important items genuinely need separable fields. Define this benefit; panels are not the default container for arbitrary paragraphs. |

`visual_action` describes the actual dominant element, reading path and treatment.
Choose type scale, color, image crop, overlap, proportions and whitespace within
that strategy yourself. No universal font/palette, template rotation, image quota
or demand that all pages look different. Keep comparisons and the deck's identity
coherent, while varying emphasis and reading task as content requires.

New multi-page plans must have more than one form/composition, but this minimal
structural check is not evidence of successful visual variety. Review actual pages
and the sequence for repeated card/box language even when their branch IDs differ.

## Material and failure branches

| Asset route | Execute |
| --- | --- |
| `none` | The chosen native expression needs no external bitmap/media. Explicitly record this; do not combine it with another asset route. |
| `supplied` | Inspect appropriate authorized material and embed the selected bytes. |
| `web_import` | Acquire the required real/reusable material via WEB-MEDIA.md, inspect the returned file and embed it in its planned role. |
| `generate` | Use the exposed built-in tool for an original raster concept/illustration, inspect and embed it. No failed-search prerequisite. |
| `source_grounded_native` | Draw faithful editable analytical/technical relationships from actual evidence. Do not claim a photo/screenshot or spatial experience has been provided. |

File routes record `kind` (`documentary`, `illustrative`, `media`), `status`
(`planned`, `ready`, `unavailable`), `file` and `origin`. Planning can retain work
still to acquire. Before authored completion, selected files must be ready and
actually used on the planned page; native media bytes are not proof of playback.

| Observed failure | Action |
| --- | --- |
| DNS/connection/TLS outage | The host uses bounded transport/DNS recovery. Record its actual result; do not repeat blind URL swaps. Preserve the intended visual question and use an accessible same-evidence source when possible. |
| Page/404/403/non-media response | Find an actual supported direct-file source or a legitimate reusable alternative. Do not pretend an error page or search thumbnail is acquired media. |
| Size/partial transfer | Select an appropriate smaller source or clip within limits, preserving meaning and documenting conversion. |
| Tool/source genuinely unavailable | Reconsider representation against the same audience need. If essential real visual evidence remains absent, record the unmet requirement; changing a label to `relate` or adding a card does not resolve it. |

## Artwork and design-reference register

Record every actually applied outside work/teaching in `decision-plan.json.references`:

```
{"id":"R1","kind":"artwork","title":"Exact work/photograph/frame title",
 "creator":"Verified creator; explicitly record unknown attribution if necessary",
 "source":"https://original.source/work","inspection":"local_image",
 "evidence":"references/work.png","observed":"What is actually visible in this work",
 "borrowed":"The useful principle/relationship taken from it",
 "applications":[{"pages":["vision"],"action":"Concrete type/image/scale/color operation on this page"}]}
```

Kinds: `artwork`, `design_work`, `teaching`, `supplied_system`. Inspection modes:
`local_image` (actual task-scoped visual file), `hosted_visual` (actual displayed
image/frame, record its observable source/tool locator), `read_text` (an inspected
teaching passage), `unavailable` (no inspected evidence; borrowed=null,
applications=[], evidence=null). Text about an artwork cannot certify observing
its composition. A museum/award/designer name alone is not a work reference.

Use actual title, creator, source, observation and principle; distinguish creator
intent from your interpretation. Reference study does not grant embedding rights
or establish factual evidence about this project. Explore any relevant art form
and high-quality source; there is no fixed corpus or artist quota. Preserve a
supplied system or a simple task-appropriate direction without invented references.

Each applying page lists its `reference_ids`; application page IDs must agree.
Record observations and adaptations concisely in source-notes.md. Before final
export, run `design_references.py --workspace WORKSPACE` to preserve existing notes
and write work/creator/source/observation/borrowed idea/page action into the affected
slide notes. Core explanation remains on the audience canvas; the provenance
record need not add pages or overload visible text. In the user-facing completion
summary, briefly name the applied works and the ideas used, or state honestly that
no outside artwork was applied. Never present unviewed attempts as inspiration.

## Behavior, implementation and existing review

Behavior choices remain `static`, `click_reveal`, `internal_navigation`,
`embedded_playback`. New presentations require content-led `click_reveal`; choose
it for staged processes, arguments, examples and layered explanations. In
source-notes.md record entry context, each click's group, persistent context and
the final complete view. Static cover/single-message pages remain available;
internal navigation/playback or slide transitions alone do not replace this
requirement. Do not fake it with only a decorative title entrance. Preserve
faithful-source/scoped-edit behavior and protected historically admitted contracts.
Use animations.md for meaningful native builds; verify internal destinations and
actual embedded files, and distinguish static inspection from player verification.

Use [native-canvas.md](native-canvas.md) to measure text, crop/layer images and
make editable one-unit bars without writing repeated low-level XML. These helpers
implement object capabilities, not a page style. Snapshot first, author in order,
inspect actual full-size and reading previews and preserve source meaning.

Run `workflow_decisions.py --stage planning`, then `--stage authored --artifact
YOUR_EXPORT`. Host checks choices, actual asset embedding and final artwork notes.
Fresh tasks require v3; historical v1/v2 records remain readable through protected
recovery/explicit --allow-legacy without inventing provenance or modifying old bytes.
The existing visual review evaluates audience fit, actual sequence and reference
transfer; neither decision counts nor the artist register establish design quality.

## Implementation within the chosen branch

Use content-led-composition.md while planning and authoring. Existing role and
visual_action carry the audience question and concrete focus, proportions, reading
path and enclosure meaning; source notes carry entry/click/final groups. No new
schema or admission gate is needed. Form/composition IDs must resolve into actual
content-specific operations before a reusable object helper is written. At natural
section milestones inspect the already authored sequence, including repeated body
pages, using saved previews. Preserve comparable encoding and source/edit scope.
