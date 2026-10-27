# Interactive authoring through the host broker

The Codex author process retains its task-only filesystem and disabled network.
The trusted runner executes Chromium and the loopback runtime through a file
request broker. No worker credential or website token enters the author prompt,
environment, scene, deck bundle, or browser.

## Author workflow

Use the normal approved PPTX CLI. The runner sets `PPTX_INTERACTIVE_PROXY` to the
task-local `interactive-proxy.py`, so existing `interactive attach`, `update`, and
`render` commands request host rendering automatically. Do not start a server or
browser in the author sandbox, and do not request broader permissions.

1. Unpack the task's input PPTX into its ordinary task-local workspace.
2. Write a schema-valid scene with local assets and a meaningful `testPlan`.
   Every attached scene must have at least one test with assertions.
3. Run `pptx.py -w WORKSPACE interactive attach --slide N --scene SCENE.json`.
   The host runs the scene, captures initial/test/reset states, and returns the
   normal renderer receipt; the CLI adds the Content Add-in and native snapshot.
4. Use `interactive update --scene SCENE.json` for changed scene content and rerun
   its tests. Author using native editable text/shapes for the surrounding deck.
5. Export to a new PPTX and write `delivery.json` with both fields:

```json
{"path":"/absolute/task/path/presentation.pptx","workspace":"/absolute/task/path/.pptx-agent/deck/workspace"}
```

The final host verification copies only matching, hash-verified sidecar content
from this workspace. It discards every author-written runtime test receipt and
independently reruns all attached scene test plans in the frozen review workspace.
The host then performs native validation/render/export and builds the portable
interactive bundle. An author-provided bundle or success claim is not proof.

By default all content is local. A scene may declare an external origin only if
it is also in the trusted runner's `interactive_network_allowlist`. Custom plugin
code requires a host-approved SHA-256 in `interactive_plugin_hashes` (`id: hash`);
a scene cannot approve its own executable plugin bytes. Built-in lazy code,
Three, ML, map and math packs do not require such custom-plugin approval.

## Host integration API

```python
broker = InteractiveHostBroker(cfg, job, trajectory=trajectory)
broker.poll()                     # frequent runner/app-server loop tick
broker.drain(tick=lease.check)    # wait for the current render before ending

verification = verify_frozen(
    cfg, author_job, delivery, frozen_root, frozen_workspace,
    tick=lease.check, trajectory=trajectory,
)
# Native validate --level 3 / review packet runs after this step.
# The protected frozen workspace original is the reviewed PPTX; the host receipt
# binds its exact SHA-256, so callers need no new untrusted artifact argument.
if verification["interactive"]:
    distribution = bundle_frozen(
        cfg, frozen_root, frozen_workspace, verification,
        "interactive-delivery", zip_output=True,
        tick=lease.check, trajectory=trajectory,
        native_service=lambda: bridge.render_requests(frozen_root, trajectory=trajectory),
    )
```

`verify_frozen` returns `interactive: false` for native-only decks without needing
an author workspace. Interactive results carry an in-memory host receipt bound
to the original frozen PPTX bytes and every native, scene, asset, capture and test file, plus the tested runtime
distribution/configuration/manifests. `bundle_frozen`
rejects missing/forged receipts and any later byte changes. It invokes the
existing bundle API, including the real native export/render gate. After a
runner restart, acquire a fresh frozen workspace and rerun verification; a
serialized author-visible receipt does not restore host authority.

Production frozen roots contain `soffice-proxy.py`; bundle export requires the
native service callback and checks that helper against the trusted runner bytes.
The host worker passes only that verified proxy to LibreOffice's adapter, keeping
native conversion inside the existing Docker isolation. Direct LibreOffice is
used only for controlled test roots without a task proxy.

The distribution result includes `bundle`, `zip`, `pptx`, `pptx_sha256`,
`exact_reviewed_pptx: true`, `runtime_verified` and
`powerpoint_playback_verified: false`. Browser rendering does not certify desktop
PowerPoint playback. The bundled `presentation.pptx` contains exactly the same
reviewed bytes as the standalone download. A fresh native export still validates
the frozen workspace; all its ZIP parts must match the reviewed presentation
before publication. Different part bytes fail delivery. When only ZIP packaging
metadata differs, the host publishes the original reviewed PPTX, updates
`deck/bundle.json` and every checksum, then verifies the final portable ZIP.
The intermediate native export remains in private host staging for inspection.

## File protocol and preservation

The helper writes `interactive-requests/<32-lowercase-hex>.request.json` atomically
and polls the corresponding reply. Requests have exactly the supported fields:

```json
{"version":1,"operation":"render","spec":"/task/scene.json","output":"/task/captures/generation-1"}
```

For imported scenes it also sends `deckRoot` and `deckId`. The broker can accept
`workspace` plus `scene` instead of `spec` for host integrations. Paths are scoped
without resolving away symlinks; every traversed directory uses `O_NOFOLLOW`.
Regular files are bounded and hashed while snapshotting. Arbitrary host paths,
source/asset traversal, symlinks, hard-linked inputs, inconsistent identities and
oversized inventories are rejected. Source bytes are copied into a private
host directory before the renderer runs, avoiding author mutation during tests.

Replies contain `{ "ok": true, "report": ... }` or a bounded error. The report's
`directory` and captures point only into the task. A normal existing capture
directory is preserved and a new `-host-<id>` generation is returned; this also
recovers a crash after capture publication but before reply publication. Existing
files and symlinks are never replaced. Only transient links created by the helper
or broker itself are removed during atomic publication.

Host subprocesses use only the configured trusted Python/plugin, a minimal
environment and a new process group with a timeout. Task proxy variables are
removed to prevent recursive brokering. Render requests are limited to 128 per
broker lifetime, 1,000 test actions per scene, 4,096 files / 512 MiB per snapshot,
and 256 MiB per input file. Host staging generations remain available for recovery
and investigation rather than deleting previous outputs.

## Verification

Run from the repository root:

```sh
pptx-agent/.venv/bin/python runner/test-interactive-host.py
```

The suite exercises real Chromium and the existing native renderer/bundle path,
plus scoped reads, symlink/hardlink rejection, protected-source checks, rejected
forged author receipts, failing test plans, post-verification tampering, and
native-only compatibility. The CLI integration test confirms that ordinary
`interactive attach` uses the broker without adding an author network grant.

Recorded result on 2026-09-20 after the runtime build was frozen: all 15 tests
passed in 21.547 seconds, including
real scene execution, ordinary CLI attach through the proxy, actual native bundle
export, exact reviewed PPTX byte identity, rejected differing native parts and
changed protected originals, and a separate loopback HTTP trap that received zero
requests from the code worker. Desktop PowerPoint playback is outside this suite.
