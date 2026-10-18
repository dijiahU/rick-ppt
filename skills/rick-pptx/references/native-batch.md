# Native JSON batch

Use `scripts/native_batch.py` to execute one page's chosen content and geometry
without writing another temporary Python wrapper. Use the exact host interpreter
from `tool-manifest.json.python`. Choose the source and unpack it yourself first.
The batch does not choose a design, create pages, replace source material, or
relax any authoring, publication, rendering or independent-review requirement.

```sh
HOST_PYTHON SKILL_ROOT/scripts/native_batch.py --task-root TASK_ROOT --workspace PARTS_OR_SESSION_DIR --input page-1.json
```

`--check-only` executes the entire batch on a temporary parts copy, returns
measurements/handles, and commits nothing. It is optional; normal execution also
preflights every text object before writing. Make pages in presentation order;
each batch must contain exactly one page number. Publish/self-check that page
as required before moving to the next page. This tool adds objects to an existing
page; it does not silently clear existing shapes or timing.

Input is `{ "version": 1, "batch_id": "page-1-v1", "operations": [...] }`.
Each operation contains `op`, `slide` and the existing helper's parameters.
Object-producing operations also need a unique `id` in this batch. Coordinates,
sizes, colors, names, fonts and image routes are the author's explicit choices.
Parameter names are the exact current `native_canvas` Python API:

| op | Existing helper | Required parameters after op/id/slide |
|---|---|---|
| text | add_text | text,font_file,size,ink,x,y,width,max_height |
| shape | add_shape | box,geometry,fill,stroke,line_width,name |
| image | add_image | source,box,fit,layer |
| connector | add_connector | start,end,points,start_site,end_site,ink,line_width,arrow,name |
| group | semantic_group | members,name |
| reveal | reveal | steps (no object id) |
| bars | add_bar_chart | labels,values,unit,colors,box,font_family,font_size |

Use existing optional helper parameters unchanged: text supports index, padding,
name, latin_font and latin_index; bars accepts `east_asian_font_family` alongside
`font_family` (new default pair: Times New Roman / SimSun); reveal supports explicit `replace: true` only
when replacing timing is authorized. Even a shape with `stroke: null` requires
a positive explicit line_width, such as 1. This preserves the helper contract.

Reference earlier objects by their `id` strings: `"start": "cause"`,
`"members": ["sample", "caption"]`, `"steps": [["sample_group"], ["result"]]`.
Existing object IDs may be positive integers; they must actually identify objects
on this page. Handles cannot refer to another page or a later operation. Group
members must satisfy existing native adjacency/parent rules. Animate a group or
its children, not both. The helper preserves IDs and connector/group/reveal targets.

For text, numeric `max_height` is a strict limit. The preflight reports **all**
text failures with object id, actual `needs_height`, available height, line count
and family. Recompose, shorten or explicitly allocate enough space. It never
shrinks fonts or enlarges a numeric limit. Set `"max_height": "auto"` only when
you intentionally want the selected real font's measured height; this does not
prevent overlaps or guarantee the actual rendered appearance.

Images must be actual files within the task root; relative paths are task-root
relative, and escaping/symlink paths are rejected. Font files must be within
`TASK_ROOT/fonts` or actual system font directories (`/System/Library/Fonts`,
`/Library/Fonts`; Linux system font directories when applicable). Copy/acquire
permitted task fonts into that directory; arbitrary private paths are not accepted.
Choose actual mixed-script faces and weights; bars keep the existing explicit
font-family/font-size contract, with an optional explicit East Asian family.
Asset acquisition and inspection remain required.

All operations run on a complete temporary parts copy, including relationships,
timing, notes, fonts and existing resources. An operation failure discards that
copy. Commit failures roll back the original parts and workspace state. Success
returns stable real-workspace handles, text measurements, exact before/after
parts SHA-256 and a task-local session `native-batches/BATCH_ID.json` receipt.
Rendering and playback are never claimed by this receipt.

Retrying the exact successful batch with unchanged parts/assets returns
`already_applied` and appends nothing. A used batch_id with changed input, changed
asset bytes or intervening edits is rejected; inspect the existing result and use
a new batch_id for intentionally new work. Failed/check-only batches have no
completion receipt. This prevents a failed multi-object script from leaving a
partial page that gets blindly appended on the next model call.
