# Release smoke gate — 2026-09-20

The functionality gate passed before either teaching case was admitted. This
record distinguishes actual model execution, deterministic regressions, browser
execution, native rendering and the still-unverified PowerPoint desktop host.

## Baseline frozen runtime

- Source fixes: `a2f1bce`; runtime built at 2026-09-19 21:11:48 UTC.
- Runtime SHA-256: `1f4b66baaf34bfd80dbf77dc29969cf43c8bfe1cb599d0b1644f6659e0575ae3`
  across 96 distribution files.
- Configuration SHA-256: `7653f243bdd5d4dc6f1b4ba6f4f3d2f7ebbddf009a759299ad15d1a6a779716a`.
- Core gzip: 126,626 bytes, below the 300,000-byte gate; optional local assets
  approximately 40.48 MiB. The Monaco shared chunks are included in pack accounting.
- Linux GitHub verification job passed:
  https://github.com/dijiahU/rick-ppt/actions/runs/35469941496.

## Executed regression and production checks

Commands are relative to the repository, except where a directory is stated.
Use the repository Python 3.11 dependency environment.

| Command / scope | Actual result |
| --- | --- |
| In `pptx-agent`: `.venv/bin/python -m pytest -q --tb=short` | 134 passed in 79.61 seconds; native XML, sidecars, receipts, hooks, actual bundle/reopen and rendering checks |
| In `pptx-agent/runtime`: `npm test` | 54 Vitest checks passed |
| Same directory: `npm run build` | TypeScript, schema compilation, production build, local pack assets and gzip size guard passed |
| Same directory: `npm run test:e2e` | 23 actual Chromium checks passed: 12 core semantics, three diagnostics/performance and eight packs |
| Same directory: `npx playwright test --config tests/browser/production.config.ts` | Three production diagnostics/performance checks passed |
| Same directory: `npx playwright test --config tests/feature-packs/production.config.ts` | Eight production-CSP checks passed with actual Monaco, JS/Pyodide, ONNX, Three, map, math and custom plugin behavior |
| `pptx-agent/.venv/bin/python -m unittest discover -s workflow -p 'test_*.py'` | 60 passed |
| `pptx-agent/.venv/bin/python runner/test-conversation.py` | 34 passed |
| `pptx-agent/.venv/bin/python runner/test-recovery-workspace.py` | Seven passed |
| `pptx-agent/.venv/bin/python runner/test-content-workflow.py` | Seven passed |
| `pptx-agent/.venv/bin/python runner/test-outline-interactive.py` | Five passed |
| `pptx-agent/.venv/bin/python runner/test-page-count.py` | Three passed |
| `pptx-agent/.venv/bin/python runner/test-acceptance-migration.py` | Five passed; additive, idempotent same-owner task admission |
| `pptx-agent/.venv/bin/python runner/test-interactive-host.py` | 15 passed, including exact reviewed PPTX bytes in the final bundle and rejection of changed native parts |
| In the actual website checkout: `node --experimental-strip-types --test scripts/test-*.mjs` | 30 tests in 15 files passed; TypeScript and production build also passed |

These counts overlap in scope and are not summed into a misleading single total.
Private command logs remain under `.work/interactive-runtime-20260920/`, including
`python-final-gate.log`, `runner-final-gate/results.json` and `website-node-final.log`.

## Actual workflow and recovery

`runner/test-workflow-live.py` ran real Codex research, authoring and three
independent review contexts, then independently validated/rendered two native
slides and the attached scene, froze output, assembled the bundle and exercised
the real runner's late-input delivery fence. All 20 checks passed in 20m55s.
The website transport was intercepted by the harness; no real account job or
quota was changed by this smoke. Private record: `workflow-live-proof-01.json`.

After fixing ZIP-metadata byte identity and freezing the final runtime,
`--reverify-reviewed` reran exact-candidate validation, all scene assertions and
native rendering without making another model or review call. Eight checks
passed. The six new scene captures are byte-identical to the previously reviewed
captures. This is evidence equivalence, not a claim that another reviewer ran.
Records: `workflow-live-reviewed-bundle-proof-02.json` and
`workflow-live-scene-equivalence-02.json`. Reviewed/delivered PPTX SHA-256:
`d7c7772e3724d6e0d4596103f8a50bc62b3e249ed1782fe28c51394294984ba9`.

Separate real app-server exercises verified same-turn feedback, interruption,
server restart, original-thread resumption and restored work in a new directory.
The old directory remained inaccessible to the recovered model. A live phase
received ordinary chat, a revision and an attachment while native Docker
rendering remained available. Outside-task filesystem and shell network access
were denied. Records: `app-server-live-proof-01.json`, `phase-live-proof-01.json`
and `recovered-thread-workspace-proof-01.json`.

