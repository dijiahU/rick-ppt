# New presentations vs editing an existing deck

The form submits `mode=create|edit`. Omitted mode remains `create` for existing clients.
Create requests require 5, 10 or 15 target slides. References and web research are optional inputs.
Edit requests require exactly one original PPTX; other reference formats remain supported. Their page-count field is ignored, and the visible form omits it.

For compatibility with the existing NOT NULL SQLite column, `jobs.pages=0` is reserved for edit requests with no fixed count. It never means a zero-slide deliverable. No historical rows or schemas are rewritten. Admin and progress views display task-dependent editing, not zero pages. Positive historical counts retain their original meaning.

The claim API translates the sentinel into `mode=edit,pages=null` and supplies the edit-scope contract before the user brief. This supports already-running bridge versions that copy the brief/pages but do not retain new fields. The stored user brief remains unchanged. Updated local request serialization also preserves mode explicitly. Editing should inspect the supplied deck, preserve unrelated slides and the original, and decide modification/addition counts from the brief. The final deliverable is a new full editable PPTX, not only the changed pages.

Verification: `node scripts/test-uploads.mjs`, `node scripts/test-task-mode-form.mjs`, existing quota/claim tests, TypeScript checks and production build. Tests use synthetic local data only; they do not claim or charge a real user task. Original deck semantic validity is still checked when the OOXML workspace is opened by the runner; upload validation alone only checks file limits/type signatures.

## Optional Fast tier

Both create and edit forms show an unchecked "Fast mode" checkbox after the
presentation-language choice. Only a checked box sends `fast: true` to
`POST /api/jobs`; requests without it are byte-for-byte the previous shape. The
route accepts only a boolean (multipart: `true`/`false`); other values are rejected
before quota is used. A Fast admission writes `task_options(job_id, service_tier='fast')`
in the same D1 batch as the job (created at runtime by `ensureModelAccounts()`, no
migration). A retry with the same request key and a different choice returns 409.
The claim response adds `service_tier: "fast"` only for those jobs; older workers
ignore it and run at their normal tier. The runner pins the choice in
`service-tier.json` on first admission (see `runner/README.md`).
Verification: `node scripts/test-fast-mode.mjs`.
