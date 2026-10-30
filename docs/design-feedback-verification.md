# Independent visual feedback and actual revision evidence

The production visual pass already uses an author-independent reviewer context.
A new critic persona alone does not address whether that reviewer identifies the
important gap, whether a designer acts on it, or whether the revised picture is
actually better. Technical acceptance and design maturity remain distinct.

The existing optional designer-response transaction saves an immutable reviewed
PPTX, previews and visual findings in host-private records. When a changed candidate
returns for its ordinary review, `review_comparison.prepare_refinement` now reuses
that exact current-task baseline. It provides only the prior visual-feedback target
pages and their original findings, with candidate/source hashes and actual prior
reading previews. It performs no new render, model call, asset acquisition or
quality scoring. No-op, rolled-back, missing or stale baselines are not projected;
unverified page correspondence is explicit. Preview integrity failures are rejected.

This material is exclusive to the existing visual pass. The blind content pass
and source-evidence content pass receive neither the prior design verdict nor
these comparison images. `prepare_review_materials` supplies the verified actual
PNG previews through the existing first-turn image path, not merely JSON file
pointers. Normal sealed review input identity and recovery still apply.

The visual guide asks for an independent critical reading before comparison,
then a concrete account of whether the earlier central gap is resolved, partly
resolved, remains or regressed. It must reject unsupported old findings and avoid
mistaking changed bytes, extra objects or peripheral polish for improvement.
A technically accepted old result is not a quality ideal. This adds no new agent,
review stage, mandatory scoring/form, style quota or unbounded iteration. Existing
required/suggestion classifications and the single bounded optional response,
exact-byte fallback, user stop and new-revision protections remain unchanged.

## Validation scope

Offline tests cover real PPTX dependency fingerprints, verified historical pixels,
current-task/revision filtering, exact first-turn image forwarding, visual-only
review roots, frozen input identity, no-op handling, rollback and interrupted work.
They do not prove model understanding or a general improvement in design quality.

A separate local subscription diagnostic used gpt-6-astra/high: two fresh anonymous,
order-reversed image reviews both preferred Rick's previously endorsed scoped
redesign, yet classified the weaker page's shortcomings as nonblocking. A fresh
native author then received the weaker PPTX, its real PNG and the original review
feedback, without the stronger image/code/history. In 322.62 seconds it completed
a substantive page-3 composition revision. Only slide3.xml changed; all other
pages/dependencies and the original four-click timing tree were retained. Active
fonts remained SimSun and Times New Roman. The candidate was rendered and checked
using exact OPC-part identity; ZIP packing bytes differed. This is a scoped feedback
experiment, not a full managed website task, independent scientific review, or
PowerPoint/Windows WPS playback test. It does not prove that all models will meet a
high visual standard or improve their autonomous first draft.

A fresh three-way anonymous image comparison ranked the raw-feedback revision above
the prior reference-assisted edit and baseline, citing the observable water-space
and outlet relationships. This was one reviewer/order, not a universal aesthetic
judgment. Source changes passed 112 targeted tests. At the end of that diagnostic,
no full managed website run, production reload/deploy or Git commit/push had been
performed.

A subsequent fresh local full-workflow test, a five-page Chinese Blue Note design
talk, completed in 1956.38 seconds using the same local model and reasoning effort.
Actual cover images entered the author's image channel before composition. Both
independent reviews completed and returned concrete correspondence/readability
suggestions. The optional designer response reached its 360-second limit without
submitting a revised candidate; connection retries occurred during that attempt.
The host retained the exact reviewed first-author bytes. Consequently this case
does not demonstrate applied design improvement and did not exercise the new
before/after refinement recheck in a live second review. The delivery was valid;
the feedback-to-revision execution bottleneck remains unresolved. No production
website deployment or worker reload was performed for that local test.

## First-candidate intent and bounded repair handoff

The continuing author now defines the intended visible result in the existing
design direction before implementation, and uses the existing early render to
check whether the main expression works. Complete text and a successful export
are not the finish line. This replaces overlapping guidance; it adds neither a
planning form nor a minimum revision count, per-page critic, aesthetic gate or
goal-mode continuation loop. Its effect on first-draft quality is unverified.

For the already authorized optional repair, `repair_inputs.prepare` supplies
the first visual finding, its actual reviewed target-page reading images and,
when available, the authoritative repair workspace's native object index. It
reuses host-private current-revision baseline receipts and the existing page
context; no new rendering/search is performed. Missing/oversized images and
object indexes retain explicit fallback states. The images are forwarded through
`Execution.phase(images=...)`; preparation metadata alone is not proof of viewing.

