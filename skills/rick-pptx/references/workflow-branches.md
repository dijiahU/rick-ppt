# Delivery decisions (v4)

assets/workflow-choices.json holds the technical routing values. Design is written
in natural language and judged on the rendered pages.

## decision-plan.json

```json
{
  "version": 4,
  "task": {"operation": "create", "viewing": "live", "research": "targeted_verification"},
  "template_preservation": ["Keep supplied background and school logo; reserve logo area"],
  "design_direction": "Short deck-wide direction: palette, type, image treatment, motif and why.",
  "references": [],
  "pages": [
    {"id": "method", "behavior": "click_reveal", "assets": [{"route": "source_grounded_native"}]}
  ]
}
```

- `task.operation`: the host's create/edit entry. Pages use the exact outline IDs
  and order.
- `viewing`: live, self_reading, dual_use or unspecified.
- `research`: supplied_only, targeted_verification or topic_research (supplied_only
  when no search is available).
- `template_preservation`: protected source elements and edit scope; [] without a
  template.
- `design_direction`: one compact provisional direction; update it when renders show
  a better one.

## Behavior and assets

`behavior`: static, click_reveal, internal_navigation or embedded_playback. New decks
need meaningful click reveals (entry state, click groups and final view noted in
source notes); covers and single-message pages can be static.

`assets` per page: `none` and `source_grounded_native` contain only `route`. File
routes supplied, web_import and generate use kind (documentary, illustrative, media),
status (planned, ready, unavailable), file and origin:

```json
{"route":"web_import","kind":"documentary","status":"planned","file":null,"origin":"Source URL or material to acquire"}
```

Planned material can stay pending during planning. Before the authored check, chosen
files must be ready, task-scoped and embedded on their page. Generated assets are
illustrative.

## References (written once)

```json
{"id":"R1","kind":"artwork","title":"Exact work title","creator":"Verified creator",
 "source":"https://original.source/work","inspection":"local_image","evidence":"references/work.png",
 "observed":"What is visible","borrowed":"Useful visual relationship",
 "applications":[{"pages":["method"],"action":"Concrete adaptation on this page"}]}
```

Kinds: artwork, design_work, teaching, supplied_system. Inspection: local_image,
hosted_visual, read_text or unavailable (then evidence=null, borrowed=null,
applications=[]). Artwork/design_work applications need actual visual inspection.
`source` is an exact credential-free HTTPS URL or task-relative file. Record applied
works and their page associations in the `decision-plan.json` `references` register.
Record only works you actually looked at. Speaker notes contain only the speech script.

## Checks

planning_commit (or workflow_decisions.py --stage planning), then
workflow_decisions.py --stage authored --artifact YOUR_EXPORT. They check page order,
capability, provenance, embedded files, notes and native behavior, not design
quality. Historical v1–v3 records stay readable with --allow-legacy.
