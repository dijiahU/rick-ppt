# Current tool preparation

The host can prepare `tool-quickstart.md` and `tool-manifest.json` in the task root.
Read the quickstart for exact executable commands, then only the needed manifest
sections. These describe the installed tools; they do not choose content, design,
references, branch values or a page template, and do not replace SKILL requirements.
When the host includes complete current documents in a phase's initial prompt,
use that reading directly. Read only deferred/changed files and needed detail;
do not reopen the same instructions or print every manifest section for discovery.
Original source/visual attachments still require actual inspection.

The planning interface supports one combined `planning_commit` submission instead
of separate scaffold generation and three-file writes. The native `ensure_next_page`
interface safely appends a blank page from an explicitly selected existing layout
or returns the existing page on retry; it never clones source content or chooses
style. See [planning-commit.md](planning-commit.md) and [native-pages.md](native-pages.md).

Use the exact interpreter path in `tool-manifest.json.python` for scripts and
inline patches. Keep its venv invocation path even if it is a symlink; do not
substitute bare python/python3 or resolve it into a system binary.

If the host has not prepared the files, replace `HOST_PYTHON` below with the exact
provided interpreter and `PLUGIN` with the exposed plugin path:

```
HOST_PYTHON PLUGIN/skills/pptx/scripts/tool_prepare.py --task-root . --python HOST_PYTHON
```

Choose the task-appropriate original or blank source yourself and unpack it using
the quickstart command. Refresh preparation with `--workspace RETURNED_PATH` after
unpacking or recovery. The manifest then supplies actual `session_dir` and
`parts_dir`: pptx/native_builds accept either; native_canvas/design_references need
the parts directory. No source is automatically unpacked or authored by this tool.

The manifest reads current CLI parsers, native_canvas function signatures and
decision options. With an existing outline it includes the existing unselected
decision scaffold. Preserve explicit delivery decisions, source meaning and actual
reference inspection. A local reference `source` is its exact task-relative file
path without a provenance label; record display attribution in title/observed.
Fill observed/borrowed/applications only after inspecting the material.

Script operations can partially complete before a later call fails. Inspect the
saved objects or restore the snapshot before retrying; use returned handles and
existing IDs rather than appending hardcoded duplicate IDs. Tool preparation does
not certify the page, replace independent review or change frozen delivery rules.
