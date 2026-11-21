# Tool preparation

<!-- tool-groups/v1 -->

The prepared manifest's `discovery.groups` lists scenario folders and `open_command`
opens one: plan, recreate, compose, images, edit, animate, fonts or verify. Open what
the page needs (for example `images` and `compose` for original design, `recreate` for
image recreation). `tool_prepare.py --task-root TASK --list-groups` / `--group NAME`
are read-only lookups. The complete tool-manifest.json remains available.

Always use the exact interpreter in `tool-manifest.json.python` (keep its venv path;
not bare python/python3). Without host preparation run:

```
HOST_PYTHON SKILL_ROOT/scripts/tool_prepare.py --task-root . --python HOST_PYTHON
```

Unpack your chosen blank/template, then refresh with `--workspace RETURNED_PATH` to
get `session_dir` and `parts_dir` (native_canvas and design_references need the parts
directory). `planning_commit` submits outline, decisions and notes in one call;
`ensure_next_page` appends a blank page from a chosen layout (see planning-commit.md,
native-pages.md).

A script can partially complete before failing: inspect saved objects or restore the
snapshot before retrying, and use returned handles instead of hard-coded IDs.
