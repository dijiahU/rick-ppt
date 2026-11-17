---
name: pptx
description: Research, create and edit standalone native PowerPoint with editable content, native animation, actual rendering and independent reviews.
---

# Native PowerPoint

Use scripts/pptx.py with the host's exact Python 3.11+ interpreter from
tool-manifest.json. Paths below are relative to this skill. Read the task's
tool-quickstart.md for the scenario folders, then open only needed groups through
tool_prepare.py --group GROUP_ID. Use installed helpers rather than
rediscovering commands. Outside a host, verify the environment first.

## Delivery boundaries

Deliver one standalone PPTX with editable essential text, analytical diagrams,
charts and native animation. Use direct OOXML and embedded assets. Preserve original
files and authorized edit scope. Content Add-ins, browser scenes, runnable code
labs, local servers, macros and external media dependencies are outside this workflow.

Preserve source facts, units, symbols, conditions and operation order. Distinguish
reported results, interpretation and illustrative examples. Real interfaces,
historical/documentary subjects and case evidence require authentic sources.
[Research and assets](references/research-and-assets.md) covers acquisition and evidence.

New decks must include useful pictures, concrete native illustrations/schematics,
or permitted sourced/generated imagery. Statistical charts/tables and trees of
text labels do not satisfy this pictorial requirement. See [Art direction](references/art-direction.md#4-turn-content-into-a-visible-relationship)
for what qualifies; preserve faithful/scoped work and explicit text-only requests.

For hosted tasks use the verified font pair in `capabilities.json.font_assets.defaults`.
The standalone default is Times New Roman for English/Latin and SimSun (宋体) for Chinese.
Use genuine selected font metrics and explicit runs/themes. This includes text recreated from an
image without a specified source typeface; a rounded or handwritten appearance is
not permission to choose a decorative font. Preserve explicit user font choices
and actual supplied template typefaces. Functional exceptions need actual
family/weight/glyph-coverage evidence plus recipient availability or verified
editable embedding. Read [fonts](references/fonts.md) and
[Windows WPS compatibility](references/windows-wps.md) when choosing or repairing
text/connectors. Mac/static previews do not certify Windows WPS playback.

## Roles and continuity

One continuing author can own research, examples, narrative, design and native
implementation in the same conversation; research and authoring remain ordered
checkpoints. Follow the host's pinned context mode. New local Codex tasks retain
that conversation; independent content and visual reviews use separate contexts.
Batch independent search queries and overlap permitted downloads without splitting
the author’s judgment. Use model-backed helpers only when the host advertises them.
Legacy/API/DSH split routes retain the actual outline, source notes, inspected
material and protected scope as their handoff. Preserve one canonical native
workspace and page order; do not invent an independent collaborator.

## Research and plan

Read [Content](references/content.md). Establish purpose, audience, viewing mode,
language and source scope. Inspect supplied material. For topic research, discover
broadly before narrowing, deepen useful cases and verify selected claims. Targeted
fact checking and design exploration are independent: a specified paper or a supplied
template does not by itself prohibit relevant visual research. Honor actual
supplied-only/offline limits and small editing scopes.

Write source-notes.md for evidence, qualifications and useful reference observations.
During planning, turn the request into page-specific design intentions using the
existing handoffs: audience outcome, main subject/evidence, the relationship to make
visible, a chosen working expression and its visible completion condition. Resolve
these before native authoring; follow content.md / page-design.md. Separate user
requirements and facts from revisable proposals, and preserve scoped edit boundaries.
Write outline.json with title, purpose and ordered slides (stable id, title,
substantive summary). Include the content and a short reader-facing account of its
proposed expression in each designed page's summary. Plan the main visual decision
now; the continuing designer refines composition and wording against actual material
and renders. A provisional plan is a concrete starting point, not a final layout.
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
mandatory design categories or eligibility combinations. When available,
[planning_commit](references/planning-commit.md) commits outline/decisions/notes together;
its success satisfies the planning check. Otherwise run workflow_decisions.py
--stage planning. Preserve historically admitted records on recovery.

## Design and author

Use [Shared aesthetic judgment](references/design-completion.md#shared-aesthetic-judgment)
from planning through rendered refinement: task authenticity, visible relationships
and accomplished craft work together. Review feedback names gaps and visible targets;
the continuing author owns the composition. Read [Art direction](references/art-direction.md)
once at design entry and use [Sequential craft](references/content-led-composition.md)
while authoring; [Worked design decisions](references/art-direction-examples.md) show
decisions and rendered checks (the host supplies them at first author entry when
available). Apply operations to current evidence, keeping composition open.

Keep one short provisional deck-wide agreement in design_direction and source notes;
test it on the first substantive page in normal order and recompose before propagating
if material or render defeats it. Build the main visual relationship before details,
keep coherent semantic encoding, and let proportion, density and image/type relations
follow content. For new decks or substantive redesigns with creative latitude,
actively explore relevant art/design/scientific illustration, inspect actual works and
transfer useful relationships (procedure in Research and assets; no artist list,
quota or separate inspiration stage; record only inspected/applied work). A template
protects its required elements, not every body-page design. For poster, editorial,
identity or image/type references consider [Pinterest](references/pinterest.md)
alongside original portfolios; links alone are not inspection.

Start from the required template/source, otherwise assets/blank.pptx. One continuing
designer makes pages in presentation order; helpers may prepare later-page
evidence/assets via the host's PREFETCH.md when available — inspect and choose their
results, and never assume future files. Use [native pages](references/native-pages.md),
[native batches](references/native-batch.md) and [native canvas](references/native-canvas.md)
for pages, font measurement, shapes, crops/layers and editable charts (helpers
implement chosen objects, not a layout); [image recreation](references/image-recreation.md)
for supplied-image recreation; [execution continuity](references/execution-continuity.md)
to resume from current files with all requirements intact.

New presentations require meaningful native click reveals: plan entry context,
semantic click groups, persistent orientation and a complete readable final view.
Static covers and single-message pages are allowed; an entirely static deck or a
cosmetic title entrance is not. Read [Animations](references/animations.md); keep
faithful-source/scoped-edit behavior.

Develop each page by build-render-view-revise (art-direction.md §6). Render when the
main composition, real material and key wording can be judged; view the exact preview
through the image channel at reading scale (page-design host context with page_id and
workspace when supported) — paths and render success are not viewing. Fix the most
useful feasible improvement while authoring, keep earlier renders and snapshot before
substantial recomposition, revert regressions. Validity/readability alone is
insufficient; within time/repair bounds keep the best verified version and report
remaining limits. No forced edit, revision quota or approval stage. At section
boundaries compare saved previews for coherence. The page-design helper may bind
consequential observations to render bytes; that grants no review pass.

Register each applied outside work once with inspected evidence and page actions, then
before saving a complete candidate run design_references.py --workspace PARTS_DIR to
write reference associations/slide notes (preserving existing notes; no manual copy of
the register). Speaker notes carry useful cues, explanation or citations; a full
transcript only when requested. Export with
`scripts/candidate_save.py --task-root TASK_DIR --workspace PARTS_DIR --output exports/CHOSEN_VERSION.pptx`,
which renders, runs the authored check (assets, notes, native behavior — not aesthetics)
and atomically updates delivery.json. Save meaningful finished repairs before optional
polish. The original route remains: workflow_decisions.py --stage authored --artifact
YOUR_EXPORT on the exact candidate, declared explicitly. Independent review follows.

## Review, revise and deliver

Use two fresh independent contexts, [content review](references/content-review.md) and
[visual review](references/visual-review.md), with required artifacts and the guide but
not the author's conversation. Content reads the audience surface first, then
sources/brief; visual judges pages/sequence before reference claims. Reviewers do not
edit; disclose missing independence.

Report technical validity and design readiness separately. Required findings concern
explicit requirements, substantive errors/omissions, comprehension/readability or
broken native features; artistic alternatives are suggestions. Authors and visual
reviewers share the [Design completion](references/design-completion.md) standard and
judge subject, visible relationships and craft against this use, not information
presence. 清楚只是最低要求：信息完整、文字可读、没有排版错误，不能代替画面设计完成；严肃可以克制，但不能只是把内容摆齐。
visual_craft rates composition, visual expression, typography and sequence with
page/region evidence; a substantive low rating enters the bounded response. The host
reads ready / needs_revision / uncertain apart from validity; substantive primary
findings return once to the continuing author, minor preferences do not. A changed
candidate replaces the reviewed baseline only when supported as better without
material regression. Keep incomplete/uncertain status at the budget boundary; no
taste-score loop or unsupported readiness claim. Historical receipts and scoped
fidelity edits keep their policy. Record findings/resolutions in review.md with
reviewer and frozen hash/version; static timing/state inspection is not playback.

On resume inspect retained pages, exports, sources and receipts. Preserve historical
originals and frozen reviewed bytes; ordinary chat does not invalidate reviews and
modification requests update only affected material. Deliver only the returned export
path and name actual reference applications, or state none were used.

## Technical references

Unpack with scripts/pptx.py and retain the workspace path. Put --workspace before
list slides / inspect N / render N / export. Take snapshots for risky changes;
inspect partial failures before retry. Preserve IDs, relationships and untouched
source parts. [Tool preparation](references/tool-preparation.md) explains host refresh.

Read as needed: [package](references/ooxml-overview.md),
[shapes](references/slides-and-shapes.md), [text](references/text.md),
[images](references/images.md), [charts](references/charts.md),
[groups/connectors](references/groups.md), [masters](references/masters-and-layouts.md),
[relationships](references/relationships.md), [safe changes](references/safe-mutation-rules.md),
[formulas](references/technical/formula-fidelity.md),
[advanced objects](references/technical/native-capabilities.md).
