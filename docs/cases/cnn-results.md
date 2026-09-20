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
- Monaco repaired release: **`0.1.0+codex.20260919230549`**, runtime
  `be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
  The same task recovered its existing work at **2026-09-19 23:14 UTC** after
  the Monaco correction passed the new smoke checks. All eight selected original
  and restored files match. A plugin upgrade rebuilds the model context and
  invalidates old stage receipts; it does not certify or discard the saved deck.
- Current corrected release: **`0.1.0+codex.20260919234350`**, runtime
  `8635c55584176218c6eadbc829d8796531bc99887469f24f6fc2345130222d37`.
  An actual HTTP/2 checkpoint publication failure stopped the prior attempt.
  After the transport correction and font-release checks, the same task resumed
  at **2026-09-19 23:49 UTC**. All eight selected original and restored files
  match, including the repaired v007 scenes and saved native page. The new
  context is revalidating the preserved work; final delivery is still pending.

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
review certifies the unfinished teaching artifacts. The current runtime release
and handover passed
[GitHub CI](https://github.com/dijiahU/rick-ppt/actions/runs/35475675726).

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

The [bounded v005 draft review](cnn-draft-interaction-review.md) adds 196 passing
multi-channel/ReLU/pooling assertions through real controls and workers, with
14 inspected captures, plus an independent check of the first eight latest
native previews. The full-CNN derivative browser check also found a font
packaging/CSP issue; its numerical success does not waive that finding. Current
scene changes and the eventual delivered pair still need final acceptance.

The all-twenty v007 initial-formula review on the current runtime found no font,
CSP or page-health failure in 40 inspected captures. Targeted pixel diagnostics
distinguish harmless typographic-bound warnings in pages 9/12 from a slight
parenthesis crop in page 14. A source review also found fixed baseline numbers
that should be distinguished from changed-code results in pages 4/19. Website
v30 delivered those bounded corrections together; the author is continuing at
input revision 7. Details and the unchanged failing diagnostic receipt are in
the linked draft review.

A subsequent C03 boundary check uses real keyboard editing to make the kernel
larger than the image. It found a missing validation path that removes the live
scene and its Reset button. Website v31 delivered that precise scene correction
through the same task, now at input revision 8. The failure is retained, and
repair/retest remains required before accepting the case.

That larger-kernel repair now passes 71 independent checks through real keyboard
input and controls. Separate checks confirm the baseline label and repaired
gradient-formula margins. They also confirm that held-out numbers follow the
changed worker run, while exposing a new TeX-escaping error that hides the percent
sign. Website v32 requests that bounded display correction before final export;
the preserved 15/18 diagnostic report is not presented as an all-pass result.

The corrected result scene then passed 61 independent checks, including one
actual learning-rate-zero edit/run, all eight returned examples and Reset.
Both 75% and 50% retain their visible percent sign and held-out label. The
author reports 194 scene tests with 679 assertions across all 20 scenes. The
host independently reran the frozen candidate with the same passing counts;
[frozen-candidate evidence](cnn-frozen-review.md) also records source correlation
and 95 additional scoped interaction checks. Audience approval is still pending.

The first independent audience phase exceeded its default 900-second limit after
inspecting all 234 interactive captures. No review verdict or final delivery was
produced. The completed author receipt and exported files remained intact. The
host increased the nine named review-phase limits to 2700 seconds, retained the
10800-second overall limit and the exact plugin version, drained its idle worker,
and conditionally requeued the same failed task at **2026-09-20 01:25 UTC**.
The new journal points to the recovered workspace at input revision 9 with
`next_phase=review`; authoring remains recorded as completed. The pending review
is restarted from the preserved export rather than rebuilding the 20 pages.

## Pending acceptance

Independent content/visual approval, matching portable bundle and delivered-file
retrieval remain pending. The exact completed authoring and scoped interaction
checks above are not yet an accepted website delivery.
Desktop PowerPoint playback remains separately unverified.
