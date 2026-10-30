---
name: rick-pptx
description: Research, design, create and edit standalone editable PowerPoint with content-led composition, inspected images and art references, native click reveals, actual rendering and independent reviews. Use for PPTX creation, redesign and scoped edits; preserve supplied templates and scope.
---

# Rick PPTX

For new presentations and substantive redesigns on a configured DSH backend,
use the packaged [full workflow](references/full-workflow.md) by default. Loading
this file alone does not start that engine. Run portable_workflow.py with the
explicitly selected provider/model configuration; then inspect its status and
host execution receipt. It handles planning/design handoff, material preparation,
native authoring, independent reviews, bounded repairs, recovery and traces.
Use core helpers directly for scoped edits or explicitly requested manual work.
Report that route accurately; do not describe it as a full managed run.

Use the actual selected account/model and available services. Do not infer API
access from a desktop subscription or silently switch harness, model or account.
If the selected harness has no complete adapter, or required prerequisites are
missing, report the specific gap and preserve work; do not silently downgrade a
requested complete run. Another harness invoking --backend dsh still uses DSH.

Resolve SKILL_ROOT from this file. Use scripts/pptx.py with Python 3.11+, lxml,
Pillow, jsonschema and fonttools in a separate task folder outside the skill.
First run `python SKILL_ROOT/scripts/doctor.py`; read
[Environment and commands](references/environment.md) when needed. Rendering needs
LibreOffice and Poppler; recipients need only the PPTX. Do not silently install
dependencies. This skill does not provide model keys or website queues. The full
workflow creates reviewer contexts through its selected harness; search and
generation use actual configured host services. Never package credentials.
Save request.json with mode (create/edit) and agreed language.

## Delivery boundaries

Deliver one standalone PPTX with editable essential text, analytical diagrams,
charts and native animation. Use direct OOXML and embedded assets. Preserve original
files and authorized edit scope. Content Add-ins, browser scenes, runnable code
labs, local servers, macros and external media dependencies are outside this workflow.

Preserve source facts, units, symbols, conditions and operation order. Distinguish
reported results, interpretation and illustrative examples. Real interfaces,
historical/documentary subjects and case evidence require authentic sources.
[Research and assets](references/research-and-assets.md) covers acquisition and evidence.

Default new English/Latin to Times New Roman and Chinese to SimSun (宋体), using
genuine font metrics and explicit runs/themes. This includes text recreated from an
image without a specified source typeface; a rounded or handwritten appearance is
not permission to choose a decorative font. Preserve explicit user font choices
and actual supplied template typefaces. Functional exceptions need actual
family/weight/glyph-coverage evidence plus recipient availability or verified
editable embedding. Read [fonts](references/fonts.md) and
[Windows WPS compatibility](references/windows-wps.md) when choosing or repairing
text/connectors. Mac/static previews do not certify Windows WPS playback.

## Roles and continuity

The content researcher/editor owns evidence, examples, audience questions and the
ordered explanation. One continuing designer/native author owns art direction,
all native pages and scoped repairs. When separate contexts are available, hand
over the current outline, source notes, actual references/material and protected
scope; keep raw research/tool conversation out of the designer's input. A single
local assistant can perform these roles in order without pretending to have
independent collaborators. Preserve one canonical native workspace and page order.

## Research and plan

Read [Content](references/content.md). Establish purpose, audience, viewing mode,
language and source scope. Inspect supplied material. For topic research, discover
broadly before narrowing, deepen useful cases and verify selected claims. Targeted
fact checking and design exploration are independent: a specified paper or a supplied
template does not by itself prohibit relevant visual research. Honor actual
supplied-only/offline limits and small editing scopes.

Write source-notes.md for evidence, qualifications and useful reference observations.
Write outline.json with title, purpose and ordered slides (stable id, title,
substantive summary). Plan the explanation and a provisional visual direction;
leave concrete composition and visible wording to the continuing designer.
Hand over traceable source locations, useful examples and necessary qualifications,
not final equal-length paragraphs or fixed coordinates. The designer may refine
expression and request focused missing evidence while preserving factual meaning.
For material-rich pages, [page evidence](references/page-design.md) provides optional
indexed pointers within the same notes and a current-page lookup tool. Simple
pages and scoped edits retain their existing lightweight handoff.
Use the requested language for public copy and notes; preserve proper names/code.
Publish the outline through the host when available and synchronize revisions.

The compact v4 decision-plan.json records the existing create/edit entry, viewing,
factual research route, actual template elements to protect, a short design direction,
page behavior/assets and any applied references. [Delivery decisions](references/workflow-branches.md)
defines the exact format. Visual forms and compositions are author choices, without
mandatory design categories or eligibility combinations. Run scripts/workflow_decisions.py --stage planning --mode create (or edit)
from the task folder. Preserve historically admitted records on recovery.

## Design and author

The continuing designer reads [Art direction](references/art-direction.md) once
at design entry and uses [Sequential craft](references/content-led-composition.md)
while authoring. The guide gives concrete ways to develop focus, scale, spatial
relationships, typography, imagery and rhythm without a fixed page taxonomy.
[Worked design decisions](references/art-direction-examples.md) demonstrate decisions and rendered checks. The host supplies this short guide at first author entry when available; otherwise read a relevant example. Apply the operation to current evidence, keeping composition open.

Establish one short, provisional deck-wide visual agreement in the existing
design_direction and source notes, then resolve the current page's composition
and wording. Test the direction on the first substantive page exercising it in
normal presentation order. If the actual material or render defeats the idea,
recompose before propagating it. Preserve facts, scope and effective semantic
encoding; an early layout choice is revisable, not a delivery constraint.
Let the audience inspect useful subjects, mechanisms, changes and comparisons.
Build the main visual relationship before supporting details; use actual renders
to refine expression as well as technical fit. Retain coherent semantic encoding
while allowing content-led changes in proportion, density and image/type relations.

