---
name: pptx
description: Research, create and edit standalone native PowerPoint with editable content, native animation, actual rendering and independent reviews.
---

# Native PowerPoint

Use scripts/pptx.py with the host's exact Python 3.11+ interpreter from
tool-manifest.json. Paths below are relative to this skill. Read the task's
tool-quickstart.md for current interfaces; use installed helpers rather than
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

Default new English/Latin to Times New Roman and Chinese to SimSun (宋体), using
genuine font metrics and explicit runs/themes. Preserve explicit user/template
requirements. Extra faces require actual coverage/weight and recipient availability
or verified editable embedding. Read [fonts](references/fonts.md) and
[Windows WPS compatibility](references/windows-wps.md) when choosing or repairing
text/connectors. Mac/static previews do not certify Windows WPS playback.

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
resolve concrete composition and visible wording while authoring each page.
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

Read [Content-led composition](references/content-led-composition.md) for the design
brief. Give the subject an effective visual expression suited to this audience and
purpose: concrete examples, relationships and results should become inspectable.
Choose scale, composition, density, layering, color and image/type relationships.
Text-led pages, imagery and detailed native diagrams can all be appropriate.
Maintain coherent visual encoding across the deck while letting content shape pages.

For new decks or substantive redesigns with creative latitude, actively explore
whether relevant art/design/scientific illustration can strengthen the direction.
Inspect the actual work and transfer useful visual relationships into current pages.
A template protects its required elements; it does not supply every body-page design.
Use the reference procedure in Research and assets; no artist list, reference quota
or separate inspiration stage. Record only actually inspected/applied work.

Start from the supplied template/source when required, otherwise assets/blank.pptx.
Use one main author and make pages in presentation order. Helpers may prepare
independent later-page evidence/assets through the host's PREFETCH.md; inspect and
choose their results. Work with actual assets, not assumed future files.

Use [native pages](references/native-pages.md), [native batches](references/native-batch.md)
and [native canvas](references/native-canvas.md) when available for page creation,
font measurements, shapes, image crops/layers and editable charts. Helpers implement
chosen objects, not a universal page layout. Technical references are linked below.

New presentations require meaningful native click reveals. Plan entry context,
semantic click groups, persistent orientation and a complete readable final view.
Static covers and single-message pages are allowed; an entirely static deck or
cosmetic title entrance does not satisfy this requirement. Read
[Animations](references/animations.md); preserve faithful-source/scoped-edit behavior.

Render and inspect each page at full size and normal reading scale before proceeding.
Check source meaning and technical fit, and whether the intended subject, mechanism
or comparison actually leads the page. Refine concrete weaknesses while making it.
At natural section boundaries compare saved previews for sequence coherence and
rhythm. Existing render checks serve this purpose; no new approval stage is needed.
Update provisional decisions when actual material or renders justify another approach.

Register each applied outside work once with its inspected evidence and page actions.
Before final export, use design_references.py --workspace PARTS_DIR to generate
page reference associations/slide notes; preserve existing notes. Run
workflow_decisions.py --stage authored --artifact YOUR_EXPORT on the exact candidate.
This checks coverage, assets, notes and native behavior, not aesthetic quality.

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
Use existing bounded repair routes, not taste-score loops. Record findings/resolutions
in review.md with reviewer and frozen artifact hash/version. Static timing/state
inspection is not target-player playback; say exactly what was verified.

On resume inspect retained pages, exports, sources and receipts before continuing.
Preserve historical originals and frozen reviewed bytes. Ordinary chat does not
invalidate reviews; modification requests update only affected material. Deliver
only the returned export path and briefly identify actual reference applications
or honestly report that none were used.

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
