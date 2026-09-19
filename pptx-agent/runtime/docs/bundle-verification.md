# Bundle export and recovery verification

Verified on macOS, 2026-09-20, using the repository Python 3.11 environment,
Chromium, LibreOffice and Poppler. These checks exercise generated OOXML,
native static rendering and the standalone interactive runtime. They do not
establish PowerPoint desktop playback or Office settings round-trip behavior.

## Commands and results

From `pptx-agent/`:

```sh
.venv/bin/python -m pytest tests/integration/test_interactive_bundle.py -q --tb=short
```

Result: **7 passed in 12.99 s**. From the repository root:

```sh
pptx-agent/.venv/bin/python runner/test-recovery-workspace.py
```

Result: **5 tests passed**. The first command creates its own blank presentation
workspace and real browser evidence; the second copies actual native workspaces
to test path relocation and preservation. Neither uses an existing website job.

## Export and portable runtime evidence

The bundle integration fixture follows this sequence:

1. Unpack the bundled blank PPTX and retain hashes of the source and protected copy.
2. Attach a declarative scene with an Increment button, bound text and Reset.
3. Run its two test cases in Chromium, assert state and rendered text, and save
   initial, changed and reset captures.
4. Validate both native OOXML and interactive assets/receipts.
5. Export with an actual LibreOffice PDF and Poppler page render, then reopen the
   exported PPTX and validate it with the scene sidecars.
6. Assemble a new portable directory and ZIP; compare native part manifests,
   scene sidecar manifests and both original PPTX hashes before and after.
7. Start the copied runtime through `start.command`, load its served preview in
   Chromium, click Increment and assert its state changed to 1.
8. Stop that runtime through `stop.command` and verify that an unrelated process
   remains running.

The workspace now records the durable bundle presentation as `latest_output`
and the directory as `latest_bundle`. Native and interactive dirty baselines
match the final preserved source trees; a subsequent refresh remains clean.
An intermediate export is retained under the workspace output directory, so an
assembly failure cannot leave `latest_output` pointing into a removed staging
directory. Assembly compares the native, sidecar and runtime source manifests
again before publication.

Existing bundle directories and ZIP files are rejected without overwriting.
Separate corrupt copies of the PPTX, scene JSON and runtime HTML are rejected by
both verification and start before a server launches. The inventory and the
bundle PPTX hash are verified together. The tests check ZIP integrity as well.

The portable controller stores its identity and secret outside the served bundle
in a private per-bundle cache. Duplicate start returns the existing matching
instance. Stop authenticates the instance through its loopback control endpoint;
it does not terminate arbitrary PIDs or processes found by name. A deliberately
wrong PID in a temporary control record is rejected, and the unrelated process
survives. The browser test also verifies that a guessed private state URL is 404.

The recorded run artifacts are under:

```text
/private/var/folders/49/2sppyd_91mb_h1ddx8tdwqfr0000gn/T/pytest-of-rick/pytest-44/real-interactive-bundle0/
  acceptance-evidence.json
  served-bundle-after-click.png
  authoring/blank/interactive/renders/bundle-example-6779867826/
  authoring/blank/renders/render-m6hb63v4/
  review bundle v1/
  review bundle v1.zip
```

These are local test artifacts; pytest may eventually rotate its temporary
directories. Rerunning the command generates a fresh complete evidence set.
The receipt explicitly records `runtime_verified: true` and
`powerpoint_playback_verified: false`.

## Workspace relocation after journal recovery

Native workspace `state.json` contains absolute `workspace`, `source`, output and
render paths. Copying its files alone makes `Workspace(...)` reject the restored
location. The host must call
`runner.recovery_workspace.relocate_task(old_root, new_root, cfg)` after a verified
checkpoint restoration and before reusing pipeline phases.

The helper verifies every protected source hash before any active JSON write,
maps only known workspace/receipt path fields inside the old task, and preserves
the original JSON bytes under a separate recovery backup directory. If an old
source is unavailable, it uses the verified protected copy in the new workspace.
Missing outputs, native renders or runtime captures invalidate their receipts;
they are not reported as passing. Unrelated prose, JSON and historical snapshots
are retained unchanged. Tampered restored originals, unsafe paths and symlinks
are rejected. Running relocation a second time is idempotent.

The five tests cover successful real-workspace reopening, exact backup bytes,
unchanged old-task hashes, missing-file invalidation, tampered restored original,
outside receipt paths, symlinks and unchanged historical snapshots. The parent
workflow still needs to call the helper and checkpoint the relocated state; this
document does not claim that source-level helper tests prove that integration.

## Boundaries of this evidence

- The portable lifecycle test uses explicit local HTTP and an ephemeral port.
  TLS/certificate checks are recorded separately by the runtime server work.
- Windows PowerShell launchers are supplied but have not been run on Windows.
- This test does not open the Content Add-in in desktop PowerPoint, verify
  slideshow interaction, or prove injected settings survive PowerPoint save/reopen.
- Successful source-manifest comparisons prove preservation for this run; a
  concurrent-mutation race was not injected by this test suite.

## Follow-up fixes and tests

The dirty-interactive Stop hook now creates its fresh bundle outside the workspace
home, avoiding recursive source inclusion. Its result lists the PPTX, bundle and
separate runtime/desktop verification states. The real Stop path plus the seven
original bundle tests and twenty hook/CLI tests pass: **28 tests**.

Recovery now retains author `delivery.json` bytes and resolves only its `path` and
`workspace` fields in memory against host-owned recovery history. Two successive
restorations retain reusable author artifact hashes; unrecorded roots and traversal
are rejected. The expanded relocation suite passes **7 tests**.
