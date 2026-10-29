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
