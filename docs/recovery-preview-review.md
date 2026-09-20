# Candidate previews during recovered review

A same-version recovery can reuse a completed author receipt and skip research
and authoring. Its new public `Reporter` starts with no page previews. The host
now publishes the pages from each successful frozen validation before starting
independent review, so these recoveries show the candidate while review runs.

Each queued PNG uses the frozen root and the current outline's `page_version`.
The existing Reporter still checks scoped paths, PNG headers and dimensions,
deduplicates uploads, and removes queued pages whose outline content changes.
Failed synchronization remains nonfatal and keeps valid pending uploads for
retry. Publication calls `review_tick` between pages, so lease loss or new input
can interrupt it before review proceeds.

Both review statuses reset to `pending` for each frozen candidate. Only the
independent reviewers change those verdicts. Publishing a preview does not
complete a journal stage, apply user feedback, authorize delivery, or alter the
exported PPTX. A failed freeze publishes nothing; a later review failure leaves
the candidate visible without claiming it passed. Final delivery continues to
use the exact reviewed frozen artifact.

The regression tests use a real durable author receipt, a real Reporter and the
actual workflow control flow, with synthetic rendering and reviewer boundaries.
They cover recovery without rerunning authoring, preview availability before a
review timeout, failed validation, new input during publication, and delayed
uploads across an outline revision:

```sh
python runner/test-content-workflow.py
python runner/test-progress.py
```

This host change takes effect in a newly started worker. It does not hot-reload
an active task or require changes to website state, plugin runtime or journals.
