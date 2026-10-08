---
name: pptx
description: Research, create and edit standalone native PowerPoint with editable content, native animation, actual rendering and independent reviews.
---

# Native PowerPoint

Use scripts/pptx.py with Python 3.11+ and installed dependencies; prefer the plugin's
.venv/bin/python. Paths below are relative to this skill.

For new decks and substantive rewrites, follow these four stages. Small edits preserve
the supplied style, content and unaffected pages; change, render and verify only the
authorized scope. Do not run full research for a title change. Critique changes no files.

## 1. Research content

Read [Content](references/content.md). Establish purpose, audience, viewing mode,
language and source scope. Read actual supplied material, including relevant figures,
examples and conditions. Search/open reliable sources for gaps and current/uncertain
claims when allowed. A source title or search snippet is not evidence of reading.

Give content the first claim on effort: understanding, reading, evidence, examples,
explanation, organization and revision. Investigate a subject enough to produce useful
substance before investing in presentation. Match depth to the task and audience;
there is no fixed time/token percentage, search count or mandatory opinion. Keep
implementation simple enough to leave room for content. Host usage records are
observations, not quality scores or acceptance gates. Never pad reading or wait to
reach a ratio; code and passive rendering are not content work.

Keep useful evidence and uncertainties in source-notes.md. Distinguish source facts,
quotations, interpretation and illustrative examples. No invented data/citations.
Respect supplied-only/offline instructions.

Read [Workflow branches](references/workflow-branches.md) and
[the choice catalog](assets/workflow-choices.json). Select explicit task branches
for the existing create/edit entry, viewing, research, references, style, palette
and typography; select each
page's intent, eligible primary/support forms, composition, density, behavior and
asset route. Record decision-plan.json with exact outline IDs/order and a short
observable role per page. No unspecified option, invented category or "consider X"
in place of selection. Execute the selected route's actions and failure alternative.
Creative composition within a route still follows the actual content and purpose.

Run scripts/workflow_decisions.py --stage planning before finishing the plan, and
--stage authored --artifact YOUR_EXPORT before finishing native authoring. New
multi-page decks cannot select one form/composition throughout; actual visual
review checks that differences are meaningful. Source/template constraints and
scoped edits preserve the authorized scope. Use
[Research and assets](references/research-and-assets.md) for source inspection and
quality within the selected reference/material route; any relevant art form may
inform that route. No fixed template rotation or demand to use all branches.

## 2. Write page content

Before authoring, write outline.json with overall purpose, sections and each page's
title and substantive explanation/evidence/example. Topic labels are insufficient.
Use natural-language content, not fixed chapters or a compulsory opinion per page.
Include only a short overall style/viewing note.

Use the requested PPT language for slides, public outline, labels and notes; preserve
proper names/code where appropriate. Publish using the host outline helper when
available, then continue without routine sign-off. Synchronize content/order changes.
Public summaries are not internal reasoning or raw source notes.

## 3. Make native pages

Start from the user's PPTX for edits or a supplied blank; bundled fallback is
assets/blank.pptx. Use direct OOXML only. Choose text, charts, tables, diagrams,
images or media for the content and neighboring pages, not a quota. Consult
[Visual review](references/visual-review.md) as practical guidance. Essential text,
data and analytical diagrams remain editable; do not flatten whole slides.

Execute the selected behavior branch: static, click_reveal, internal_navigation
or embedded_playback. Follow its conditions/checks in workflow-branches.md; for
click_reveal, read [Animations](references/animations.md). No implicit animation
from multiple ideas or a website task.

Read [Research and assets](references/research-and-assets.md) for imagery/media and
check actual host capabilities. Inspect and import real assets. Reference evidence
is required for technical structures; crude invented shapes are not a substitute
for a requested illustration. Generated illustration is not documentary evidence.
When the chosen expression uses assets, acquire/inspect/embed them and check their
actual explanatory role, cropping and annotations. Reconsider a provisional plan
if the available material or rendered result changes its suitability. Keep required
analytical content editable; photographic/illustrative assets can be embedded.
Record consequential substitutions or limitations. Neither cards nor images are
a universal substitute for another form.

