# Submit a complete planning bundle in one call

Write one task-local JSON file, such as `planning-input.json`:

```json
{
  "version": 1,
  "outline": {
    "title": "Reader-facing deck title",
    "purpose": "What this audience should understand or do",
    "style": "Optional description of the actual visual direction",
    "slides": [
      {"id": "page-1", "title": "Page title", "summary": "Substantive public explanation", "section": "Optional section"}
    ]
  },
  "decisions": {"version": 3, "task": {}, "design_direction": "...", "references": [], "pages": []},
  "source_notes": "# Source notes\n\nOriginal Markdown evidence, qualifications, design applications and native build plan.\n"
}
```

The `decisions` above only illustrates nesting; `{}` and `[]` are **not valid
completed decisions**. Supply the full existing v3 task, page and reference fields,
with every applicable branch chosen by the author. Use the exact task/page IDs
from the prepared planning context/catalog and [workflow-branches.md](workflow-branches.md).
There are no inferred choices or new planning categories. `outline.slides` is the
ordered page array; `pages` is not an outline alias.

Run the prepared interpreter invocation once:

```text
HOST_PYTHON PLUGIN/skills/pptx/scripts/planning_commit.py --task-root TASK --input planning-input.json --mode create --expected-pages 5
```

Use `--mode edit` for the existing edit entry. Page-count checking is optional when
the task has no fixed total. The current complete outline contract also supports
page `presentationMode` and `interaction` metadata and an existing `revision`;
this helper preserves them. It does not authorize interactive add-ins or change
the standalone native delivery policy. Public outline text must remain free of
local paths, private logs and credentials.

The tool checks bounded JSON (including duplicate keys and nonfinite numbers),
current outline text/IDs/count, then calls the existing
`workflow_decisions.validate_plan(..., stage='planning')`. An error returns
`{"ok":false,"error":"..."}` with exit status 1. Correct the specific rejected
field in the same bundle and rerun; do not repeat research for a formatting error.
This consolidates existing planning checks; it adds no review stage or aesthetic
score and does not certify facts, reference authenticity or final page quality.
The host still validates current capabilities and the admitted contract.

On success, it writes `outline.json`, `decision-plan.json` and `source-notes.md`
only after all checks pass. JSON values, ordering and authored text remain intact
(serialization whitespace can change); Markdown is written exactly as supplied,
including its final newline or lack of one. No branch selection, normalization,
auto-repair or historical schema migration is written. Existing output files are
intentionally replaced as one submission, retaining permissions and restoring the
original bytes on a handled commit failure. The input bundle remains unchanged.
The result lists output hashes, sizes and whether each file replaced an old file.
Do not run simultaneous writers against these three files.

Input and outputs must be regular task-local files with no symlink paths. Use the
real task-directory path. Limits: outline 2 MiB, decisions 512 KiB, source notes
2 MiB; the combined input has a small JSON-escaping overhead allowance. CLI errors
leave existing outputs untouched. If rollback itself encounters a disk failure,
the tool reports the preserved backup directory instead of deleting its originals.

`--allow-legacy` is reserved for an explicitly admitted historical contract. It
allows the existing validator's historical compatibility behavior, including a
previously admitted static contract, while preserving the submitted original
record. Never set it to bypass requirements on a new task.

After success, publish the outline with the existing host publisher. Do not create
a separate scaffold or rerun the planning validator just to duplicate this result.
Actual authoring, authored artifact checks, renders and independent reviews remain
in their existing workflow.
