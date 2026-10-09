# PPTX LAB local execution bridge

[![PPTX LAB · 点击进入网站](https://rickppt.aaarickmorty.chatgpt.site/og.png)](https://rickppt.aaarickmorty.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rickppt.aaarickmorty.chatgpt.site)**

Website: https://rickppt.aaarickmorty.chatgpt.site

Current production policy delivers one standalone native PPTX. Author pages in
order, seek relevant design knowledge/material when the task benefits, and run
independent content/visual reviews in parallel on the same frozen candidate.
The visual review checks style against content, purpose, audience and viewing mode.
Expression is chosen from the actual content, evidence, audience, purpose, viewing
mode and supplied constraints. New presentations require meaningful native click
reveals; multi-step explanation uses an entry/click/final-view plan. Static covers
and single-message pages are allowed. The host pins this requirement outside the
task, rejects all-static new plans and checks actual entrance targets on the
exported pages. Transition-only and cosmetic title effects are insufficient in
visual review. Faithful conversions, scoped edits and older admitted tasks preserve
their behavior contract. No default medium, layout, density, style or asset-acquisition sequence. Search, generation and native authoring are available
when they help; inspect and embed selected assets, preserve required editability
and distinguish original illustration from documentary evidence. Reviews judge
actual task fit, not adherence to a preferred visual recipe.
Each page must have an explicit expression choice and explanatory role. New
multi-page decks require purposeful differences across the sequence instead of
one repeated treatment; recoloring is insufficient. Comparable material can keep
consistent encoding. No fixed rotation or requirement to use every option.
Critical decisions use the finite [workflow branch protocol](../pptx-agent/skills/pptx/references/workflow-branches.md)
and its versioned choice catalog. Task entry has only create/edit and follows the
existing host mode; ordinary missing material is handled in its source/asset branch,
without a mandatory input-completeness gate. Agents record decision-plan.json alongside the
public outline, selecting task/page/asset/behavior branch IDs and executing their
entry conditions and actions. The host validates exact page coverage, eligibility,
tool availability, planned variation and selected bytes/native behavior on the
actual authored page. Invalid/missing selections stop acceptance before independent
review; this is an execution contract, not an aesthetic score. Review findings
select content_revision, native_repair or retain_suggestion; implementation-only
findings do not force full content research. Existing approved-byte recovery and
legacy reports keep their compatibility path. No additional audience review stage.
The v3 contract selects audience strategy and concrete canvas composition instead
of free-form layout/density labels. Authors retain typography, color, crop, scale,
overlap and rhythm decisions. Image/type combinations and deliberately designed
pure-text pages are explicit; repeated prose-box language is judged on actual pages.
Applied artistic/design/teaching references record exact work/title/creator/source,
actual inspection, observation, borrowed principle and page action. A protected
host admission receipt prevents new tasks bypassing v3 with historical records.
`design_references.py` writes applied records into affected slide notes before
export; the host verifies final notes and actual selected asset bytes. Scoped
reference images/notes reach visual review after initial canvas judgment, while
the blind content pass excludes author design records. V3 visual reports assess
audience fit, sequence and reference transfer without scores or extra review rounds.
`native_canvas.py` supplies installed-font metrics, native image crop/layering and
editable one-unit bars, not slide templates. Authors/reviewers share the saved
output-language contract. The media broker bounds DNS recovery and caches only
verified public answers within their TTL. Old verified exports and admitted tasks
retain protected historical compatibility without fabricated artistic provenance.
Ordinary chat preserves reviews; actual revisions invalidate them. Owner pause
stops authoring/rendering/reviews and retains recovery checkpoints. Reviewed files
can be retransmitted after exact hash/revision checks, including across upgrades.
Source conversions and scoped edits prioritize fidelity. Native semantic groups,
anchored connectors and scaled reading previews support editing and review.
Historical browser-scene/portable-bundle instructions below describe older versions;
the single-file production profile disables those paths. Native runtime staging
does not require building their browser assets.

New default-provider tasks use `gpt-6.1-sol` with `high` reasoning. Both values are
pinned in each task's private model receipt and reused on recovery. Existing
model-only receipts retain their model and implicit effort. Explicit external
provider profiles retain their own model and reasoning settings. Optional private
settings `default_model` and `default_reasoning_effort` control newly admitted tasks.

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
The token must match WORKER_TOKEN in Sites. The bridge uses curl to respect this
host's proxy setup. The credential is not passed to Codex, the renderer, command
arguments or website client code.

After every plugin installation/cachebuster, run the
[installed hook Python preflight](../docs/installed-hook-runtime.md) against that
exact installed directory and the retained dependency venv, then repeat with
`--check` before activation. Worker success with an explicit Python path does not
verify the cached hooks' default `python3` startup. The tool adds only a missing
`.venv` link and never replaces an existing environment.

For a complex interactive lesson, the host can set `job_timeout_seconds` up to
10800 and `phase_timeout_seconds` to an object such as `{"author":7200}`. The
phase override is still bounded by the remaining overall task deadline;
ordinary jobs retain the existing 45-minute authoring and 90-minute total defaults.
Independent reviews default to 900 seconds each. Lessons with many interactive
captures may need explicit overrides for `content-first-1`, `content-evidence-1`
and `visual-1`; set the corresponding `-2` and `-3` names for repair rounds too.
The production 20-page CNN case uses 2700 seconds for each of these nine phases
after its first review exceeded 900 seconds while inspecting 234 captures.
Keep these limits in the private host settings, not the task prompt. Settings are
read when the supervisor starts: drain and hand off the worker before retrying.
Retain the exact plugin version when resuming unchanged completed authoring;
verified revision/artifact receipts allow the workflow to restart at review.

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

The workflow considers text, sourced media, original generation and native diagrams
according to the task. Chosen factual illustrations must preserve verified identity,
structure and meaning; chosen generated concepts are labeled illustrative. No
fixed acquisition sequence, pilot-page requirement or preferred medium. Review
checks actual explanation and requested behavior, not package validity alone.
An unmet essential requirement is reported as a gap, not a verified completion.

The capability manifest distinguishes search, actual acquisition, native embedding and playback.
Public HTTPS images/GIF/video/audio can now be imported with the task-local web-media-proxy.py.
See WEB-MEDIA.md for formats, explicit conversion/fallback, limits and native embedding.
Build the isolated decoder with `docker build -t pptx-lab-media:2 media-container`.
The host validates and IP-pins each redirect, uses a configured unauthenticated
loopback HTTP proxy when present, and decodes media in a no-network container.
Proxy transport resolves through a fixed public HTTPS DNS service and pins the
CONNECT address while preserving TLS hostname verification. Direct transport
remains available without a local proxy. Requests have a shared 65-second download
budget and bounded transient retries; structured errors distinguish DNS, TLS,
connection, HTTP, size and non-media failures. The task never receives proxy
configuration, shell network or Docker access.
Native timing XML and embedded clips are available, but static render/export is not evidence
of verified PowerPoint playback. This does not change website reference-upload formats.
Tests: test-web-media.py (policy), test-web-media.py --live (real downloads through sandbox,
native embed/render/export), test-media-formats.py (real isolated format conversions).

The compatibility launcher `production-entry.py` reads the staged runtime from
the production runner's private settings rather than embedding a version path.
Copy it to the existing local bridge's `runner.py`, and copy `start-worker.py`
beside it. Existing bridge credentials stay in that bridge's private settings.
`start-worker.py --reload` stops new claims in the verified current worker,
allows active tasks to finish, and starts one configured successor waiting for
the singleton lock. Repeated reloads do not create duplicate successors.
Each worker writes a private `runtime-PID.local.json` receipt with the runtime it
actually loaded, branch-file availability and default model/effort. `waiting`
is a prepared handoff; only `ready` proves activation after isolation self-test.
Tests: `test-production-bridge.py`.

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

New website tasks receive `ANIMATION.md` with the progressive guide. Viewing mode
comes from the actual request; no assumed live/dual mode. Static presentation and
native builds are chosen for the audience and explanation, with no rule that
multiple ideas require animation. If builds are chosen, plan and inspect their
states. Preserve explicit instructions and unaffected existing behavior.

The task reviews native timing, click groups, targets and representative states
per page, and checks that builds survive final export. Native object entrance
timing is distinct from transitions and embedded media. Native timing is authored directly in the editable deck.
The website's image previews and independent LibreOffice render remain static;
neither certifies PowerPoint slide-show playback. No PowerPoint player is exposed
to the task, so its public review must distinguish encoded/inspected builds from
untested playback. `test-presentation-builds.py` exercises build behavior with an
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

HTTP/2 framing failures (`curl16`) are transient when no HTTP status or a 2xx
status was received, like other lost transport responses. Conversation poll and
checkpoint publication defer to their existing later retries; the local journal
snapshot remains saved before publication, and completed assistant replies keep
their durable outbox IDs across reconnects. Authentication/lease rejections and
local programming errors still propagate. This does not replay claim/operator
retry requests or change the HTTP protocol policy.

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

For explicitly requested site-owner acceptance cases when no signed-in browser is
available, `prepare-acceptance-migration.py` can prepare a single additive data
migration for an authenticated owner deployment. It does not submit anything or
read a credential. Supply the prepared request JSON, the exact existing task UUID
and title identifying the owner's account, and a fresh output SQL path. The SQL
adds only the new queued task, retains existing jobs and quota configuration,
checks global queue capacity, and deduplicates its request key. It introduces no
HTTP authentication bypass. Ordinary user submissions continue through `/api/jobs`
with their existing quota rules. Apply acceptance migrations only after the smoke
gate, then inspect the new job using the separate read-only review tool.

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


## Content-led composition release

Version 0.1.0+codex.20261009composition2 keeps the existing four stages, v3 decision
contract, sequential pages, separate bounded reviews and reviewed-hash single-PPTX
delivery. role/visual_action resolve audience question, canvas focus/proportions,
reading path, enclosure meaning and native pacing. Saved previews are compared at
natural section milestones; explicit body-page variation requests are checked even
when covers/photos interrupt a repeated pattern. Artwork records retain inspected
work, borrowed principle and actual page application. No new gate or style score.

native_canvas returns workspace/slide/object handles, supports explicit shapes,
anchored connectors, borderless semantic groups and reveal steps, and reports
measured required text height. Two media requests may run concurrently per task
with serialized publication and existing per-task limits. Decoder v2 returns safe
error codes; keep v1 available for existing workers. Oversized originals need a
same-source derivative, not raised decode limits.

Native rendering freezes scoped input bytes into a private read-only mount; a private
output mount is writable and its verified PDF is atomically published into the task. Trace input bytes and
render metadata are linked by SHA. Runtime staging records the container font
catalog; render reports and review packets include version and Fontconfig family
candidates. Per-glyph fallback and actual PowerPoint playback remain distinct
verification tasks. Do not assume host text metrics equal the container renderer.

Before submitting a new request, the form displays the resolved PPT language and
whether it came from a manual choice, the brief or the default. Manual selection
wins; the final literal is saved and shared by author and reviewers. This changes
no saved historical task or quota/schema. UI updates require normal Sites publishing.

## External model with retained hosted tools

APINebula Opus uses the exact provider model ID `claude-opus-5-5` and the existing
Chat Completions adapter. Configure a host-private profile, never a front-end key:

```json
{"model":"claude-opus-5-5","base_url":"https://apinebula.ai/v1",
 "wire_api":"chat_completions","api_key_env":"PPTX_MODEL_API_KEY",
 "web_search":"disabled","image_generation":false,
 "auxiliary_tools":"existing_backend"}
```

The external model receives native file/vision tools plus the explicit dynamic
`pptx_search_sources` and `pptx_generate_image` tools. The latter execute only their
requested operation through the existing default-provider channel in a separate
restricted context, and return source evidence or actual generated task-local PNGs.
They do not author pages, perform another review, or receive the external API key.
Native authoring stays sequential; content and visual review remain independent.
Reviewers do not receive generation/search helper contexts or author reasoning.
Source/offline constraints, original/generated distinctions and import limits remain.
The source evidence is recorded under retained-tool-evidence; observed tool events
and separate retained-channel usage are recorded, with no hidden reasoning.

Canonical `settings.local.json` selects `model_profile`; the launcher propagates
only its path while retaining separate website credentials. Loaded runtime receipts
include the actual `model_backend`. Existing default-provider tasks automatically
retain their admitted provider on resume. An external admission remains bound to
its recorded model/URL/tool route; key rotation is allowed, silent model changes
are rejected. Keep the profile file at mode 0600 when it contains a key. No global
Codex or Claude settings are changed.

APINebula model-list, vision/function call, real sandbox file use, schema response,
Opus→retained search and Opus→retained generation have been exercised with isolated
fixtures. The target's Responses probes returned convert_request_failed; use the
verified Chat adapter, not a claimed direct Responses capability. These probes
establish observed interface behavior, not the upstream identity behind an alias.


The API acceptance run also exposed the prior scratch-directory alias collision:
`:tmpdir` resolved to task TMPDIR and denied its own scratch files. Both permission
builders now deny the concrete host temporary root, with a more specific task
write grant, and point zsh TMPPREFIX into the task. Real sandbox tests verify
heredoc/task scratch writes and denial of a synthetic file outside the task.


External planning completion is followed by authoritative validation. If a provider
stops after a failed decision CLI, the same research context receives the concrete
error and exact scaffold, with at most two structural corrections. Facts, source
scope, existing assets and outline are reused; no additional research or audience
review stage is added. Invalid choices still fail rather than being auto-mapped.

The Chat adapter retries one empty transient transport failure within the current
request budget (TLS/connection/reset/timeout), never a partial response or certificate
failure. Existing bounded 429 retries remain. Closing the provider session kills
its active local upstream curl processes, so user pause does not leave the local
model transport running. Static SSE replay remains a compatibility mechanism, not
true upstream token streaming. No completion/frozen-artifact recovery policy changes.

The real independent-review test exposed a gateway that accepted JSON Schema
parameters without enforcing the report format. The adapter also states the exact
schema in the model instruction; the original strict host parser and report checks
remain authoritative. An external reviewer may receive one format-only correction
in its completed independent context, with a distinct turn receipt linked to the
original inspection. Incomplete turns or missing page coverage cannot use that
correction. A formatting failure does not cause research or authoring to be repeated.
Image-view events are retained in trajectories so actual page/state inspection can
be distinguished from reading only the structural inventory.