The authoring limit remains 360 seconds. When that host timer expires in the
ordinary response wait, the optional repair can interrupt the writer and wait up
to 15 additional seconds for its terminal transport receipt, bounded by the task
deadline. This is shutdown/verification time, not another writing interval. The
lease, user stop, pending input and revision checks remain active. Only the
explicit `delivery.json` candidate with changed bytes and stable identity can
cross this boundary. Incomplete/undeclared/no-op outputs, unconfirmed interruption
and expired task budgets keep the existing fallback. Accepted means candidate
handoff only: authored constraints, frozen rendering and independent reviews still
decide whether the file is deliverable. No files are selected by timestamp.

Offline tests use real PNG/PPTX files and mock app-server stdio to exercise actual
image forwarding, current object indexes, writer interruption, deadline handoff,
revision/stop propagation and invalid/no-op/mutable candidates. No new live
generation, absolute readiness gate or automatic visual winner selection is
claimed by these changes. Image-based human calibration remains an evaluation
activity, not a mandatory runtime reference corpus. Existing observed preferences
are relative judgments; unknown absolute-readiness labels must remain unknown.

## 2026-10-30: actual candidate handoff and the next design-sequence test

The five-page Harness² local full run (task de06463d-9f2a-4277-82a0-24c8bacd8839)
completed in 2550.06 seconds. Its author received actual registered figures and
applicable design-reference pixels before their relevant implementation. Independent
visual feedback identified the weak parallel/sequential distinction. Repair received
the actual page-3 reading image and 34 native objects directly. At 360.676 seconds,
the host interrupted the author and accepted its earlier explicitly declared complete
candidate, then froze/rendered and independently reviewed it. The final SHA was
bd64587be3c42a4a950fd18abe0ac96c46a531c1efc1f5e350ea55018230f9e3.
Only slide3.xml changed among slide parts; five notes changed. Page-2/4 padding
edits existed later in the working directory but were not re-exported, so they were
correctly absent from delivery. First-draft design maturity was not established.

The following narrow iteration replaces overlapping sequential-craft prose with
an explicit audience-task → concrete subject/evidence → expression/composition →
main render test → finish/checkpoint method. Existing short worked decisions are
supplied as actual text once at author entry instead of only a link. The existing
page-context tool supplies a composition cue before a current preview, and an
expression-test cue beside actual rendered input; sent receipts distinguish method
text from picture delivery and never certify understanding. No new page schema,
layout chooser, per-page reviewer, aesthetic score or image/revision quota is added.
Research guidance retains selective attributed source fragments alongside summaries.

candidate_save.py combines unchanged native export with real rendering, existing
authored checks when records exist, and atomic delivery.json declaration. Historical
exports are retained; failures keep the prior declaration. It does not replace
independent review, choose files by timestamp, or certify design/playback.
The change passed 161 targeted tests plus an actual native CLI export/render/save.
The fresh local full-workflow test afca65aa-c523-4e64-8838-5c9da826c64b uses the
same five-page brief, original template, local gpt-6-astra/high and a pinned portable
4f1d36ea36b7e2c2 package. Prior PPTX/feedback is not author input. Live search and
sampling are not frozen, so this is a same-task reproduction rather than a strict
quality ablation. At test launch, design benefit remains unverified. No production
worker reload, website mutation or Git push is part of this iteration.

The first launch stopped after research because the enabled author-role string
assembly contained a unary-plus TypeError. It was fixed before any author model
call; an executable three-role entry regression brings the targeted total to 162.
The corrected package is portable.86cbe326af72b577. Journal recovery restored the
current task and revalidated its handoff in 167.413 seconds. The successful attempt
then completed in 2088.4 seconds; total wall time including failure/recovery was
2934.82 seconds. This is not a clean latency or randomized quality comparison.

The author actually received the complete 7404-byte existing worked guide; the
page tool recorded 24 method-text sends. Saving ran successfully in both author
and repair. The first draft used explicit branches/chained states and an authentic
rule excerpt. Independent review requested a stronger retention path; only
slide4.xml changed during the bounded repair, which again handed off an explicit
candidate at its deadline and passed normal re-review. Final SHA:
acbd566820d32af99dbd499c4c480d021c4b014177374ddd3a8b6750ed32b32e.
The editable numeric example and case-score caption remained unapplied suggestions.
No general first-draft readiness, weaker-model transfer, speed gain or target-player
compatibility is established. No worker reload, website change or Git push occurred.

## Design completion and version selection, 2026-10-30

This iteration connects existing independent judgment to bounded action and actual
file selection. It does not establish a human-calibrated design threshold. The shared
design-completion guide reaches the continuing author at entry/repair and the visual
reviewer in its sealed role prompt. Subject/evidence selection, visible relationships,
proportion and craft remain content-led, without a prescribed layout, image count,
reference quota or additional author stage.

