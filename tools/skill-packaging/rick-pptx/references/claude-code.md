# Claude Code route

Claude Code loads this folder as a skill from `~/.claude/skills/rick-pptx/`
(personal) or `PROJECT/.claude/skills/rick-pptx/` (project). `agents/openai.yaml`
is Codex metadata and is ignored here. The managed DSH engine is not started:
this Claude Code session is the single continuing author and runs the core
helpers itself. Everything else in SKILL.md (delivery boundaries, sequential
authoring, render-view-revise, independent reviews, frozen delivery) applies.

## Bootstrap a task

Use an absolute, resolved task directory (`pwd -P`), outside the skill folder.
Use one explicit Python 3.11+ interpreter (for example the output of
`command -v python3.11`), then reuse the `python` value recorded in
tool-manifest.json for every later helper call.

```sh
PY=/absolute/python3.11; S=SKILL_ROOT/scripts; T=/absolute/task
$PY $S/doctor.py
$PY $S/font_assets.py --root $T ensure times-new-roman-regular times-new-roman-bold simsun-regular
$PY $S/pptx.py unpack SKILL_ROOT/assets/blank.pptx --base $T/sessions   # or the supplied PPTX
$PY $S/tool_prepare.py --task-root $T --workspace $T/sessions/NAME/workspace
$PY $S/tool_prepare.py --task-root $T --group compose                    # open only needed groups
```

Write request.json, outline.json, decision-plan.json and source-notes.md in the
task root as SKILL.md describes. Python helpers can be imported by adding
`SKILL_ROOT/scripts` to `sys.path`; keep your own build scripts outside the task's
downloaded-asset folders.

## Render with the task fonts

On macOS, LibreOffice does not see the task's `fonts/` folder by default and
silently substitutes (SimSun rendered as Arial Unicode MS). Export the
fontconfig file written by font_assets.py in every shell command that renders,
including review_packet.py click-state images (Claude Code shell calls do not
keep variables, so set it in each such command), and check the embedded faces:

```sh
export FONTCONFIG_FILE=$T/fonts.conf
$PY $S/pptx.py --workspace WORKSPACE render > $T/render.json
pdffonts RENDER_DIR/deck.pdf     # expect SimSun / TimesNewRoman, not a fallback
```

A substituted preview cannot be used to judge typography; fix it or report it.

## Host capabilities mapped to Claude Code

| Host term in the guides | Claude Code equivalent |
| --- | --- |
| image channel / view the render | `Read` the exact PNG (slide-N.png, assets, references). A path or a successful render is not viewing. |
| search / browser | `WebSearch` to discover, `WebFetch` to read pages. Download permitted files with `curl` into a new task folder such as `assets/downloads/`, then `Read` the image before choosing it; record source/licence/page role in source-notes.md. |
| image generation | Not built in. Choose sourced imagery or native illustration; set generation routes to unavailable in decision-plan.json and never describe an image as generated. |
| font broker / font-proxy.py | `font_assets.py ensure` for host-installed faces; OFL downloads only with the user's permission. |
| PREFETCH helpers, page-design host context | Not available. Prepare later-page material yourself; `Read` renders and saved previews directly. |
| independent content / visual reviewers | `Agent` subagents (fresh context), one per review, launched in parallel on the same frozen export. |
| host publisher, progress, receipts | Not available. Keep files in the task folder and report the exported path and SHA-256. |

## Independent reviews with subagents

Freeze the candidate (candidate_save.py or export + `shasum -a 256`), then build
packets with review_packet.py. Copy inputs into two separate folders:

- `review-content/`: page images and visible text first, then the original brief
  and sources. No outline, decision plan, source notes, reference register or slide notes.
- `review-visual/`: page images, click-state simulations, the brief, then
  applicable reference images/register entries.

Brief each subagent with the folder path, the frozen SHA-256, the guide to apply
(`SKILL_ROOT/references/content-review.md` or `visual-review.md` with
`design-completion.md`) and the required JSON output. Do not paste your design
rationale or ask them to confirm it. Reviewers do not edit files.

Handle findings through SKILL.md's single bounded repair: change the affected
regions, re-render, `Read` before/after, re-freeze and re-review only changed
bytes. Keep the reviewed baseline when the repair is not better.

## Report

State: Claude Code route (not the managed DSH engine), model actually used,
whether reviews ran in separate subagent contexts, the font check result, and
what remains unverified (PowerPoint/WPS playback, image generation if unused).
