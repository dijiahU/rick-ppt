# Native direct editor

The task workspace now separates direct controls from Agent comments. Direct saves
use a deterministic OOXML engine and the existing native renderer, with no model
calls and no task quota charge. The task remains complete while its native save
runs; the previous delivered PPTX remains available until atomic publication.

Supported controls: ordinary text (including inline editing), compatible Times
New Roman / SimSun font pair, size, bold/italic/underline, text color, horizontal
and vertical alignment; object position/size, drag/resize, rotation, slide centering;
shape fill/opacity and outline; connector outline and arrow endings; PNG/JPG picture
replacement and crop; ordinary table cell text; front/back layer order; safe object
deletion; solid slide background; draft undo/redo and local persistence. The object
list resolves overlapping targets. Complex text/formulas/charts/SmartArt retain
the scoped Agent route. Objects with anchored connectors do not expose movement;
animated or referenced objects do not expose deletion. Existing relationships,
animation targets, untouched parts and original files are preserved.

The canvas remains an actual PNG of the saved PPTX, with draft bounds and a focused
text editor on top. Draft controls do not claim to be a full fidelity live renderer.
Save performs one LibreOffice conversion and rasterizes only affected pages; it
reuses untouched saved previews. Browsers display the new native render afterwards.
Direct saves require a completed task, the current saved version and an online
native save worker. The source/output limit is 30 MiB; replacement pictures are
PNG/JPG up to 20 MB, with at most 10 per save.

`website/lib/native-canvas-client.ts` reads eligible native objects from a private,
checksum-verified PPTX in the browser. `native-edits.ts` validates the bounded
operation payload. Owner/admin opt-in, CSRF and current-version guards apply on
the task route. Immutable source keys and staged image ownership are enforced.

`native_edits` is a separate leased queue. `runner/native_edit_worker.py` services
one save at a time alongside the existing model pool. `native_editor.py` applies
operations directly to OOXML. Each attempt starts from the frozen source. The
finish route validates artifact/render hashes, retains old versions and atomically
updates the delivered result only if the task/source/lease still match. A stale
worker cannot overwrite a newer delivery. Failure leaves the original untouched.

A native save records a scoped revision containing the exact already-edited
baseline, marked `directSave`. It does not enqueue a model task. The existing
conversation transport downloads and verifies that baseline when the user next
requests Agent work; the author is instructed to continue from it and not replay
edits or restore an older checkpoint. User-facing conversation shows a concise
saved-edit receipt instead of internal JSON. Legacy preview routes also prefer the
current delivered canvas when the task is complete.

Validation: real SQLite/R2 handler tests cover permissions, admin opt-in, CSRF,
duplicate requests, concurrent saves, stale versions/leases, atomic publication,
retained history and baseline transport. Actual React DOM-emulator event tests
cover selection, text/table editing, drag, undo/redo and native saving. Python tests
check unchanged parts, native timing preservation, mixed run formatting, transformed
groups, protected deletion, shared-image isolation and empty text fields. A real
native save/render test uses synthetic slides, including picture crop, table cells,
text styling, movement and background changes; its receipt records zero model calls.
TypeScript and production builds pass. No browser was connected for actual browser
QA; LibreOffice rendering does not certify PowerPoint/WPS playback.

Run tests from the canonical repository:

```sh
python runner/test-native-editor.py
python runner/test-native-edit-render.py /absolute/local/test-artifacts
cd website
node scripts/test-native-edits.mjs /absolute/local/test-artifacts
node scripts/test-native-editor-ui.mjs /absolute/local/test-artifacts
```

The Python commands require the configured runner environment with lxml/Pillow and
the installed LibreOffice/Poppler tools. Synthetic test files are never submitted
as production user tasks.
