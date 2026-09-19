# Real workflow smoke

`test-workflow-live.py` is an explicit, opt-in release check. It creates a new
synthetic two-slide lesson and uses the real `run_workflow`, Codex app-server,
restricted author processes, Docker native renderer, host Chromium broker,
independent audience reviewers, and portable bundle builder. Only the website
transport and lease are in-process fakes. It never loads runner settings, claims
a website job, reads a review credential, or changes an existing task.

From the repository root:

```sh
pptx-agent/.venv/bin/python runner/test-workflow-live.py --out /absolute/new-proof.json
```

Prerequisites are the installed local Codex CLI/auth boundary, Docker renderer
image, plugin virtual environment, built interactive runtime, and Chromium
already required by the runner. A complete run makes real model calls. It can
take several minutes and prints phase changes and lease-check heartbeats.
Every invocation requires a new proof filename. Task folders, candidates,
rendered previews, journals, and private host traces remain available after
success or failure; their locations are recorded in the local proof.

The lesson uses editable native context for `count_next = count + 1` and a
declarative Increment/Reset region. The gate checks exact page count, native text,
exported Content Add-in structure, real click assertions for 0/1/2, host captures
in review packets, separate reviewer threads, resolved required findings,
reviewed artifact hashes, all portable ZIP checksums, public previews, and a
reusable delivery-ready checkpoint. Chromium verification is recorded separately
from desktop PowerPoint playback; this test does not certify desktop playback.

The final-upload race can be checked without model calls:

```sh
pptx-agent/.venv/bin/python runner/test-workflow-live.py --gate-only --out /absolute/new-gate-proof.json
```

That deterministic check runs the production `_run_job_locked` completion loop.
A fake API inserts new user input immediately before completion, rejects the old
revision with HTTP 412, and accepts only the reprocessed current revision. Model
results are synthetic in this isolated subtest. It checks that the old candidate
remains, the lease is not finished prematurely, and only the new revision is
delivered. The full run also verifies that a newly polled correction invalidates
an already reviewed delivery and raises `RevisionPending` at the host boundary.
The intentionally pending final correction belongs only to the retained synthetic
smoke task; no website queue receives it.

Proof records contain aggregate assertions and artifact hashes rather than full
conversation contents. A proof is successful only when `passed` is `true` and
every entry in `checks` is true. Failed evidence is retained and must not be
overwritten by a later run.
