# Sequential native pages

Use `native_pages.py` when the next authored page does not exist yet. Choose an
existing native layout explicitly, either by package part or by an existing page
whose layout you want to use. The tool creates one empty-content page and retains
the layout → master → theme relationship chain. It chooses no geometry, colors,
typography, content or composition. Continue authoring pages in presentation order.

```sh
HOST_PYTHON "$SKILL_ROOT/scripts/native_pages.py" \
  --task-root "$TASK" --workspace "$TASK/projects/blank/workspace" \
  --page 2 --source-slide 1 --key page-2 --mode blank_from_layout
```

Replace `HOST_PYTHON` with the exact interpreter from `tool-quickstart.md`.
`--layout ppt/slideLayouts/slideLayout7.xml` is the explicit alternative to
`--source-slide 1`. Select the actual inspected template layout for the page.

The stable `--key` binds the exact request and actual page identity. Repeating it
returns the same page even after authoring its contents or appending later pages.
It never appends the page again. A different request under that key, a disappeared
page, or changed identity/layout is rejected. Requesting an existing page returns
it intact if its layout matches; no existing objects are cleared. Appending is
limited to `current_page_count + 1`; skipped pages are rejected.

This operation is **not a slide clone**. `blank_from_layout` preserves the selected
layout, master and theme, including inherited template appearance. It does not
copy the source page's own objects, backgrounds, notes, charts, media or animation.
For faithful scoped edits, edit the existing page through the established native
path. The original PowerPoint remains protected. Package writes, state refresh and
the operation receipt commit together with rollback on failure. Real rendering,
native behavior checks and independent reviews remain required.
