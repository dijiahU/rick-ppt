# Workflow branches

Use this routing protocol for planning, authoring, revision and review. The finite
choice IDs live in [workflow-choices.json](../assets/workflow-choices.json); select
those IDs, not an invented category or an unfilled "consider X". Creative treatment
happens within the selected branches. Selection is required; no choice is preselected.
Explicit user requirements, supplied templates, permitted tools and factual fidelity
restrict eligibility. The existing four stages and sequential page order remain.

## 1. Task route

| Decision | Choices and entry conditions | Result |
| --- | --- | --- |
| Task entry | `create`: make a new presentation; `edit`: change a supplied presentation | Copy the existing host task mode. There are no additional input-state task types. Within edit, follow the requested scope; within create, preserve supplied evidence/templates where required. |
| Viewing | `live`, `self_reading`, `dual_use`: explicitly stated or established by supplied use; `unspecified`: evidence does not establish it | Do not invent live use. Essential meaning remains accessible; choose behavior at page level. |
| Research | `supplied_only`: supplied/offline constraints or no permitted search; `targeted_verification`: sources exist but a specific gap/current claim needs checking; `topic_research`: the requested topic needs substantive research | Read the relevant sources; stop when the actual gaps are resolved. Do not repeat a research branch after a geometry fix. |
| Design references | `preserve_supplied`: required source/template style; `use_available`: inspected supplied/task knowledge supports the choice; `targeted_search`: a specific design/material question needs outside reference | Record relevant applications. Search references can come from any relevant art; no compulsory book list. |
| Style system | `editorial`: reading/type hierarchy is central; `analytical`: evidence/relationships dominate; `image_led`: visual recognition/experience dominates; `expressive`: a requested idea/feeling needs artistic treatment; `supplied_system`: source style must be retained | Define concrete type/color/composition for this task within that family. These are systems, not page templates. |
| Palette | `inherited`, `neutral`, `semantic`, `expressive` | Respect source color when required; otherwise select color roles for reading, distinctions or experience. No prescribed colors. |
| Typography | `inherited`, `installed_role_system` | Preserve required source type or assign roles using available fonts. No prescribed font family. |

Missing ordinary material is handled inside its research/asset branch: search,
use supplied material, generate an appropriate concept or qualify an unknown.
There is no mandatory completeness/conflict classification before every task.
Only an explicit required attachment that is absent, or mutually incompatible
mandatory requirements that prevent progress, needs a concrete clarification.
Preserve work in that exceptional case; do not invent facts or repeatedly repair
contradictory assumptions. Host-resolved input is shared by author and reviewer.

## 2. Page route: intent → eligible primary form

Select one intent and one primary form from its catalog branch. Add zero or more
distinct supporting forms from the form menu. Supporting text may accompany any
image/diagram. The primary form describes the main explanatory work, not the title.

| Intent | Eligible primary forms |
| --- | --- |
| `introduce` | typography, documentary_image, original_illustration, worked_example, storyboard |
| `explain` | typography, diagram, worked_example, storyboard, documentary_image, embedded_media |
| `compare` | table, data_chart, diagram, documentary_image, worked_example, typography |
| `quantify` | data_chart, table, worked_example, diagram |
| `show_space` | diagram, documentary_image, original_illustration, storyboard, embedded_media |
| `demonstrate` | worked_example, storyboard, documentary_image, diagram, embedded_media |
| `envision` | original_illustration, documentary_image, typography, storyboard, diagram |
| `summarize` | typography, table, diagram, data_chart, worked_example |
| `sequence` | diagram, storyboard, worked_example, table, embedded_media |
| `decide` | table, data_chart, diagram, worked_example, typography |

The intent identifies the reader's task: recognition, understanding, comparison,
quantity, spatial relationships, actual use, a proposed vision, synthesis, ordered
progression or a decision. Choose from that branch according to evidence and use.
Real-product demonstration and documentary imagery require real sources; generation
can express an original vision but cannot counterfeit an actual screen or case.

Next select a composition family: `focus` (one main field), `split` (complementary
fields), `sequence` (ordered steps), `layered` (nested/overlapping levels), `spatial`
(location/adjacency), `comparison` (shared dimensions), or `multipanel` (related
examples/views). Choose density `sparse`, `balanced` or `dense` for this content and
viewing distance; these labels do not impose a word count or object count.

For new multi-page decks and requested whole-deck redesigns, the complete plan must not use one primary-form/
composition pair throughout. The local validator catches that omission; actual
visual review checks that variation is meaningful, not just changed labels/colors.
Related comparisons keep consistent encoding. Preserve supplied templates and
bounded edits; do not mechanically rotate all menu items.

## 3. Asset route, selected for each material need

| Route | Condition | Required action / fallback |
| --- | --- | --- |
| `none` | Selected native text/data/diagram explains the page without an external bitmap/media asset | Record the explicit route; it cannot be combined with another asset route. |
| `supplied` | Suitable material is in the authorized inputs | Inspect it and embed the selected bytes with attribution/context. |
| `web_import` | Real or reusable material is needed and a permitted source is available | Search/open/inspect; acquire via WEB-MEDIA.md; inspect and embed the local file. A search thumbnail is not acquisition. |
| `generate` | An original raster concept/illustration serves the page and the built-in tool is exposed | Use imagegen-skill.md; inspect the task-local result; embed and label it illustrative. No failed-search prerequisite. |
| `source_grounded_native` | A faithful analytical/technical schematic is the selected expression | Read the evidence and draw native editable relationships; do not pretend it is a real photo/screenshot. |

