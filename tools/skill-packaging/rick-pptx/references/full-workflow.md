# Complete workflow on DSH

The full release includes the production authoring engine, every native helper,
planning and design handoff, asynchronous material preparation, separate content
and visual reviews, bounded repair, checkpoint recovery, actual rendering,
version-bound delivery, progress, conversation and native usage receipts.
Website billing, authentication, queue claiming and editor UI are not started.

On an explicitly configured DSH backend, new decks and substantive redesigns
use this managed entry by default, including when the request just says to use
the skill. Scoped edits can use the core helpers. Running tools and manually
calling reviewers is not evidence that the managed engine ran. A different
outer harness must not be silently switched to DSH or a different model.

## Prepare the execution environment

Use Python 3.11+ in a task-independent virtual environment. Install explicitly:

```sh
python -m pip install -r SKILL_ROOT/scripts/requirements-dsh.txt
python SKILL_ROOT/scripts/doctor.py --full
```

The DSH SDK brings its matching runtime; it does not require Codex. Use the full
`sdk` profile, or a custom profile retaining its SDK JSON-RPC service and required
tools. `sdk-minimal` is rejected for complete runs. The selected profile owns its
model, tools, approval policy and sandbox; the package does not assert Codex's
filesystem policy applies to DSH. Do not grant wider tool access merely to make
a task run. Native checks run trusted packaged scripts on task-scoped data.

For DSH skill discovery, put the `rick-pptx` folder under your workspace's
`.dsh/skills/` or `.agents/skills/`. You can also explicitly ask DSH to read this
package's absolute `SKILL.md` path. Installing the skill and installing the SDK
execution environment are separate steps. A pre-existing DSH executable can be
selected with `dsh_bin` / `--dsh-bin`; it must expose the matching SDK protocol.

The full engine currently uses the existing Docker image `pptx-lab-renderer:1`
for frozen, network-isolated rendering. Its tools also need Poppler and genuine
fonts. Core CLI helpers can use installed LibreOffice directly, but that alone
does not satisfy the complete engine's Docker-renderer requirement. Never claim
Windows WPS playback from either renderer. Missing prerequisites must be fixed
or reported; do not skip reviews, animation checks or font requirements.

The image build sources are bundled. On a new machine with Docker installed and
running, explicitly build the renderer; build the media image when normalization
of acquired/generated assets is needed:

```sh
docker build -t pptx-lab-renderer:1 SKILL_ROOT/engine/runner/render-container
docker build -t pptx-lab-media:2 SKILL_ROOT/engine/runner/media-container
```

The complete route has been exercised on macOS. Linux is a portability target,
not a separately verified platform; Windows-native execution is unverified.

DSH model/tool availability comes from the selected profile. A text-only model
needs an explicitly configured image-reading route for image recreation and
visual review. Search and generation must be actual registered tools/services;
no fabricated images, citations or silent operator-account fallback. Missing
services do not justify changing a required source/asset route. Material workers
receive bounded requests, not permission to edit the author's presentation.

## Select the model and credentials

Create a configuration **outside the skill and model workspace**, for example:

```json
{
  "provider": "deepseek-official",
  "model": "deepseek-flash",
  "reasoning_effort": "high",
  "profile": "sdk",
  "base_url": "https://api.deepseek.com/anthropic/v1",
  "api_key_env": "DEEPSEEK_API_KEY"
}
```

Use the exact model and effort supported by your DSH adapter. The example is not
an entitlement check. Credentials may instead already be configured in an
explicitly selected `dsh_home`. Do not put API keys in the config, request, skill,
transcript or PPTX. Model API fees belong to that configured account; this route
does not consume or automatically inherit a Codex subscription. The engine uses
an explicit task-private DSH home unless you select another one.

The official DSH adapter uses DeepSeek's Messages endpoint. A base URL copied
from a Responses or Chat Completions profile is not interchangeable; use the
native provider default or its actual Messages API base URL.

To reuse an existing private JSON credential file, select `api_key_file` instead
of `api_key_env`. The file must have an `api_key` field and mode 0600. Only its
path belongs in the configuration; its contents never belong in this skill.

## Run, inspect, stop and resume

Save the actual brief and attachments in a request JSON file:

```json
{
  "title": "Presentation title",
  "brief": "The actual user request, without rewriting its scope",
  "pages": 5,
  "language": "zh-CN",
  "mode": "create",
  "attachments": ["/absolute/path/to/source.png"]
}
```

Use `edit` for a supplied-deck edit. Omit pages when the user has not specified a
count; the admitted outline remains capped at 50. Attachment paths can be relative
to the request file. The source is retained and checksum-verified.

```sh
python SKILL_ROOT/scripts/portable_workflow.py run --backend dsh --config /private/dsh-model.json --request /work/request.json --out /work/ppt-task
python SKILL_ROOT/scripts/portable_workflow.py status --out /work/ppt-task
python SKILL_ROOT/scripts/portable_workflow.py message --out /work/ppt-task --kind revision --text 'The actual modification request' --attachment /work/new-reference.png
python SKILL_ROOT/scripts/portable_workflow.py message --out /work/ppt-task --kind chat --text 'How is progress?'
python SKILL_ROOT/scripts/portable_workflow.py stop --out /work/ppt-task
python SKILL_ROOT/scripts/portable_workflow.py resume --backend dsh --config /private/dsh-model.json --out /work/ppt-task
```

Keep the run process alive, or use the calling harness's authorized background
execution. Packaging a skill does not override host sleep/background policies.
Wait for paused/failed status and process exit before resume; concurrent runs on
one task are locked out. Resume retains provider/model/home and frozen artifacts.
An explicit `max_tokens` change in the selected configuration is recorded in a
host receipt and may raise the per-request output allowance after truncation.
It does not switch models, relax report validation or approve an incomplete pass.
DSH's SDK currently exposes runtime shutdown, not a per-session cancel RPC: the
adapter closes only its owned phase runtime and confirms cancellation before a
file-preserving context rebuild. It never silently switches to Codex.

If restoring a checkpoint changes the workspace path, the old DSH session is
retained and the workflow starts a fresh file-based context. Changing a DSH
working directory does not change its permission origin; the adapter does not
pretend an old origin grants access to the restored workspace. Same-workspace
native session restoration remains available.

An author that keeps inspecting after declaring an export can hand that exact
candidate to the host at a safe tool boundary. The model runtime's actual stop
status is recorded separately. This only ends authoring: authored-contract
checks, frozen rendering, independent reviews and any required repairs still
run before delivery. New revisions, changed bytes or owner stop invalidate the
handoff. A declared file is not a review pass.

`presentation.pptx` is the accepted final standalone file. `status.json` records
state and final hash. `host/execution.json` records the host-selected model and
harness, hashed skill/engine identity, and observed phase/tool summaries. These
are execution receipts, not provider-confirmed model identity or proof of design
quality. `doctor --full` verifies the package's payload hashes before execution;
a mixed or modified installation must be rebuilt/reinstalled rather than called
the verified release. Task-local `trajectory/`, `host/records/`, `host/usage/`,
`local-worker/`, `state/` and `workspaces/` retain the real exposed execution,
checks, independent review receipts, native reported usage and recovery evidence.
Native usage is not an independently verified API invoice; missing usage/cost is
unknown, never zero. Do not deliver internal state alongside the final PPTX.

Other harnesses can load the skill and call these same tools. The currently
implemented complete execution adapter is DSH; another outer harness calling
`--backend dsh` still runs DSH internally. A new complete backend must implement
the session/event/receipt adapter and pass the same workflow tests. Do not describe
an unimplemented backend or merely copied instructions as a tested full adapter.
