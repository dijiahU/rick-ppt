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
- Initial authoring release: `0.1.0+codex.20260919214127`, runtime
  `fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de`.
  Website v25 requeued this same task; the actual Codex research phase began at
  **2026-09-19 21:42 UTC** with a persisted checkpoint and thread identity.
- Current repaired release: **`0.1.0+codex.20260919230549`**, runtime
  `be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
  The same task recovered its existing work at **2026-09-19 23:14 UTC** after
  the Monaco correction passed the new smoke checks. All eight selected original
  and restored files match. A plugin upgrade rebuilds the model context and
  invalidates old stage receipts; it does not certify or discard the saved deck.

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
authorized task is now running with the final Office identity patch and its
passing 79-unit/23-browser/production-pack checks.
An exact-task/timestamp-scoped data migration records a visible explanation and
requeues only this failed first attempt. It does not modify the original CNN,
change quota settings or create another duplicate task.

## Research evidence

The worker has prepared a complete 20-slide outline, with one learner experiment
and a readable native fallback planned per page. Its fixed Python reference is
now retained as a [reproducible example](../../examples/cnn-reference/README.md).
The [independent numerical review](cnn-numerical-review.md) verifies all 50
parameters, 344 finite differences and an independently implemented 480-update
training run. It reproduces 16/16 training predictions and 6/8 held-out predictions;
held-out images never enter updates. Actual checkpoint losses rise at epochs 1
and 5 before declining. These are synthetic teaching results.

This evidence applies only to the reviewed source SHA. A separate
[actual Python worker check](cnn-python-worker-review.md) passed 22 assertions
under production CSP, including default training and learning rate zero. Neither
review certifies the unfinished teaching artifacts. The final runtime release passed
[GitHub CI](https://github.com/dijiahU/rick-ppt/actions/runs/35471242145).

The [controlled live recovery](cnn-live-workflow.md) now passed initial
continuation: the same task resumed the same author thread, reused research and
restored checked source files without changing the old attempt. Website v27 then
delivered one ordinary chat and two revision messages into that active turn.
They are acknowledged and clearly labeled automated acceptance feedback; final
answers and artifact application remain pending.

Subsequent live checks found and repaired a canonical-path problem after Mac
recovery and a Monaco multiline-edit event storm. The repaired runtime passed
79 unit, 24 combined browser, nine production-pack and three diagnostic checks,
plus 197 independent learner-input assertions on preserved draft scenes and
eight fresh native/bundle checks. These are scoped regression results. Eight
interactive scene receipts and corresponding page work were retained at handover;
the final 20-page artifact still needs complete revalidation on the new runtime.
Website v29 also delivered a precise request to fix the remaining formula
subscript clipping in v005 pages 15 and 16; the worker acknowledged it.

## Pending acceptance

The native deck, scene reports, actual edited-code execution, mechanism animation,
independent content/visual reviews, matching portable bundle and delivered file
hashes remain pending. This document is a progress record, not a pass certificate.
Desktop PowerPoint playback remains separately unverified.