The [technical showcase](../pptx-agent/runtime/docs/technical-showcase.md) adds
four native slides, six regions and 18 cases / 34 assertions through the public
CLI, export/reopen and a served portable bundle. The final native pages were
visually inspected; an identified Stop-label crop was corrected. Actual pointer,
keyboard and edited-source execution are covered by the browser checks, rather
than inferred from test JSON.

## Deployment and limits

The first real CNN claim exposed an installed-version boundary not covered by the
initial `0.2.0` fixtures: the generic journal ID validator rejected the legitimate
`+codex` suffix. No authoring began. A separate bounded version validator and
installed-version startup preflight now cover create/checkpoint/reopen/recover,
and empty failed-initialization directories can be retried without deleting them.
The expanded workflow suite passes **70 checks**, plus runner trajectory six,
recovery seven and conversation 34. Damaged histories still fail closed. This
repair is recorded in the same new case's history and does not rewrite the prior
user task. The final Office identity patch receives its own runtime gate.

The final Office patch preserves already-deserialized Settings strings instead
of parsing them a second time; legal IDs such as `null` and `false` now retain
their identity. This changes no session-persistence promise. The new frozen
build at 21:37:39.673 UTC has fingerprint
`fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de`
(96 files, unchanged configuration hash) and core gzip **126,663 bytes**.
It passes **79 unit, 23 combined browser, three production diagnostics and eight
production pack checks**, plus TypeScript/build/size. Details are in
`pptx-agent/runtime/docs/office-identity-verification.md`.

Fresh exact-candidate host verification on this build passes eight checks in
`workflow-live-office-bundle-proof-03.json`. All six scene captures and both
native page PNGs are byte-identical to the previously reviewed version. Existing
full-workflow and showcase proofs remain bound to their recorded builds; they
are not relabeled as new model reviews or new-runtime receipts.

Website version 23 is published successfully with conversation, attachments,
recovery, interactive outline metadata and an atomic late-revision delivery
fence. Local desktop/mobile UI checks verified sending/uploading, applied status,
reload/deduplication, normal chat and same-task resume against the actual routes.

Plugin `0.1.0+codex.20260919214127` is installed and staged immutably; all 17 older
cache versions and the old marketplace source are preserved. Installed doctor,
hook compatibility and narrow filesystem/network isolation checks passed. The
native Docker render smoke passed on the identical frozen runtime. The final
cachebuster additionally includes the evidence documents and showcase script.

## CNN-discovered Monaco correction

Source `8dd1e9f` fixes highlighted multiline editing. Synchronous decoration
updates reentered Monaco's content-event delivery; its automatic indentation also
published thousands of intermediate code-change events. The code pack now
coalesces both outside that stack and publishes the final buffer once. The
runtime's 2,000-action safety limit is unchanged.

The single production build at `2026-09-19T23:01:52.400785Z` has 96 files and
fingerprint `be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
It passed 79 unit tests, 24 combined browser tests, nine production feature-pack
checks and three production diagnostics. An independent learner-input replay of
the preserved CNN draft passed 197 assertions with 24 captures, including real
JS/Python keyboard edits, Stop, errors, Reset and zero-epoch training. The exact
8,828-character synthetic input buffer that previously produced 3,805 page errors
now produces zero. Real clipboard paste preserves all 2,781 source characters
and remains executable. This distinguishes composition-style input from paste;
it does not promise that auto-indented synthetic input equals its intended text.

Fresh host/native/portable verification of the previously reviewed two-page
smoke candidate passed all eight checks on this build. The native PPTX remains
byte-identical to the reviewed artifact. This is fresh renderer and packaging
evidence, not another model-review run or final CNN acceptance.

The installed and staged release is `0.1.0+codex.20260919230549`. Plugin validation,
doctor, filesystem/network isolation and installed-version journal preflight
passed. All 18 older cache versions are retained. The installer removed them,
so their complete backups restored the original hooks and files; subsequent
Python use regenerated 24 bytecode files, while all non-bytecode source files
still match. Original bytecode also remains in the backup. After startup checks,
the replacement worker resumed the same CNN task at 23:14 UTC with this immutable
release. All eight selected originals/restored files matched. Changed plugin
identity invalidates earlier stage receipts, so final case evidence must be
regenerated against this build.
At 21:25 UTC the old idle worker drained normally. After the startup and Office
identity corrections, worker 4473 passed the installed-version recovery preflight
and began CNN research at 21:42 UTC. `worker-handoff.json` and
`worker-handoff-office.json` record both transitions; the
private worker log contains no task credentials. A process-scoped `caffeinate`
keeps the Mac awake only while this worker runs; no login service was installed.

Teaching cases run only after that handoff. Their prompts and acceptance
contracts are in `docs/cases/`; preparing a prompt does not pass a case.

PowerPoint desktop startup, slideshow focus and Office settings persistence are
**NOT RUN**: the desktop automation connection is unavailable. Browser behavior,
native LibreOffice rendering and OOXML fixture matching do not prove those host
behaviors. Windows and Office web are also unverified. See the separate manual
checklist and compatibility matrix. All independent work continues.