File routes also select `kind`: `documentary`, `illustrative`, or `media`, and
`status`: `planned`, `ready`, or `unavailable`. Before author completion, selected
file assets must be `ready`, with a task-relative `file` and an `origin` source/credit
or generation reference. When normalizing/converting, record the actual file bytes
that are embedded. The host checks use on the planned page, not merely existence
in the task directory or unused placement under ppt/media.

If acquisition/generation fails, select a supported alternative route/form and
update the plan, keeping the actual limitation in source notes. If a requested
essential visual cannot be met, report that unresolved requirement; do not declare
a placeholder complete. Explicit offline/supplied-only/no-generation constraints
and tool availability remove ineligible routes. No API/install/permission fallback.

## 4. Behavior route

| Choice | Entry condition | Execution/check |
| --- | --- | --- |
| `static` | A complete view serves reading/comparison or interaction is unnecessary | Keep the page complete and readable. |
| `click_reveal` | Requested/appropriate stepwise explanation benefits from presenter control | Use animations.md; reveal related objects together and inspect states/targets. |
| `internal_navigation` | The task needs nonlinear movement within this deck | Use native internal slide links; verify destinations. |
| `embedded_playback` | An explanation needs an actual embedded clip/audio | Select embedded_media and embed the actual file; distinguish static inspection from target-player playback. |

Multiple ideas alone do not select animation. External sites/runtimes are not a
delivery branch. Unsupported essential behavior is reported, never simulated as
verified playback.

## 5. Execution / review / repair routes

| Observed result | Route and next action |
| --- | --- |
| Plan incomplete, unknown choice, incompatible intent/form or stale page IDs | Correct decision-plan.json locally before native authoring; do not invent a fallback choice. |
| Render unreadable, clipped, incorrect crop/group/connector/timing, or chosen material absent | Repair the affected native page/asset; rerender that page and refresh its preview. |
| Source facts, explanation, required example or operation order wrong/missing | Re-enter the affected content branch, then implement its native correction. |
| Native package validation fails | Fix the package/native operation using the actual error, preserving original and previous exports. |
| Draft ready | Freeze/validate/render; independent content and visual contexts review that exact candidate in parallel. |
| Review finding needs new facts/explanation | Select finding route `content_revision`. |
| Review finding needs implementation only (layout, fonts, captions, asset placement, native behavior) | Select `native_repair`; do not start a full content-research pass. |
| Optional refinement or inherited out-of-scope issue | Select `retain_suggestion`; it does not block delivery. |
| User chat only | Answer in the existing separate chat path; preserve the frozen review. |
| Actual user modification | Update affected choices/content/native pages and review the new candidate. |
| Temporary transport error, bytes/revision unchanged | Use existing bounded retry/checkpoint recovery; retain candidate and receipts, do not regenerate. |
| User stop | Stop active work through the existing stop path and retain checkpoints. |
| Reviewed hash/revision matches delivery input | Upload those exact standalone PPTX bytes. |
| Hash/revision changed or required correction unresolved | Return to the affected correction/review branch; never upload as reviewed. |

Repair routes do not create extra reviewers or unlimited loops; the existing bounded
repair budget remains. Conflicting requirements must be resolved as input, not hidden
by repeated content/native repairs. Reviewer context excludes the author's decision
rationale. Review actual pages and the request using the same branch criteria.

## Decision record and local checks

Write task-local decision-plan.json beside outline.json, with root keys version,
task and pages. Copy the task fields and their IDs from the
catalog. Each page has `id`, `intent`, `form`, `support` (array), `layout`, `density`,
`behavior`, `assets` (array), and a short observable `role`; IDs/order match outline.
Each file asset has route/kind/status/file/origin; a no-file route is just
`{"route":"none"}` or `{"route":"source_grounded_native"}`. This is a concise
execution record, not private reasoning or a public outline replacement.
After writing outline.json, the checker can emit an unselected scaffold with the
exact page IDs: use --template and save its output as decision-plan.json. Null
values are deliberately unselected and invalid until filled from the catalog.

Example page (not a prescribed layout):

```json
{"id":"space","intent":"show_space","form":"diagram","support":["typography"],"layout":"spatial","density":"balanced","behavior":"static","assets":[{"route":"source_grounded_native"}],"role":"Show which functions share a circulation spine."}
```

Run with the provided interpreter and plugin path:

```
python PLUGIN/skills/pptx/scripts/workflow_decisions.py --stage planning
python PLUGIN/skills/pptx/scripts/workflow_decisions.py --stage authored --artifact exports/final.pptx
```

The host repeats these structural checks before accepting new planning/author output
and before frozen review. It rejects missing/invalid choices and missing selected
asset/native behavior. These checks do not certify aesthetics, factual provenance
or playback; existing audience reviews still do. Old verified exports/recovery
receipts without a decision record retain their existing recovery path.
