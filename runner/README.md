# PPTX LAB local execution bridge

[![PPTX LAB · 点击进入网站](https://rick-ppt.woodsy-crane-8759.chatgpt.site/og.png)](https://rick-ppt.woodsy-crane-8759.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rick-ppt.woodsy-crane-8759.chatgpt.site)**

Website: https://rick-ppt.woodsy-crane-8759.chatgpt.site

The public site uses ChatGPT account login, with ten lifetime queue admissions per account.
Administrators retain their existing unlimited admission policy. This local bridge
runs up to three tasks concurrently using the local saved Codex login. The durable
workflow uses Codex app-server for live steering and compatible thread recovery.
Keep the Mac awake and Docker running. No launch-at-login service is installed.

## Start

```
../pptx-agent/.venv/bin/python runner.py
```

Run from this directory. Ctrl-C/SIGTERM stops new polling and lets the current job finish.
A forced interruption retains a host-owned checkpoint. The owner can resume the
same job from the website without creating a duplicate quota admission; the worker
restores a verified new attempt and retains the old files. A job may run for at most
ninety minutes by default. A process lock prevents duplicate new workers. Use --once
for a single queue check, --self-test for filesystem/network
isolation, --codex-smoke for a minimal new Codex thread, --render-smoke for actual PPT rendering.

settings.local.json contains the worker credential; keep it private and do not send it to testers.
`PPTX_RUNNER_SETTINGS` may select an absolute private settings path. Required keys
are `site`, `token`, `plugin`, `python`, and `blank`; `plugin` must point to a built
versioned plugin directory and `python` to its dependency environment. Optional
`state_directory` selects private durable state. Never copy credentials into tasks.
It must match WORKER_TOKEN in Sites. The bridge uses curl to respect this host's proxy setup.
The credential is not passed to Codex, the renderer, command arguments or website client code.

## Isolation and workflow

### Content-first native workflow

Research/read sources → publish substantive per-page outline → author native OOXML
and appropriate declarative interactive regions → freeze and independently rerun
scene/native validation → independent content and visual reviews → repair → deliver
the exact reviewed PPTX and portable bundle. No compulsory art-direction document.
Small existing-deck edits stay within scope; there is no obligation to research unrelated topics.

Content receives priority: research, evidence, examples, explanation and organization
precede visual implementation. There is no fixed time/token percentage or separate half-budget
pool. Host receipts record elapsed time, output tokens and uncached-input-plus-output only
for observation, never as a quality score or acceptance gate. Match depth to the task;
do not pad research, repeat cached input or wait to manufacture a ratio.

The content reviewer first sees only actual pages, then a separate evidence pass receives
the original brief/sources and first-view report. A separate visual context sees the sequence,
full-size pages and native timing/media inventory. Neither sees the author's rationale.
Required findings block delivery until fixed; at most two repair rounds bound the loop.
Review receipts bind the artifact SHA-256. Static PNG/timing checks never certify playback;
visual status remains partly unverified when motion has no target-player evidence.

- Reviewers use fresh contexts. Author repair/recovery may resume the author's thread
  with narrow current-task filesystem access and no shell network.
- Codex receives no worker credential, other task directories, Docker socket or desktop tools.
- The renderer remains isolated in pptx-lab-renderer:1. Only scoped PPTX-to-PDF requests pass the broker.
- The output is frozen, unpacked, validated and rendered independently before audience reviews.
- Chart XLSX data may be embedded after passive-workbook validation; arbitrary active/OLE payloads remain rejected.
- Host-owned logs, review receipts and measured budget records remain private. The website receives
  only the public outline, explicit notes, completed assistant messages, review state
  and scoped page previews. Private reasoning is never published.

## Optional search and image generation

The runner explicitly enables live hosted web search and built-in image generation, independently
of disabled shell networking. Each job receives capabilities.json and the bundled ImageGen skill;
the PPTX skill includes optional research/asset guidance. The agent chooses these tools when they
fit the brief; offline/supplied-assets-only requests remain authoritative. No API fallback is wired.

Built-in images are saved by Codex in a thread-specific generated_images folder. AssetImporter
uses the trusted app-server start/resume thread ID, never an agent-submitted path,
to copy that thread's completed PNGs into the job's assets/. assets/index.json lists local assets.
Other threads are never scanned or imported; source/destination symlinks are rejected. Imports
are limited to 12 PNGs per task, 20 MB per PNG. No personal generated-image directory is granted
to the task. Inspect and embed images while preserving native editable text, data and diagrams.

test-capabilities.py --live checks real hosted search and generation. test-assets.py covers
thread confinement, symlink rejection and incomplete-image retries. test-visual-capabilities.py
runs a real two-slide search/image/import/render workflow with local-only delivery and no website quota.

## Visual material and quality policy

The PPTX workflow now routes professional/technical illustrations and requested motion through
supplied material and reliable reusable source research before generation or careful self-authoring,
subject to the user's explicit original/offline constraints. Key complex assets are piloted before reuse.
Quality review checks actual structure, execution and required motion, not only package validity.
Do not deliver unapproved crude substitutes as complete. If an essential visual requirement cannot
be met, the job should explain the gap instead of exporting a misleading final result.pptx.

The capability manifest distinguishes search, actual acquisition, native embedding and playback.
Public HTTPS images/GIF/video/audio can now be imported with the task-local web-media-proxy.py.
See WEB-MEDIA.md for formats, explicit conversion/fallback, limits and native embedding.
Build the isolated decoder with `docker build -t pptx-lab-media:1 media-container`.
The host validates and DNS-pins each redirect, sends no credentials/proxy configuration, and
decodes media in a no-network container. The task never receives shell network or Docker access.
Native timing XML and embedded clips are available, but static render/export is not evidence
of verified PowerPoint playback. This does not change website reference-upload formats.
Tests: test-web-media.py (policy), test-web-media.py --live (real downloads through sandbox,
native embed/render/export), test-media-formats.py (real isolated format conversions).

## Uploaded reference files

The website accepts up to 3 PDF/PPTX/DOCX/TXT/MD/CSV/PNG/JPG files with a brief,
10 MB per file and 20 MB total. Files are private R2 objects bound to the admitted job.
The host receives them only through the leased worker attachment endpoint, verifies
size and SHA-256, rejects unsafe/encrypted/oversized Office archives and active embedded
content, and saves UUID-based filenames in the new task's references/ directory.
Original names are display labels only. No host extraction or execution takes place.
The task reads the reference manifest before outlining and may use a requested PPTX
as a template without overwriting the original. It must disclose unreadable inputs.
No external upload, macros, scripts or expanded filesystem/network access is authorized.
These are size/type/isolation checks, not antivirus certification. Invalid document
structure may still fail the queued task; uploaded files remain private to their owner.
Run test-attachments.py and test-attachment-pptx.py for boundary and real generation tests.

## Presentation language

Website tasks carry a validated, saved `language` value: en, fr, es, zh-CN or ja.
The form defaults to its UI language (English on first visit) and allows a separate PPT choice.
The runner preserves that value in request.json and instructs authoring and rendered review to
use it for all audience-facing content, regardless of the language used to type the brief.
Proper names and original source titles may remain unchanged. Legacy jobs with no saved choice
keep their explicit brief language or topic language; they are not retroactively set to English.
test-language.py checks the transport boundary; test-language-pptx.py runs a real French
render/export smoke from a Chinese topic with local-only delivery and no website quota.

## Public activity panel

The updated bridge uploads allowlisted tool-activity codes and task-scoped PNGs, never model
reasoning, messages, raw commands, command output, local paths or thread identifiers. The site
polls these records every five seconds and checks job ownership for both events and images.
PNG reads walk task directories with no-follow descriptors and size/dimension caps. Intermediate
images may change; independent validation previews replace them before final upload.
Progress transport is best-effort with short timeouts and cannot by itself fail generation.
Validation renews the job lease, including between preview uploads. Run test-progress.py for
the sanitizer, symlink denial, duplicate suppression and failure-isolation tests.
Deploy the matching website version before restarting the worker with this updated source.

The renderer contains Ubuntu-packaged LibreOffice and Noto CJK fonts. Rendering may differ from
macOS PowerPoint. Current validation checks do not constitute a full security or visual fidelity audit.

## Build renderer

```
docker build --tag pptx-lab-renderer:1 render-container
```

No permanent Docker container or public local port is used. Rendering containers are ephemeral.
Task files remain in uniquely named pptx-lab-job-* temporary directories for diagnosis; remove only
specific reviewed task directories after completion, never while a job is active.

## Incremental page delivery

Read PROGRESS.md and PUBLIC-ACTIVITY.md for the task-visible narrative and per-page
render contract. `public-progress.py` is copied into each isolated job together
with allowlisted runtime script paths; it contains no website credential.
Deploy the matching site before draining/restarting the single local supervisor.
Existing running jobs retain their original task-local workflow; the new contract
applies to newly claimed jobs. No old task is resubmitted or rewritten.

Local verification: `python3 test-progress.py`,
`python3 test-content-workflow.py`, and `python3 test-progressive-e2e.py` using the
runner's configured Python. The end-to-end case intercepts every upload locally
and checks that page 1 is published before page 2 starts and before final delivery.

## Presenter-controlled builds

New website tasks receive `ANIMATION.md` with the progressive guide. For live or
dual-use decks, multi-idea explanatory pages default to native click-controlled
reveals, with initial/intermediate/final states planned before authoring. This
requirement matches the bundled skill's content-driven native-build guidance. Explicit static/no-animation briefs and unaffected existing
slides retain their requested behavior. Covers and single-message pages may
remain static when that matches their role.

The task reviews native timing, click groups, targets and representative states
per page, and checks that builds survive final export. Native object entrance
timing is distinct from transitions and embedded media. Native timing is authored directly in the editable deck.
The website's image previews and independent LibreOffice render remain static;
neither certifies PowerPoint slide-show playback. No PowerPoint player is exposed
to the task, so its public review must distinguish encoded/inspected builds from
untested playback. `test-presentation-builds.py` exercises the default with an
ordinary two-page brief, real isolated rendering and locally intercepted delivery.

## Connection recovery and explicit reruns

The current conversation-aware workflow adds durable phase/artifact receipts, live
message acknowledgements and checkpoint restoration. Read
[`workflow/README-recovery.md`](../workflow/README-recovery.md) and
[`workflow/README-app-server.md`](../workflow/README-app-server.md). The owner's
Resume button keeps the same job and previous successful versions. New revisions
invalidate stale review receipts; final completion rejects any newly pending input.

Interactive CLI calls route through `interactive-proxy.py`; the host independently
copies bounded local inputs, runs Chromium, freezes sidecars and assembles a bundle.
Read [INTERACTIVE.md](INTERACTIVE.md). Real transport and phase tests are opt-in;
they never contact production queues. The synthetic full-workflow smoke likewise
requires an explicit new proof path and retains its artifacts.

`resilience.py` keeps one independent heartbeat thread for the whole execution,
including attachment download, rendering, verification and upload. A successful
heartbeat is renewed every 20 seconds; transient transport/server failures retry
after 5 seconds without stopping generation. Each heartbeat request is bounded
to 10 seconds. An explicit lease/auth rejection stops the attempt immediately;
150 seconds without an acknowledgement stops it before the server's 180-second
stale-job cutoff. Claim requests are never automatically replayed.

Attachment reads and final completion/failure messages retry transient failures
up to three attempts. The deployed worker API accepts repeated completion/failure
acknowledgements for the same lease without replacing a delivered result. Deploy
the matching server before starting this runner. Private `failures/` records retain
sanitized action, HTTP and curl error codes; credentials and response bodies are
never recorded. `python3 test-resilience.py` exercises offline fault injection;
the portal's `node scripts/test-worker-recovery.mjs` exercises the actual routes.

Only with explicit authorization to rerun a failed task, POST the worker-authenticated
`/api/worker/TASK_UUID?action=retry` with its reviewed `expectedUpdatedAt` timestamp.
This atomically returns the unchanged failed attempt to the queue, resets its old
lease/progress, and preserves the brief, attachments, ID and quota charge. It rejects
completed/changed tasks, stale timestamps and a full queue. The review credential
cannot call this endpoint. Inspect ambiguous responses using read-only review access
before any further action; never claim jobs simply to inspect them.

## Release verification

test-native-workflow-live.py runs a real three-page new-model workflow with all site requests intercepted locally. It never claims a queue task or spends website quota. test-content-workflow.py checks outline invalidation, reviewer isolation, report coverage, honest token accounting and passive chart workbook acceptance. Existing transport, attachment, lease, asset and queue tests remain applicable.

New website requests resolve an explicit total in the topic/brief before the numeric
fallback input. The saved pages field is the final total. New decks support 1–50
pages consistently in outlines, preview reporting and delivery count validation.

Administrator execution tracing is host-owned. Each phase has a separate pinned
log reader for operational events, including independent reviewers. Reasoning
events are excluded. Sanitized JSONL is retained under private records/ and sent
as immutable, lease-scoped R2 chunks for the admin viewer. Attachment preparation,
verification and delivery status are also recorded. Trace transport failures do
not stop generation; retries resend the identical chunk. Long fields and capture
limits are marked explicitly. Raw original execution logs stay local.

## Local Agent trajectories

New queue executions write observable trajectories to `../trajectory/<task UUID>/<run UUID>/`.
This private local directory is separate from the plugin repository. Each run has
ordered `events.jsonl`, linked `steps.jsonl`, a checkpointed `manifest.json`, and
content-addressed `blobs/` with file-version maps under `snapshots/`.

Phase prompts, launch arguments, runtime/plugin files, exposed tool inputs and
outputs, reviewer reports, failed actions, revisions and delivery hashes are
retained. Long observations are not shortened to fit the website UI. Credential
redaction, local storage limits and unsupported events are explicit. These are
observable trajectories, not full provider model-request dumps: hidden reasoning,
resolved default model details, hosted search responses and exact image inputs may
not be exposed by CLI. File snapshots are not atomic under concurrent tools.

`trajectory_history.py --watch` uses only `review.py list/fetch` to mirror task
identities every minute and recover legacy terminal-task logs. It does not claim,
rerun or mutate jobs. Historical recovery marks unknown prompts, attempt boundaries
and original event timestamps, and preserves fetched original artifacts. Stop it
with SIGTERM; a private lock prevents duplicate mirrors. New recording failures
appear as capture gaps/admin errors and do not invalidate a successfully made PPTX.

Run `test-trajectory.py` to verify action/feedback linkage, long outputs, snapshots,
symlink protection, session isolation, actual subprocess capture and historical
read-only recovery. `test-admin-trace.py` and `test-content-workflow.py` cover the
existing trace transport and presentation orchestration.

Trajectory v2 also retains private original bytes under `raw-blobs/`, readable
artifact aliases by role under `artifacts/`, an append-only `artifacts.jsonl`
catalog and acknowledged final PPTX files under `final/`. Download originals and
normalized media are captured separately, before decoder temporary files disappear.
Every complete generated PNG from the verified CLI thread is archived independently
of the 12-image PPT import quota. Renderer inputs/PDF outputs are captured before
the broker replies, and task files are sampled every two seconds as well as at
tool/phase boundaries. There is no per-file/total archive byte truncation; disk
failures and unstable reads are gaps. Private originals are not training exports.

`trajectory_replay.py list RUN_DIRECTORY` lists snapshots and artifacts.
`trajectory_replay.py restore RUN_DIRECTORY --snapshot UUID --out NEW_DIRECTORY`
restores an observed file set and verifies original SHA-256 hashes without running
any archived code or model. `artifact RUN_DIRECTORY --id ARTIFACT_ID --out NEW_FILE`
restores one file. Existing destinations, missing originals, corrupt hashes and
unsafe paths are rejected. Byte restoration is not deterministic model rerunning:
unexposed provider context/results and transient writes inside a tool call remain
outside the capture boundary. `test-trajectory-artifacts.py` covers these guarantees.
