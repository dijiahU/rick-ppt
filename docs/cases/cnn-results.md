# CNN acceptance run

Status: **in progress; no teaching artifact accepted yet**.

- [Website task](https://rick-ppt.woodsy-crane-8759.chatgpt.site/jobs/db69fb9d-5d27-4fc2-9553-a722e2a5acbc)
- New task ID: `db69fb9d-5d27-4fc2-9553-a722e2a5acbc`.
- Same owner as the prior “介绍cnn” task; equality verified through the read-only
  review interface. The original task is unchanged.
- English, 20 slides, using the [researched brief](cnn-prompt.md) and
  [numerical/interaction contract](acceptance-checks.md).
- Initial admission: website v24, source
  `a7a8ddca306b8a61a530b9ed2e2f09394b63b865`, after the documented smoke gate and
  worker handoff. Ordinary worker leasing and the existing owner-scoped UI apply.
- Installed release: `0.1.0+codex.20260919212441`; initial runtime fingerprint
  `1f4b66baaf34bfd80dbf77dc29969cf43c8bfe1cb599d0b1644f6659e0575ae3`.

## Observations and repair history

The first real claim stopped before authoring because the durable journal's
generic identifier validator rejected the legitimate `+codex` plugin-version
suffix. The smoke fixtures had used `0.2.0`, so this installed-version boundary
had not been exercised. No slides or output were fabricated. The failure record,
initial task and read-only fetch are retained privately.

The correction now uses a separate plugin-version validator, preserves strict
task/run/checkpoint identifiers and adds an installed-version startup preflight.
It also distinguishes an empty failed-initialization directory from a committed
journal, retaining the former and refusing to silently reset a damaged history.
The actual installed cachebuster passes create/checkpoint/reopen/recover/receipt
reuse. All 70 workflow tests and 47 related runner checks pass. The same newly
authorized task will be retried after the final Office identity patch is staged.
An exact-task/timestamp-scoped data migration records a visible explanation and
requeues only this failed first attempt. It does not modify the original CNN,
change quota settings or create another duplicate task.

## Pending acceptance

The native deck, scene reports, actual edited-code execution, mechanism animation,
independent content/visual reviews, matching portable bundle and delivered file
hashes remain pending. This document is a progress record, not a pass certificate.
Desktop PowerPoint playback remains separately unverified.
