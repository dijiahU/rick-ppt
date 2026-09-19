# Release smoke gate — 2026-09-20

The functionality gate passed before either teaching case was admitted. This
record distinguishes actual model execution, deterministic regressions, browser
execution, native rendering and the still-unverified PowerPoint desktop host.

## Frozen runtime

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

Website version 23 is published successfully with conversation, attachments,
recovery, interactive outline metadata and an atomic late-revision delivery
fence. Local desktop/mobile UI checks verified sending/uploading, applied status,
reload/deduplication, normal chat and same-task resume against the actual routes.

The installed immutable plugin and worker handoff are recorded in the execution
plan. Teaching cases run only after that handoff. Their prompts and acceptance
contracts are in `docs/cases/`; preparing a prompt does not pass a case.

PowerPoint desktop startup, slideshow focus and Office settings persistence are
**NOT RUN**: the desktop automation connection is unavailable. Browser behavior,
native LibreOffice rendering and OOXML fixture matching do not prove those host
behaviors. Windows and Office web are also unverified. See the separate manual
checklist and compatibility matrix. All independent work continues.
