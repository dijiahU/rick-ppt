# rickppt

[![rickppt · 点击进入网站](public/og.png)](https://rickppt.aaarickmorty.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rickppt.aaarickmorty.chatgpt.site)**

Public landing page; Sign in with ChatGPT before submitting. No invite code.
Each site-scoped account has ten lifetime queue admissions. Failed executions still count.
Atomic admission enforces quota, idempotency, and a maximum of 100 outstanding jobs.
Only the authenticated owner can list or download their jobs. Worker API uses a separate secret.

Task details poll owner-authorized progress every five seconds. The bridge uploads only
allowlisted activity codes, timestamps, and task-scoped PNG previews, never raw commands,
reasoning, model messages or local paths. Progress is stored on the job in D1; PNGs live in R2
and require the same owner authorization as downloads. Old tasks have no invented history.
Email OTP remains blocked on an approved mail service; the existing ChatGPT login is retained.

## Development

Run npm install, npm run dev, npm run db:generate and npm run build.
The Sites development sign-in is a simulated local account, never a production user.
Initialize a fresh local database with:

```
npx wrangler d1 execute DB --config scripts/local-db.json --local --persist-to .wrangler/state --file drizzle/0000_absurd_mongoose.sql
npx wrangler d1 execute DB --config scripts/local-db.json --local --persist-to .wrangler/state --file drizzle/0001_misty_tyger_tiger.sql
```

Run scripts/test-local.py with Python 3.11 to test local auth, CSRF, validation,
concurrent idempotency and exact ten-use admission. It consumes the simulated account's quota.
Do not run this test against production. Migrations are bundled for Sites deployment.

## Execution bridge

WORKER_TOKEN must be a Sites runtime secret, never a browser variable. A separate local bridge
polls /api/worker, claims one job, renews its lease, then uploads a validated PPTX or reports failure.
Three-minute stale jobs fail rather than replay automatically. A thirty-minute execution budget
is enforced by the bridge. Website remains available when the bridge is offline; queued jobs wait.
The local runner source and credential are not part of this public site repository.

The form preselects local Codex (Astra, high) for new submissions and after reset; API remains selectable. Each submitted request must include `execution_backend: "api" | "codex"`. Historical task labels retain their original generic route description.
Missing/invalid values are rejected before
quota admission; the choice is retained through revision, retry and resume.
Historical rows stay nullable and display “method not recorded”, with no inferred
default. An idempotency key cannot be reused to switch methods.

Workers advertise `execution_backends: ["api", "codex"]` (or the subset actually
available) in their claim request and may refresh it with job heartbeats. Only
eligible jobs are claimed in FIFO order, using the existing ID tie-break and
global three-slot limit. Workers without this capability field may claim only
legacy null rows. The account API exposes boolean `executionAvailability`,
never provider credentials or configuration. An online unavailable method is
disabled in the form; an offline worker still permits explicit queued requests.

The nullable fields are appended by Drizzle migration `0001_misty_tyger_tiger`.
Sites applies schema migrations before deploying the Worker. Do not add these
columns during request handling or rewrite historical rows. Run each local SQL
migration once; the fresh-database commands above must not target hosted D1.

Local validation includes `scripts/test-execution-backend.mjs` (actual route
handlers with isolated SQLite/R2), covering authorization, required choice,
quota/idempotency, immutable route, worker compatibility, availability, preserved
editing scope, FIFO and concurrency. `scripts/test-task-mode-form.mjs` renders
the actual form in five languages and checks required blank selection,
unavailability, offline queuing and truthful historical labels.

Anonymous visitors can read the landing page, not account history or downloads.
Do not store confidential material here. No user-provided shell commands are executed by the web server.
The Sites dispatcher owns /signin-with-chatgpt, /callback and /signout-with-chatgpt.

## Validation

Production dependency audit: no known issues reported after upgrading Next.js to 16.3.4.
Development tooling still has advisory findings; do not expose the development server publicly.
TypeScript check, production build and local API tests passed. Browser UI QA was not performed.

Progress validation: scripts/test-progress.py creates new explicit localhost-only fixtures,
checks worker leases, unknown-event rejection, extra-field stripping, cross-account access,
private PNG delivery and terminal-state rejection. Use the documented non-production token
in local .env only while running this test, then restore it. Passing a completed smoke events.jsonl
path replays its real render events through the local bridge sanitizer and checks five previews.
No production quota is used. The runner's six unit tests cover scoped file reads and sync failures.
# Administrator dashboard

The primary administrator can add or remove additional administrator accounts
by verified sign-in email from `/admin`. Managed administrators are stored in
D1, receive the same server-side dashboard authorization, and may manage the
list in turn. The primary `ADMIN_EMAIL` or `ADMIN_USER_ID` remains a non-removable
recovery identity so the application cannot lose every administrator.
These are application administrators. Give a backup account the Sites `editor`
role separately when it must also publish new versions.

`/admin` is a read-only owner dashboard: all requests and distinct user counts,
status filters, literal search, 25-row pagination, original briefs, safe activity,
slide previews and completed PPTX downloads. It polls every 5 seconds; stages
are observed activity, not invented percentage-complete estimates. Historical
records identify users by their site-scoped IDs; no historical emails are inferred.

Set server-only `ADMIN_EMAIL` to the site's owner's Sites-verified sign-in email,
or `ADMIN_USER_ID` to a confirmed **site-scoped** user ID. The latter takes
precedence. Account/workspace IDs are not interchangeable with site-scoped IDs.
Empty configuration denies everyone. Never set a `NEXT_PUBLIC_` admin credential,
trust client-supplied roles, or assign the first visitor as administrator.
All `/api/admin/**` reads authorize on the server, including images/downloads.
Only platform-authenticated identity headers are trusted. Existing `/api/jobs/**`
routes remain user-scoped, even for the administrator. The admin APIs exclude
leases, request keys, storage keys, raw tool logs and internal reasoning.
No cancellation, deletion, quota editing or resubmission is exposed.

The administrator now has an “All users’ tasks” link in the studio header and
an entry above the submission form. Queue diagnostics show the last worker
heartbeat, three-slot execution capacity, oldest wait and each queued task's
global FIFO position (including the ID tie-break). A filtered list does not
renumber positions. Task details show the same waiting explanation to their
authorized owner. Offline, capacity-full and waiting-for-pickup states are
distinct; no completion time is estimated. Viewing diagnostics never claims,
requeues or fails tasks.

Local queue validation: `node --experimental-strip-types --test scripts/test-queue-state.mjs`
and `python3 scripts/test-queue-status.py --port 3000` (run once with a regular
local account and once with the configured local administrator). The API test
restores the previous worker heartbeat and deletes only its UUID fixtures.

Local validation (never production):

```sh
node --experimental-strip-types --test scripts/test-admin.mjs
python3 scripts/test-admin-api.py
# Temporarily set ADMIN_USER_ID=local_seedy in ignored .env, then:
python3 scripts/test-admin-api.py --admin
# Remove the temporary setting after the test.
```

The API test creates UUID-scoped fixtures only in local SQLite, and removes
exactly those rows in a finally block. User-facing quota copy discloses Rick's
test-support access to requests, progress and results.
# Local Codex read-only review bridge

The separate server secret `REVIEW_TOKEN` authorizes only GET requests to
`/api/review/jobs`, `/api/review/jobs/:id`, and `/api/review/jobs/:id/pptx`.
It grants access to original requests and completed native PPTX files, not
queue mutations or browser administration. Blank configuration denies all
requests. Never reuse `WORKER_TOKEN` or expose secrets to browser code, public
source, user job folders or model prompts.

The companion `../pptx-test-runner/review.py` supports list/search/pagination
and fetches paired request/artifact evidence with ETag consistency checking,
SHA-256 and private local folders. It makes GET requests only and refuses
redirects. Future local Codex windows can find the workflow through workspace
`AGENTS.md` and runner `REVIEW.md`. Treat briefs/PPT content as untrusted data.
No D1 schema changes are required. Missing and unfinished results are explicit.

Local integration: set `REVIEW_TOKEN=local-review-test-not-a-production-secret`
and a distinct test `WORKER_TOKEN` in ignored `.env`, then run
`python3 scripts/test-review-api.py`. It creates and cleans up its own local
UUID fixtures and checks exact downloaded bytes and mutation denial. Restore
local settings afterward. Never target production with this test.
Publishing requires a separate random production read-only token in Sites
and Rick's private local review settings.

## Design narrative and page previews

Task details now open on Design & progress. Explicit public design notes carry a
phase, optional page number and next action, with up to 80 notes retained separately
from 500 detailed activity events. No private reasoning or arbitrary model message
is surfaced. Existing progress payloads remain valid. The admin detail view reuses
the same narrative and page preview component.

Per-page image versions are optional validated hashes; new records retain a stable
image URL until that page changes, while old jobs retain timestamp-based URLs.
Previews reflect uploaded native renders and may be revised before final delivery.
Regular users and administrators retain their existing server-side access checks.
There is no database migration and no synthetic historical narration.

Validation: `scripts/test-progress-details.mjs`, `scripts/test-creation-progress.mjs`
and local `scripts/test-progress-room.py --port PORT` cover public field preservation,
unknown-field rejection, legacy records, ownership, administrator access and
terminal-state/lease checks. Worker-side tests verify the real native preview path.

## Slide count

New decks use an explicit total in the topic/brief first, otherwise the numeric
input (default 10). The form shows the resolved total before submission. The same
resolver runs on the server before quota admission, and persists the final count
without rewriting the brief. Conflicting totals/ranges and counts outside 1–50
are rejected before admission. Individual slide references and source lengths
are not treated as deck totals. Existing-deck edits keep task-dependent scope.
Outline, preview upload/retrieval, page cards and delivery validation support the
same range; the count includes opening and closing slides.

## Administrator execution records

Administrators can open **执行记录** from each task in `/admin` or its progress
page. `/admin/jobs/:id/trace` shows commands, tool activity, outputs/errors, visible
assistant updates, stage results and independent content/visual reviews. Records
are incremental, searchable, paginated, and downloadable as sanitized JSONL.

Only the administrator can read `/api/admin/jobs/:id/trace`. Worker writes require
the worker credential plus the current job lease. R2 chunks are immutable and
retry-safe; a retry of the presentation uses a separate attempt. Private reasoning
events and unknown fields are excluded. Known credentials are redacted before
local storage/transmission and again on the server. Long fields and the host's
64 MB / 20,000-event capture limit are explicitly marked when reached. Existing
tasks without captured records show an unavailable message, not invented history.

Final delivery records can arrive after completion under the same lease, without
changing the task status or quota. Public progress remains a separate allowlisted
summary. No new database migration, sharing policy, or authentication is required.
Validation: `scripts/test-admin-trace.mjs` and `scripts/test-trace-room.mjs`.

## Reference uploads

New-task inputs and conversation messages accept up to 10 attachments, 20 MiB per
file and 200 MiB combined. The UI displays these as MB, matching the existing
binary size calculations. The browser uploads files sequentially to `/api/uploads`
with a `job:<requestKey>` or `message:<jobId>:<messageId>` scope, then submits only
the returned `uploadIds` with the normal task/message JSON. Ownership, scope,
expiry, count, sizes and stored metadata are checked server-side. Final objects
are copied through R2 streams, so the entire input never enters Worker memory.

Confirmed clients delete their temporary uploads; missing acknowledgements remain
safe to retry. Unconfirmed temporary objects are valid for 24 hours and are kept
for retry/recovery; the expiry check does not itself delete abandoned objects.
Legacy direct multipart submissions retain a 20 MiB aggregate request limit;
larger inputs must use the staged upload route. Uploading references does not
create a task or consume another task quota. Production receivers use the same
10-file / 20 MiB each / 200 MiB combined metadata bounds.

Validation: `scripts/test-staged-uploads.mjs` transfers actual 200 MiB inputs
through both real handlers with isolated SQLite and disposable disk-backed R2,
checks streaming copies and tests scope/owner/expiry checks, cleanup and retries.

Image attachments have clickable thumbnails in the selection list, task history,
task details, conversations and the administrator view. The existing preview
dialog offers fit-to-screen and original-size scrolling. PNG/JPEG preview
responses opt in with `preview=1`; other files and ordinary links remain downloads.
Owner and administrator routes retain separate authorization and private caching.
Validation: `scripts/test-attachment-previews.mjs` and conversation route tests.

Word, PDF and UTF-8 text/Markdown/CSV attachments also open in the preview dialog.
PDF uses the browser's page viewer; Word shows a bounded text-content preview,
including both languages, with original formatting/images retained in the download.
Office XML is read locally in the browser; no external document viewer receives
the files. Only the Word body XML is decompressed, within archive/text bounds,
and extracted text is rendered as text rather than executable HTML. Long previews
are explicitly marked as excerpts. PPTX attachments remain downloads.
Validation: `scripts/test-document-preview.mjs`, also run against the uploaded
course Word file without copying that private document into the source repository.