For new decks or substantive redesigns with creative latitude, actively explore
whether relevant art/design/scientific illustration can strengthen the direction.
Inspect the actual work and transfer useful visual relationships into current pages.
A template protects its required elements; it does not supply every body-page design.
Use the reference procedure in Research and assets; no artist list, reference quota
or separate inspiration stage. Record only actually inspected/applied work.

Start from the supplied template/source when required, otherwise assets/blank.pptx.
Use one continuing designer/native author and make pages in presentation order. Helpers may prepare
independent later-page evidence/assets through the host's PREFETCH.md when available; inspect and
choose their results. Work with actual assets, not assumed future files.

Use [native canvas](references/native-canvas.md) for
font measurements, shapes, image crops/layers and editable charts. Helpers implement
chosen objects, not a universal page layout. Technical references are linked below.

New presentations require meaningful native click reveals. Plan entry context,
semantic click groups, persistent orientation and a complete readable final view.
Static covers and single-message pages are allowed; an entirely static deck or
cosmetic title entrance does not satisfy this requirement. Read
[Animations](references/animations.md); preserve faithful-source/scoped-edit behavior.

Develop each page through a build-render-view-revise loop. Render once its main
composition, real material and key wording can be judged, before polishing minor
decoration. View the exact preview through the image channel at normal reading
scale and inspect uncertain detail at full size. Use the existing page-design host
context with page_id and workspace after rendering when supported; otherwise open
the returned image with the available viewer. Paths and render success are not viewing.
Use the rendered page to choose the most useful feasible design improvement.
Locate the affected region and decide local repair or substantial recomposition
within scope; implement it while authoring, then render/view the result before
proceeding. Final optional repair does not replace developing the page. Keep earlier
renders and snapshot before substantial recomposition; revert a regression when
appropriate. Within creative scope, retain a first result when supported meaning,
the intended visual task and audience-appropriate composition/craft are resolved
at reading scale. Validity/readability alone is insufficient. Address consequential
visual gaps within existing time/repair bounds; keep the best verified version at
the limit and report remaining design limits. No forced edit, revision quota or
new approval stage. Preserve faithful/scoped work.
At section boundaries compare saved unchanged previews for sequence coherence.
The page-design helper can optionally bind consequential author observations to
render bytes in existing notes; these records grant no independent review pass.

Register each applied outside work once with its inspected evidence and page actions.
Before saving a complete candidate, use design_references.py --workspace PARTS_DIR
to write page reference associations/slide notes; preserve existing notes.
Use `scripts/candidate_save.py --task-root TASK_DIR --workspace PARTS_DIR --output exports/CHOSEN_VERSION.pptx`
to export/render, run the existing authored check and atomically update delivery.json.
Save meaningful finished repairs before further optional polish, refreshing after
additional completed corrections. The check covers assets, notes and native behavior,
not aesthetic quality. The original export route remains available: run
workflow_decisions.py --stage authored --artifact YOUR_EXPORT on its exact candidate
and declare it explicitly. Independent review follows either route.

## Review, revise and deliver

Use two fresh independent contexts: [content review](references/content-review.md)
and [visual review](references/visual-review.md). Give required artifacts and the
relevant guide, without the author's conversation. Content first reads the audience
surface, then sources/brief. Visual review judges actual pages/sequence before
reference claims. Reviewers do not edit; if independence is unavailable, disclose it.

Report technical delivery validity and design readiness distinctly. A readable,
accurate deck may still need concrete design refinements. Required findings concern
explicit requirements, substantive errors/omissions, comprehension/readability or
broken native features; discretionary artistic alternatives remain suggestions.
Authors and visual reviewers use the same [Design completion](references/design-completion.md)
standard. At first design entry and existing render points, judge the actual
subject, visible relationships and craft against this task's use, not the presence
of information alone. The host consumes ready / needs_revision / uncertain
separately from technical validity. Substantive primary findings can return once
to the continuing author within the existing bound; minor preferences alone do
not trigger a pass. Compare actual before/after pages: keep a valid candidate
only when supported as better without material regression; otherwise retain the
reviewed baseline. Preserve incomplete/uncertain design status at the budget
boundary; no repeated taste-score loop or unsupported readiness claim.
Historical receipts and scoped fidelity edits retain their prior policy. Record findings/resolutions
in review.md with reviewer and frozen artifact hash/version. Static timing/state
inspection is not target-player playback; say exactly what was verified.

On resume inspect retained pages, exports, sources and receipts before continuing.
Preserve historical originals and frozen reviewed bytes. Ordinary chat does not
invalidate reviews; modification requests update only affected material. Deliver
only the returned export path and briefly identify actual reference applications
or honestly report that none were used.

## Technical references

Use [execution continuity](references/execution-continuity.md) to reuse current
saved work and actual tool interfaces without repeating unchanged preparation.

Unpack with scripts/pptx.py and retain the workspace path. Put --workspace before
list slides / inspect N / render N / export. Take snapshots for risky changes;
inspect partial failures before retry. Preserve IDs, relationships and untouched
source parts. Use the verified environment interpreter consistently.

Read as needed: [package](references/ooxml-overview.md),
[shapes](references/slides-and-shapes.md), [text](references/text.md),
[images](references/images.md), [charts](references/charts.md),
[groups/connectors](references/groups.md), [masters](references/masters-and-layouts.md),
[relationships](references/relationships.md), [safe changes](references/safe-mutation-rules.md),
[formulas](references/technical/formula-fidelity.md),
[advanced objects](references/technical/native-capabilities.md).
