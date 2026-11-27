---
name: pptx
description: Research, create and edit standalone native PowerPoint with editable content, native animation, actual rendering and independent reviews.
---

# Native PowerPoint

Use scripts/pptx.py with the exact Python interpreter in tool-manifest.json. Paths
are relative to this skill. tool-quickstart.md lists the tool groups; open only the
ones you need with tool_prepare.py --group GROUP_ID.

## Pipeline

1. **Research** ([content](references/content.md)): understand purpose, audience,
   language and supplied material; search facts, real cases, usable images and
   finished visual work; write source-notes.md and outline.json (stable id, title,
   substantive summary per slide, including the relationship the page must show).
   Planning fixes each page's point and relationship and checks whole-template fit.
   Commit outline, decisions and notes with
   [planning_commit](references/planning-commit.md). The v4 decision-plan.json
   format is in [delivery decisions](references/workflow-branches.md).
2. **Design** ([art direction](references/art-direction.md)): look at real decks of the
   same genre, pick the register (restrained, standard, expressive, celebratory) and write
   deck-style.json before page 1; use its @colour tokens for new designs and keep
   template colours on retained pages.
3. **Author**: build native pages in order from assets/blank.pptx, a supplied template,
   or an editable library template fetched with `action=template`. Follow the
   [template paths](references/content.md). Fill base pages in place, build new pages
   on template masters, or study a source page and sketch a new composition. Follow the [art direction](references/art-direction.md) for page search, sketches and render checks before moving on, and [borrowing](references/borrowing.md) with [poster thinking](references/poster-thinking.md) before designing any key page: the deck is a sequence, each key page is a poster. Tools:
   [native batches](references/native-batch.md), [native canvas](references/native-canvas.md),
   [native pages](references/native-pages.md), [image recreation](references/image-recreation.md).
4. **Animate** ([animations](references/animations.md)): new decks use native click
   reveals for multi-step content; covers and single-message pages can be static.
5. **Save**: run design_references.py --workspace PARTS_DIR, then
   `scripts/candidate_save.py --task-root TASK_DIR --workspace PARTS_DIR --output exports/VERSION.pptx`
   (renders, runs the authored check, updates delivery.json).
6. **Review and repair**: the host runs independent [content](references/content-review.md)
   and [visual](references/visual-review.md) reviews against
   [design completion](references/design-completion.md). Repair assigned findings and
   save a fresh export each round.

## Boundaries

- One standalone PPTX. Text, diagrams, charts, formulas and animation stay native and
  editable. No add-ins, macros, browser scenes, runnable code, local servers or
  external media dependencies.
- Keep source facts, units, symbols, conditions and operation order. Separate
  reported results, interpretation, suggestions and illustrative examples. Real
  interfaces, historical subjects and case evidence need authentic sources; generated
  images are labelled illustrative. Acquisition rules: [research and assets](references/research-and-assets.md).
- Fonts: choice is open. Pick families for the language (Japanese text in a Japanese
  face, never SimSun), register and requested style, install the actual file into the
  task so previews match, and list every family used in the completion summary. The
  default pair (Times New Roman / SimSun, DengXian / Arial for display) applies when
  nothing argues otherwise. See [fonts](references/fonts.md).
- Respect supplied-only/offline instructions and the scope of an edit. Preserve
  original files and earlier exports.
- Use the requested language for slides and notes; keep proper names and code.

## Continuity

One author conversation owns research, design, pages and repairs; independent
reviews run in separate contexts. On resume inspect retained pages, exports, sources
and receipts before redoing work ([execution continuity](references/execution-continuity.md)).

## Technical references

Unpack with scripts/pptx.py and keep the workspace path. Put --workspace before
list slides / inspect N / render N / export. Snapshot before risky changes. Preserve
IDs, relationships and untouched source parts. [Tool preparation](references/tool-preparation.md)
explains host refresh. As needed: [package](references/ooxml-overview.md),
[shapes](references/slides-and-shapes.md), [text](references/text.md),
[images](references/images.md), [charts](references/charts.md),
[groups/connectors](references/groups.md), [masters](references/masters-and-layouts.md),
[relationships](references/relationships.md), [safe changes](references/safe-mutation-rules.md),
[formulas](references/technical/formula-fidelity.md),
[advanced objects](references/technical/native-capabilities.md).
