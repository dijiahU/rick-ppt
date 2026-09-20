# Recovering completed independent review passes

The host now saves each validated independent review report immediately. If a
later pass fails, a subsequent worker attempt can reuse matching completed
passes instead of discarding their reports and reviewing those inputs again.
The three roles remain separate: first audience content review, content review
with the brief and original attachments, and visual review.

This is **completed-pass recovery**, not unfinished-turn continuation. An
unfinished pass is reviewed again by a new independent reviewer. This change
does not interrupt, resume, restart, or hot-reload an already running worker.

## Conditions for reuse

`runner/review_sessions.py` keeps its records under the host's private
`records/review-sessions/` directory, outside the author workspace and the
plugin directory exposed to the model. The existing worker task lock remains
the concurrency owner. There is no journal schema change or author-supplied
approval receipt.

A reusable pass must match all of these inputs:

- Task ID, input revision from the journal, and installed plugin version.
- Exact frozen PPTX bytes and every rendered native page's bytes.
- Names, byte lengths, and SHA-256 hashes of every review-packet file.
- Actual runtime distribution, configuration, manifests, plugin manifest, and
  content/visual review-reference files.
- Reviewer role, exact prompt, and all files supplied to that role. These include
  the first-view report, request, source index, and original attachments where
  appropriate.

The shared prompt explicitly selects the configured Python interpreter for
inspection scripts written by the reviewer. It still prohibits executing code
supplied by the presentation or its sources and modifying the supplied inputs.
Interpreter/prompt changes invalidate reuse. A blind reviewer receives neither
the request nor the author outline/source notes; cached blind reports do not
introduce those files into its isolated directory.

The host still freezes and independently validates the candidate on recovery.
It compares exact regenerated evidence bytes; it does not normalize away image
or inventory differences. A changed capture, even on the same slide, prevents
reuse. A valid first-view report is serialized identically when first produced
and when loaded from cache, avoiding a false mismatch in the next pass.

A read-only check of seven preserved real freeze outputs found no generated
absolute workspace paths or timestamps in their inventories. Two 20-page CNN
freezes had byte-identical PPTX and inventory files and the same 97-file runtime
fingerprint. However, 24 of their 287 packet files differed: all were interactive
PNGs, with 6–678 actual pixels differing per image. This pair correctly produces
a cache miss. This change therefore does **not** claim to eliminate every repeat
of that CNN review. Reusing the original frozen evidence instead of regenerating
it would require separate implementation; comparisons here remain exact.

## Completion and stored evidence

Each attempt records its role, canonical isolated directory, phase/log identity,
client message ID, thread ID, turn ID, and last observed terminal status. Records
are newly created files with a SHA-256-linked sequence; reports are separate
immutable files whose hash and byte count are committed in the validated entry.
Each publication writes and flushes a private `.pending-*` file, then atomically
links it to an exclusive final name and flushes the containing directory. Only
the publishing call's own temporary is cleaned; older temporary files, records,
and roots are retained. Recovery ignores an unpublished temporary or empty
attempt directory. A fully published record left linked to its temporary after
a crash is readable and still checksum-verified. Corrupt published records are
never treated as harmless temporary writes.

Only the matching `turn.completed` event with `status: completed`, followed by
the existing strict `REPORT_SCHEMA`/page/finding validation, can commit a
reusable report. The host rechecks frozen inputs and the reviewer's supplied
file copies before committing it. Loading a cached report verifies the record
chain, report checksum, current input identity, and report schema again.
Tampering fails closed rather than silently accepting or repairing a receipt.

Generic execution errors and progress messages are not terminal events or
approval. An unsuccessful attempt keeps `report_status: pending` and the last
observed turn status; an unknown/in-progress status is not relabeled as
interrupted merely because the local process exited. A hard crash can leave
the attempt's execution status as `running`, but its report remains pending
and is never reused. On retry that incomplete role receives a new isolated
root and thread. Completed reports in other matching roles remain reusable.

Cache reuse is recorded as `reused_validated_report` in host stage/thread audit
metadata. It neither invents a new model execution nor repeats the original
token usage. Required findings remain required findings when reused; the cache
does not convert a correction request into a passing review.

## Explicit limits

- There is no same-thread continuation, partial screenshot progress recovery,
  forced turn interruption, or terminal-status reconciliation in this change.
- Existing pre-ledger reports are not automatically adopted. They lack the
  complete identity and terminal receipt required for safe reuse.
- Recovery selection during an unfinished `content-revision` or `repair` phase
  remains a separate workflow concern. This cache does not change that routing.
- A restarted process still needs fresh host interactive verification before
  bundling. The in-memory `_VERIFIED` authorization is not serialized or reused.
- Browser/static evidence remains distinct from actual PowerPoint playback;
  completed-report reuse adds no desktop-playback claim.

## Verification

Use the repository's prepared Python environment:

```sh
pptx-agent/.venv/bin/python runner/test-review-sessions.py
pptx-agent/.venv/bin/python runner/test-content-workflow.py
```

The first suite exercises real filesystem receipts and the actual `review()`
control flow with synthetic reviewer responses. A protocol-boundary test also
drives the actual `Execution.phase()` lifecycle. It covers second-stage failure
and first-stage reuse, all-role reuse, PPTX/packet/native/revision/task/runtime/
configuration/prompt changes, report and terminal-record tampering, blind-review
isolation, in-pass input mutation, progress text, and missing terminal events.
No website, live task, model service, browser or native renderer is invoked by
these tests.

Validation for this change: **25 review-recovery tests and 11 content-workflow
tests passed** using the commands above; `git diff --check` also passed.
