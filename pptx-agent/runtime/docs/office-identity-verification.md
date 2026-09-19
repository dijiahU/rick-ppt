# Office identity decoding correction

The Office Settings API returns already deserialized values. The former
`identity()` implementation parsed every string again, so formally valid scene
IDs `null` and `false` became missing identities. The corrected reader preserves
all four string fields verbatim and requires `schemaVersion` to be the supported
integer number `1`. Missing/empty/wrongly typed fields produce a field-specific
error. Scene ID syntax, UUID/hash integrity and fetched scene validation remain
the responsibility of their existing validators; preserving a string such as
`123` here does not waive the scene schema's separate ID rules.

There is **no legacy raw-JSON decoding mode**: a numeric schema version supplied
as the string `"1"` is rejected; a string containing quote characters is retained
as that exact string, not decoded again. OOXML properties still contain the
normal serialized JSON values—Office performs that single deserialization before
`Settings.get` returns them. This follows Microsoft's
[Settings API contract](https://learn.microsoft.com/en-us/javascript/api/office/office.settings?view=powerpoint-js-preview).

Attachment already writes the five identity properties into the PPTX. Reading
them at startup does not require `saveAsync`. The existing explicit
`saveIdentity` helper is unchanged and is not called automatically. Mutated
settings require `set`/`saveAsync` and a subsequent document save. Slider values,
edited code and uploaded files remain session state; authoring recovery remains
the workflow journal's responsibility. See the updated
[manual checklist](../../docs/manual-powerpoint-verification.md) and Microsoft's
[persistence guidance](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/persisting-add-in-state-and-settings).

## Validation and frozen build

`tests/office-settings.test.ts` adds 25 mock-host checks: string preservation,
invalid fields/version, delayed `Office.onReady`, standalone bypass, missing
Office.js, wrong host, no startup writes, explicit successful asynchronous save
and propagated save errors. These are API-boundary unit tests, **not actual
PowerPoint execution**.

Commands run from `pptx-agent/runtime`:

```sh
npm test -- --reporter=dot
npm run build
npm run test:e2e
npx playwright test --config tests/browser/production.config.ts
npx playwright test --config tests/feature-packs/production.config.ts
```

All passed: **79 unit tests** across four files, production build/TypeScript/size
gate, **23 combined browser cases** (15.2 s), **three production
diagnostic/performance cases** (9.6 s), and **eight production feature-pack
cases** (6.7 s). The latter two use the actual built runtime and loopback-server
CSP. They do not replace the mock-only qualification of the Office API tests.

The production build includes TypeScript checking and the 300,000-byte core gzip
gate. Its manifest was written at **2026-09-19 21:37:39.673 UTC**, core gzip is
**126,663 bytes**, and strict runtime identity is:

```json
{
  "sha256": "fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de",
  "files": 96,
  "configuration": "7653f243bdd5d4dc6f1b4ba6f4f3d2f7ebbddf009a759299ad15d1a6a779716a"
}
```

The earlier diagnostics/performance report and six-region technical showcase
explicitly identify runtime `1f4b66ba…75ae3`. Those files and private artifacts are
preserved unchanged as evidence of that build; their receipts are not presented
as receipts for this newer runtime. Actual PowerPoint property injection,
slideshow behavior and save/reopen remain unverified.