New substantive reviews require ready / needs_revision / uncertain and primary
finding IDs. Needs_revision must reference existing actionable findings and enables
the existing single bounded first-round response. Ready or uncertain alone does not
start cosmetic refinement. Finding severity, hard-defect repair, faithful/local-edit
routing and old pinned-report policy remain intact. Primary finding order controls
the actual target PNG/object input, rather than incidental finding-array order.

Re-review receives saved target images and other pages whose native dependencies
changed, including shared dimensions/fonts; no original rerender is added.
Structured comparison binds exact baseline/candidate hashes and accounts for each
original visual finding. Absent actual before/after input requires uncertainty.
Only a better valid candidate without reported material regression replaces the
baseline. Equivalent, worse or uncertain candidates restore reviewed bytes. Partial
improvement may remain explicitly unfinished. Public visual summaries and review.md
carry that state instead of equating file validity with completed design.

203 targeted checks passed: 163 runner tests plus 40 native batch, compatibility and
candidate-save pytest cases. Integration fixtures verify real PNG bytes in the first
visual call, hash/schema binding, content isolation, policy-sensitive cache reuse,
scoped edits, exact selected bytes, no-op, one-pass bounds and existing stop/revision
recovery. These are offline mechanism tests, not new model-generated presentations.
Initial unittest discovery for pytest functions and an import-shadowing PYTHONPATH
were corrected; those unsuccessful probes are not counted as passing tests.

Source version: 0.1.0+codex.20261030designcompletion1.
Portable engine: 0.1.0+portable.fd7cad211f10224c. All 254 package files, 186 source
hashes and ZIP entries were checked; skill validation passed. Archive SHA-256:
66ea2a453af17d5cd687962caeb810118ca0fcc26e2c7ef9ec9f10d75a97b7f6.
Evidence: builds/design-completion-selection-20261030-212204 in the PPT lab.

Remaining limitations: reviewers can still misjudge readiness, give weak feedback
or prefer worse pages. Consuming their judgments does not calibrate them or guarantee
strong first drafts. The bounded response can still end with an unfinished valid
artifact, now disclosed. No new paid model generation, worker reload, website
deployment or Git push occurred. Previous experiments and frozen deliveries remain
unchanged; source and the repository's portable release were updated.

## Operational evidence and sequence continuity, 2026-10-30

The completion-policy experiment 2a73ecaf-9292-4cfa-8afd-83ec123bd1cc finished
in 1680.14 seconds. Its first and delivered SHA were identical:
cc2f34dea8889d4d947c9abb028fcd4a412436ed516617b98845b61415eadb04.
The independent visual reviewer selected ready; no response or version-selection
branch ran. This verifies actual policy input/report consumption, not the selector's
design benefit. Rick observed improvement. Local comparison found stronger hierarchy
and a clearer retention/reset page, but the case lost its visible link to the prior
two-branch mechanism, its operation remained mostly named, and the full source
overview's relevant details were too small. The model listed two of those issues
while still accepting readiness. It remains one same-task, non-randomized sample.

The next narrow change updates existing author cues and reference guidance: choose
a source-supported operational detail when a case explains a mechanism; keep the
necessary cross-page entity/branch mapping; inspect relevant image detail at its
intended scale. Exact source rules or permitted labeled illustrations remain valid
when real outputs are unavailable. No fabricated documentary result, universal
before/after layout, image quota, new schema, stage or reviewer was added. The shared
completion guide asks the reviewer to reconcile readiness with its own findings
about an essential relationship/evidence that remains invisible. No string-matching
heuristic decides aesthetics, and the existing single-response bound remains.

130 focused checks passed (design-input transport 20, design-author/continuity 24,
phase context 19, design completion/selection 15, review sessions/cache/scope 52).
The portable skill validator and 254-file/186-source hash verification passed.
Source version: 0.1.0+codex.20261030designcontinuity1.
Portable version: 0.1.0+portable.71008dc496a08166.
Archive SHA: 2c2bf57065ccabdbb390ed629cfd5d937d7c529c93f29073b02cba2c5dd0b423.

Fresh local test 990547f5-d262-4d0b-a4ad-36de9cba7f5e uses the same five-page
Harness² brief and exact template, local Codex gpt-6-astra/high, fresh research and
author contexts, and synthetic local website transport. No old slide, old review or
observer's page-specific solution is an author attachment. Search and sampling are
not frozen; this remains a reproduction rather than a strict ablation. Candidate
freezes, actual previews, review receipts, selection records and the complete trace
are retained under builds/local-codex-harness2-design-continuity-20261030-231540
in the PPT lab. At launch its design result is unverified. Production workers,
website jobs, accounts and historical delivered files were not changed.

