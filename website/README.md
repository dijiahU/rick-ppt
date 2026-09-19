# PPTX LAB

[![PPTX LAB · 点击进入网站](public/og.png)](https://rick-ppt.woodsy-crane-8759.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rick-ppt.woodsy-crane-8759.chatgpt.site)**

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
npx wrangler d1 execute DB --config scripts/local-db.json --local --persist-to .wrangler/state --file drizzle/0000_absurd_virginia_dare.sql
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
