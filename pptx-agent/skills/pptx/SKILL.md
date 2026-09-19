---
name: pptx
description: Research, create and edit native PowerPoint with composable interactive scenes, editable code labs, actual rendering and independent content and visual reviews.
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

For live/dual-use multi-idea explanations, use presenter-controlled native builds
in meaningful groups. Read [Animations](references/animations.md). Preserve context
and introduce information in teaching order. Transitions/all-at-once entrance do
not replace staged explanation. Static briefs, simultaneous comparisons and
single-message pages can remain complete on entry.

Read [Research and assets](references/research-and-assets.md) for imagery/media and
check actual host capabilities. Inspect and import real assets. Reference evidence
is required for technical structures; crude invented shapes are not a substitute
for a requested illustration. Generated illustration is not documentary evidence.

Build, render and inspect each page; repair defects and publish native previews
where available. Return to content when a visual exposes a missing explanation.
Essential self-reading meaning must be visible without inaccessible notes.

For interactive lessons, simulations, editable runnable code or exploratory views,
read [Interactive authoring](references/interactive-authoring.md). Use native OOXML
for the slide and versioned JSON scenes for its Content Add-in regions. Choose
native versus interactive treatment during the outline stage; never replace the
whole deck with screenshots or write a new topic-specific React application.
Use the shared runtime components, state, actions and optional packs. Retain native
titles, context, equations and readable fallback meaning around the live region.
Every scene needs meaningful input/result test assertions and real browser captures.
When the host exposes INTERACTIVE.md, its file broker performs scene rendering
without broadening the author's permissions. Export both the PPTX and its portable
bundle; a PPTX by itself retains static fallbacks but not the complete runtime.

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
Review interactive initial, intermediate, changed-input and reset captures as well
as native pages. Distinguish scene-runtime tests, static PowerPoint fallback and
actual PowerPoint slideshow/settings round-trip verification.

## Native operations

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