## Content presentation feedback, 2026-10-31

Test 990547f5-d262-4d0b-a4ad-36de9cba7f5e completed in 1722.82 seconds with
one frozen candidate and zero formal repair rounds. First and delivered SHA:
0a915e87eca25f97b4a6cdb934f82a75b771b1271aedec38cfd6bbe2193ae223.
Content F2 described consequential result qualifications buried in small credits;
visual readiness was ready and did not include that finding. The existing response
condition consumed only visual primary findings. Thus content presentation feedback
could not trigger the bounded response. That is a demonstrated routing gap; it
does not establish that every suggestion should be applied or that the whole deck
needs redesign. Content F1 also explicitly said the native diagrams already carried
the explanation, so a small supporting overview alone is not a compulsory repair.

The pinned completion guide now opts into content-presentation/v1. Only the existing
final source-checked content report adds presentation_findings: IDs of existing,
actionable audience-interpretation gaps. The blind pass is unchanged. No preference
quota or keyword classifier selects findings. Source/content correction cannot be
rerouted through this list. Old guides and receipts retain their original contracts.
Both reviews stay independent; their original findings, severities and judgments
are retained. Either a visual primary gap or a nominated content presentation gap
can authorize the same first-round, 360-second, one-response path when no required
defect exists. A new main author instruction makes necessary qualifications visible
alongside their evidence without requiring a uniform layout or text/font quota.

Existing repair inputs attach the nominated page's actual reviewed PNG and native
object evidence. Source-qualified IDs prevent collisions between content and visual
findings in repair/comparison inputs. The existing before/after pass checks the
original gaps and changed regions; source meaning is separately rechecked by content.
Worse/uncertain candidates still fall back to exact reviewed bytes. Missing final
content reassessment, or a newly nominated content gap where none existed, cannot
be accepted as an unqualified improvement. Unfinished content presentation remains
visible in the public summary even when the independent visual verdict is ready.

183 focused offline checks passed: completion/selection 21, continuing author 24,
repair images/deadline 14, comparison 12, review isolation/cache 52, recovery 13,
public reports 7, review material 12, phase context 19, workflow policy 9. Actual
fixture PNG bytes/colours were checked at the repair-call boundary and matched to
the host baseline; this is transport/decision validation, not a design-quality test.
Source version: 0.1.0+codex.20261031contentpresentation1. Previous source modifications
were retained; this iteration's backup is builds/design-content-feedback-20261031-003640
in the PPT lab. No worker reload, production task mutation or Git push was performed.

Portable release 0.1.0+portable.09f1eee9785aa18f passed skill validation; all 186
source hashes, 253 payload hashes and corresponding ZIP entries matched (254 files
including the manifest). ZIP SHA:
6438520f546109da75bc062784488119be65198e37fe3dd5187aec8380c2d435.
Fresh test 38d0d272-7848-4343-9eea-4fc044b18494 started with the same brief/template,
local Codex Astra/high and independent new research/author contexts. Its folder is
builds/local-codex-harness2-content-presentation-20261031-004420 in the PPT lab.
Only original inputs are supplied; old case conclusions remain host-side evidence.
First/final bytes, all frozen candidates, full traces, nominal versus actual repair
counts and source-qualified comparison findings are retained. At launch, generation
and its design benefit remain pending; live research/sampling are not controlled.

## Requested author-guidance rollback, 2026-10-31

Test 38d0d272-7848-4343-9eea-4fc044b18494 finished in 1432.57 seconds, with zero
formal repairs and the same first/final SHA:
61dc8640ae06621b99b3b7d0938faf501f10ac71680cc058b0804c5cbafa4031.
The visual report selected ready and the content report returned no presentation
priorities, so the newly connected response branch was not exercised. Rick preferred
the preceding design-continuity result. These fresh generations changed the outline,
case and design references; they do not isolate the effect of one instruction.

At Rick's request, removed only the new initial-author paragraph requiring important
qualifications to have a readable role beside their evidence. Existing source-fidelity
and readability requirements remain. Retained the content presentation priorities,
direct repair images and source-qualified before/after selection. No presentation
was regenerated or historical delivery modified for this rollback. Source version:
0.1.0+codex.20261031contentpresentation2.

Rollback release checks: 203 runner checks and 40 native candidate/compatibility
checks passed; skill validation passed. Verified the removed paragraph is absent
from source, standalone reference and embedded engine reference, while the content
presentation contract remains. All 186 source hashes, 253 payload hashes and ZIP
entries matched. Portable version: 0.1.0+portable.1062f13fdd22bb30. Archive SHA:
798e2181a06d2232ef6b73d728f57292f63e20f952dd043db77da489a867cfde.
