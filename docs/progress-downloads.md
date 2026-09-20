# Progress downloads and interrupted correction recovery

Progress downloads are independent of final delivery. The worker checks task-scoped
successful exports in a background thread every 15 seconds, validates complete native
OOXML and passive Office content, and uploads an immutable SHA-addressed PPTX. An
incomplete newer export does not hide the previous valid one. Network failure retains
local files and retries. SIGKILL or offline operation can only retain the last export
already uploaded; source edits since that export are not a downloadable presentation.
The author now exports a new version after each checked page. Partial exports do not
relax the exact final page count or independent review gate.

The owner/admin task page exposes a clearly unreviewed progress download, page count
and saved time. Failed, queued and complete tasks retain access. Owner isolation,
worker lease checks before and after storage, SHA checks, bounded body reads,
monotonic revision/export ordering, and a separate draft table prevent overwriting
final delivery or promoting drafts to accepted results. Interrupted historical jobs
can be backfilled only with the worker credential and the exact failed-attempt
updatedAt; task status and quota do not change.

Unfinished content-revision/repair phases now take priority over an older reusable
author export. Recovery binds host review findings, baseline PPTX hash, revision,
plugin and phase causality; it preserves the interrupted author thread and enters
the following review round only after repair completes. Unverified or stale findings
return to authoring instead of approving the old candidate.

Validation: 16 draft uploader tests, 12 real-Journal recovery tests, 11 workflow
regressions, 25 completed-review tests; website route tests use real SQLite with
isolated storage, plus rendered labels in five languages. Typecheck and production
build pass. Read-only inspection of the actual CNN journal selects repair-1 on the
same thread with review-2 next; its saved 20-page export passes the draft validator.

Deployment status: source prepared, not yet published. The Sites connector returned
project_not_found for the existing project and no accessible sites; no replacement
project or access change was created. GitHub preserves the implementation. Existing
website worker routes remain usable. The latest CNN progress file is also retained
locally under the user's project delivery folder. YOLO is paused by the user's
instruction and is not retried.

## CNN recovery capacity fix (2026-09-20)

The resumed CNN task reached 1,353,369,952 checkpoint bytes across 22,477 files,
mostly retained interactive/native rendering history. The generic 1 GiB journal
budget stopped the worker during checkpointing; a subsequent user retry remained
queued after the one-shot worker exited. The host now uses a bounded 4 GiB /
100,000-entry budget, retaining per-file limits and all integrity validation.
No task files or prior snapshots are removed. All 51 journal tests pass,
including checkpoint growth failure followed by successful recovery under a
larger budget while preserving the previous snapshot. CNN alone is resumed;
YOLO remains paused by user request.
