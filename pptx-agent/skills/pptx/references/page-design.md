# Page tasks and page context

## Page task block (in source-notes.md)

For a page with real material or a non-obvious visual task, write one fenced block.
`page_id` is the outline ID; other fields are optional.

```pptx-handoff
{
  "page_id": "attention-example",
  "question": "How does the current position combine information from other positions?",
  "evidence": [{"source": "references/paper.pdf", "locator": "Section/figure", "claim": "The supported mechanism and its conditions"}],
  "materials": [{"file": "assets/attention-reference.png", "role": "Inspected detail useful for this explanation"}],
  "preserve": ["Illustrative weights are not reported measurements"],
  "uncertainties": ["Exact example values still need checking"],
  "visual_opportunity": "Main visual: one worked example aligning the current position's weights with their source values and the resulting combination; reveal the combination after its inputs. Finished when the audience can trace which values contribute."
}
```

A prose heading is not a block. planning_commit returns `page_task_projection`
showing which page IDs were recorded; fix a missing block there. The host passes these
tasks to the author and to the visual reviewer (never to the blind content pass).
`page_design.py brief --task-root TASK` prints the projection.

## Page context while authoring

```sh
HOST_PYTHON PLUGIN/skills/pptx/scripts/page_design.py context --task-root TASK --page-id ACTUAL_ID --workspace PARTS_DIR
```

(or the host tool `pptx_page_design_context`). It returns the page's task and evidence,
its materials as images, the native object index, `layout_checks` clues (off-slide,
overlapping text, tiny or crammed text, a line through text, text across the edge of
a filled area) and, after `render N`, the current render.
Render and inspect after each batch of fixes.

## Optional observation record

To keep a consequential decision for later pages or resume:

```json
{"observation": "The relationship was hidden in body text.", "actual_change": "Enlarged the input/output relationship, removed duplicate text.", "preserve": ["Original labels"], "outcome": "changed"}
```

```sh
HOST_PYTHON PLUGIN/skills/pptx/scripts/page_design.py record --task-root TASK --page-id ACTUAL_ID --workspace PARTS_DIR --input observation.json
```

`outcome` is `changed`, `retained` or `unresolved`. The helper appends a
`pptx-design-observation` block to source-notes.md.