Build, render and inspect each page; repair defects and publish native previews
where available. Return to content when a visual exposes a missing explanation.
Essential self-reading meaning must be visible without inaccessible notes.

While finalizing the current page's wording and composition, return to targeted
design search when a new question needs it. Apply the reference to the current
content and verify the rendered result, keeping sequential authoring and the
agreed visual direction. Reuse prior findings for equivalent problems.

Deliver a single standalone PPTX. Use native objects, click-controlled builds,
trigger animations, internal slide links and embedded media. Do not create Content
Add-ins, JSON browser scenes, runnable code labs, local servers, runtime bundles,
installers, macros, external website controls or externally linked media. Present
code as editable explanatory text. Keep essential content readable in PowerPoint.

In a resumable host workflow, inspect restored artifacts before continuing. Respect
ordered user corrections supplied by the host and answer live chat. Refresh affected
outline, scenes, captures and exports after a correction; prior reviews certify only
their recorded input/artifact version. Preserve earlier exports and original inputs.

## 4. Independent audience reviews and revision

Use two fresh reviewer contexts, not the author's conversation: host orchestration
or independent subagents with no inherited history. Give only required artifacts and
the relevant review reference. Reviewers do not edit the deck. If independence is
unavailable, disclose it; self-critique cannot be labeled independent.

- [Content review](references/content-review.md): first the audience surface without
  the author's outline/rationale, then the original brief and sources.
- [Visual review](references/visual-review.md): actual full-size pages, sequence,
  typography, imagery, density, theme, staged reveals and media.

[Observed examples](references/review-examples.md) clarify failures, not required layouts.
Record findings/resolutions in review.md with reviewer and reviewed hash/version.
Fix factual errors, essential omissions, broken explanation, unreadability and
required-media failures. Style suggestions may be retained with reasons. Recheck
revisions, context and final order. No finding quotas or repeated taste-score loops.
Static render/timing inspection is not playback verification. Report exactly what
was tested; do not silently downgrade an essential requirement and declare completion.
For image recreation and scoped edits, evaluate fidelity and authorized changes.
Inherited source ambiguities and unrelated improvements are suggestions, not
delivery blockers. Content and visual reviews can run independently in parallel;
source conversion can compare directly with the original without a blind pass.

## Native operations

Plan content and layout together in source-notes.md, then author in page order.
Record the takeaway, evidence, must-preserve qualifiers/units/operation order,
visual hierarchy and suitable arrangement. Keep this compact and internal;
no separate design stage or pilot pages are required. Preserve source meaning
when simplifying visuals. Name movable semantic groups and use anchored native
connectors for linked nodes; see groups.md and scripts/native_structure.py.
The review packet adds 900-pixel reading previews and factual structure inventory.
Check formulas, labels, captions, wrapping and collisions at that scale as well
as full size. Concrete defects require correction; taste preferences remain
suggestions.

1. Unpack using scripts/pptx.py and retain its workspace path.
2. Put --workspace PATH before commands: list slides, inspect N, find TEXT, refs PART.
   Page numbers follow presentation order.
3. Edit XML within scope; preserve untouched parts, IDs, extensions and media.
   Never overwrite the user's source or original.pptx.
4. Validate, render N, open the returned image, repair and rerender. Snapshot risky
   changes; use diff to check scope and rollback for recovery.
5. Deliver only the returned export path. Export validates/renders the package;
   it does not certify understanding, aesthetics or untested playback.

Workspace files are authoritative. Existing hooks protect originals and validate
changes. Add no aesthetic scores, mandatory wording gates or review Stop loops.

Read technical references only as needed:
[package](references/ooxml-overview.md), [shapes](references/slides-and-shapes.md),
[text](references/text.md), [images](references/images.md), [charts](references/charts.md),
[groups](references/groups.md), [masters](references/masters-and-layouts.md),
[relationships](references/relationships.md), [safe changes](references/safe-mutation-rules.md),
[formulas](references/technical/formula-fidelity.md),
[advanced objects](references/technical/native-capabilities.md).
