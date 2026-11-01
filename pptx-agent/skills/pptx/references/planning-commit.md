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
  "decisions": {"version": 4, "task": {}, "template_preservation": [], "design_direction": "...", "references": [], "pages": []},
  "source_notes": "# Source notes\n\nOriginal Markdown evidence, qualifications, design applications and native build plan.\n"
}
```

The decisions object uses the compact v4 delivery contract in
[workflow-branches.md](workflow-branches.md): exact task/page IDs, protected template
elements, behavior, assets and actual reference applications. Composition/style are
open author choices, not mandatory design categories. `outline.slides` is the
ordered page array; `pages` is not an outline alias.

If research notes already exist, replace `source_notes` with
`"source_notes_file": "source-notes.md"` (or another existing task-local Markdown
file). Supply exactly one of these keys. The tool snapshots the UTF-8 file for
the submission, preserves its exact bytes including line endings, and returns
its path/hash in `source_notes_input`. It checks that the source has not changed
before committing. Missing, oversized, empty, non-UTF-8, external or symlink files
are rejected without replacing outputs. This avoids retyping accumulated research
inside JSON; it does not summarize or discard evidence. The original inline form
remains supported.

Keep reader-facing page summaries in the outline, evidence/details and native
build plans in source notes, and reference applications in the decision register.
Use exact source/page/section pointers where the same detail is needed elsewhere;
do not copy whole sections into all three files. Preserve substantive summaries,
source qualifiers and useful examples; no text-length or research quota is imposed.

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
