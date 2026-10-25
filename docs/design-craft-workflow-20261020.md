# Design craft workflow update · 2026-10-20

Version: `0.1.0+codex.20261020designcraft`.

The approved 15-page historical-document redesign exposed a gap between a correct,
readable deck and an immediately usable editorial presentation. The adopted changes
move concrete design judgments into ordinary authoring and retain independent
review for omissions. They do not introduce a new stage or quality score.

## Behavior changes

- Planning retains substantive evidence and source invariants, but its visual
  direction is provisional. Existing `role`/`visual_action` identify the actual
  focal object or relation and how the reader will see it. A form label alone is
  insufficient. Final wording and composition are resolved together on the current
  page rather than prewriting equal paragraphs throughout the deck.
- On the first actual render, the main author checks first-glance emphasis,
  perceptible comparisons/changes/dependencies, and the useful role of each image
  and quotation. Concrete weak expression is repaired alongside fit and factual
  checks before moving on. Necessary qualifiers remain readable and close to the
  corresponding claim. There is no new checklist artifact or author approval gate.
- At natural section boundaries the author reuses saved previews to inspect
  opening grammar, density, reading path and rhythm. Repeated title/quote/body
  treatment can flatten a sequence even when the lower diagrams differ. Related
  comparisons retain consistent encoding; there is no fixed layout rotation,
  bigger-headline rule, picture quota or requirement to manufacture a climax.
- The existing visual review evaluates those actual operations. It can report
  a concrete nonblocking editorial suggestion even when factual/readability
  checks pass. Findings identify a page/region, audience effect and feasible
  correction. Required/suggestion boundaries and bounded repair stay unchanged;
  "no required findings" does not automatically establish strong design.

The shared runner research/author/visual prompts, production Skill, portable Skill
overlay and generated installable package are aligned. Both local and API execution
use the shared workflow. The standalone installed `rick-pptx` was synchronized.
No schema fields, phase ordering, model selection, billing, delivery policy or
website UI were changed. Historical PPTX bytes and review receipts are preserved.

## Verification

- Content workflow: 12 tests passed.
- Independent review sessions/recovery: 47 tests passed.
- Prepared phase contexts: 13 tests passed.
- Review-material isolation: 10 tests passed.
- Tool preparation: 15 tests passed.
- Production bridge/runtime selection: 10 tests passed (107 targeted tests total).
- Skill format validation and environment doctor passed.
- Portable package: 55 files; all 54 source-input hashes and every ZIP entry
  matched the generated source. ZIP SHA-256:
  `dd8d7c9b3e1fa2754f9d7777f99b140743c10d88780765f48daec7c26ca14607`.
- Immutable runtime staging passed journal/recovery, outside-read denial,
  network-denial and permitted-task-write self-tests. Worker receipt confirmed
  the new version ready after a graceful handoff; no running task was cancelled.

`test-workflow-policy.py` has two pre-existing failing cases. Re-executing that
suite with the unmodified HEAD workflow reproduced the same failures: the old
hyperlink-rejection expectation and a scoped-review fixture returning no
content-first report to the public-review publisher. These were not changed or
represented as passing. This update does not claim a clean full-repository suite.

The user-approved local redesign supports these chosen operations, not a claim
that every model now reliably produces equivalent aesthetics. No additional paid
model run was initiated for this prompt/reference update. Actual Windows WPS or
PowerPoint slideshow interoperability is separate from static/rendering evidence.
