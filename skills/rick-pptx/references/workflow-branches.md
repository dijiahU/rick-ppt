# Delivery decisions and open design (v4)

The catalog in assets/workflow-choices.json contains technical routing values.
Design is described in natural language and judged on actual pages. Composition,
style, palette, visual form and strategy are not mandatory categorical selections.

## Compact decision-plan.json

```json
{
  "version": 4,
  "task": {"operation": "create", "viewing": "live", "research": "targeted_verification"},
  "template_preservation": ["Keep supplied background and school logo; reserve logo area"],
  "design_direction": "A scientific explanation with inspectable mechanisms and consistent comparison encoding; body composition remains open.",
  "references": [],
  "pages": [
    {"id": "method", "behavior": "click_reveal", "assets": [{"route": "source_grounded_native"}]}
  ]
}
```

Use the host's existing `create`/`edit` entry and exact outline page IDs/order.
`viewing`: live, self_reading, dual_use or unspecified.
`research`: supplied_only, targeted_verification or topic_research for the factual
investigation. Respect user source limits. With no search capability use supplied_only.
Relevant design discovery is independent of the factual route and of template
protection, subject to actual offline/supplied-only permissions.

`template_preservation` names actual protected source elements/style and edit scope;
use [] without a template. It does not force inherited body composition or prevent
outside inspiration. `design_direction` is one compact, provisional coherent premise.
Revise it when actual assets or rendered pages demonstrate a better expression;
planning validation establishes execution consistency, not aesthetic endorsement.
Preserve actual user/source constraints and synchronize affected asset/behavior
records when the expression changes; no new design status field is required. Page role,
visual_action, intent, strategy, form, support and composition may optionally be
free descriptions; none is required or checked against a design taxonomy.

## Page behavior and assets

Behavior is static, click_reveal, internal_navigation or embedded_playback.
New presentations require meaningful native click reveals, with entry context,
semantic click units, persistent orientation and a complete final view recorded in
source notes. Static covers/single-message pages are allowed. Preserve scoped edit,
faithful-source and historically admitted behavior. Final checks inspect native
entrance targets, links and media; static checks cannot certify target playback.

Each page records its selected assets. `none` and `source_grounded_native` contain
only route. File routes supplied/web_import/generate use kind (documentary,
illustrative, media), status (planned, ready, unavailable), file and origin:

```json
{"route":"web_import","kind":"documentary","status":"planned","file":null,"origin":"Actual source URL or material still to acquire"}
```

Planning can retain pending material. Before authored completion, selected files
must be ready, task-scoped and embedded on the correct page; media must actually
have a playable relationship. Generate requires an available generation tool and
an illustrative role. Acquire/inspect/embed through permitted paths, update choices
when the actual material warrants another expression, and disclose unmet explicit
requirements. See research-and-assets.md for authenticity and failure handling.

## Reference record, written once

Record only actually inspected works/teaching and honest failed access:

```json
{"id":"R1","kind":"artwork","title":"Exact work title","creator":"Verified creator",
 "source":"https://original.source/work","inspection":"local_image","evidence":"references/work.png",
 "observed":"What is actually visible","borrowed":"Useful visual relationship",
 "applications":[{"pages":["method"],"action":"Concrete adaptation to the current subject"}]}
```

Kinds: artwork, design_work, teaching, supplied_system. Inspection: local_image,
hosted_visual, read_text or unavailable. Artwork/design_work applications require
actual visual inspection; text about a painting is not that inspection. Unknown
attribution must be stated honestly. Unavailable entries use evidence=null,
borrowed=null, applications=[]. Source is an exact credential-free HTTPS URL or
task-relative file, not a human-readable label. Viewing does not grant embedding
rights or establish project facts.

Application page IDs are the single source of page associations in v4. The helper
derives page reference IDs and writes affected slide notes from this register:
`design_references.py --workspace PARTS_DIR`. Existing notes are retained. If optional
page reference_ids are supplied they must match derived applications. No outside
artwork is required for every task; never invent influence. Briefly identify actual
applied work/ideas in the completion summary, or honestly report none.

Run workflow_decisions.py --stage planning (or planning_commit once when available),
then --stage authored --artifact YOUR_EXPORT on the exact candidate. Checks cover
page/order, capability, provenance, chosen bytes/notes and native behavior. They do
not require categorical layout diversity or certify design quality. Existing visual
review judges actual style fit, expression, coherence, sequence and reference transfer.
Facts, explicit requirements and demonstrated comprehension/readability defects can
require repair; artistic alternatives remain concrete suggestions. Preserve bounded
repair, user stop, chat/revision separation and frozen-hash delivery.

Previously admitted v1–v3 records remain readable using their original contracts.
New tasks use v4; --allow-legacy is only for historical recovery. Do not rewrite
historical plans, reviewed bytes or receipts just to update the schema.
