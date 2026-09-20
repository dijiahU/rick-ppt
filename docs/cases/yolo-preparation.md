# YOLO case preparation

Status: **prepared, not submitted**. Release smoke and CNN functional/native
checks have passed. YOLO admission can now proceed while CNN's remaining
independent audience reviews run; both cases still require their own complete
review and delivered-artifact verification before acceptance.

The [18-slide brief](yolo-prompt.md) retains the selected Ultralytics v8.2.0
implementation, numerical fixtures, commented code, partial-head optimization,
inference provenance requirements and honest fallback when genuine pretrained
ONNX inference is unavailable. It now incorporates findings from the CNN case:
label fixed baselines, bind changing numbers and units to the same result,
visually check dynamic mathematical text and retain the editor/Reset after
invalid parameter edits. This does not change the runtime or create a lesson
specific application.

The private v003 submission brief has 11,926 UTF-16 units against the 12,000
limit; the complete JSON body has 12,360 UTF-8 bytes. Payload SHA-256:
`4cf9a4a06132df3641039af9d29ae437b40c95aa32b81cf6f20dc9417a61981a`.
Brief SHA-256:
`2275e8db8ea40118a8b237a7f9556fba482caed0b9f9f3037ee047dd4612032d`.
Older payloads and the original website task remain unchanged.

An in-memory check against the actual schema found a boundary defect in the
earlier candidate admission SQL: inserting into a queue of 99 and repeating
the request at 100 evaluates a NULL status before the uniqueness conflict is
ignored. The new single `INSERT SELECT` filters capacity and existing identities
before insertion. It resolves the owner from the exact original task and title;
it does not change jobs, account settings or quotas already present.

Seven scenarios, applied twice each, passed: empty queue, queue at 99, full queue,
missing original task, wrong original title, reserved ID already used and an
existing owner/request key under another ID. Every existing row remains intact.
The SQL SHA-256 is
`5ec79b2e30b51e87e2ac3baa4c27950a856ac400b166dd46d9fd9d5c7b7190bb`.
Private proof `yolo-v003-migration-proof-01` retains the original failure, actual
schema fingerprints and 14 executions. A conditional no-op is not creation:
deployment must be followed by an exact task/owner/brief/status readback.

The separate [numerical reference](../../examples/yolo-reference/README.md)
passes 75 checks. Neither preparation result certifies a finished presentation,
a real pretrained detector or PowerPoint execution.

## Separate real-model feasibility result

The [pinned model compatibility probe](../../examples/yolo-reference/real-model.md)
completed on 2026-09-20: official YOLOv8n release weights were exported with the
verified Ultralytics v8.2.0 commit, executed with CPU ONNX Runtime, and run through
the existing production `ModelRunner` using its actual browser button and WASM
provider. **11/11 browser checks and 9/9 formal scene/asset import checks passed**;
both browser screenshots were reviewed. Precise source, original weight, exported
ONNX, input/output and evidence hashes are in the
[non-executable evidence manifest](../../examples/yolo-reference/real-model-observed.json).
The weight checkpoint internally records `8.0.0.dev0`; the v8.2.0 release and
exporter pin must not be presented as its training version.

The independent scalar reference remains a separate 75-check result. Actual
single-image model execution is now evidenced, but the **formal YOLO task is
still not submitted**, and the prepared **host static asset handoff has not been
executed**. No final lesson, native fallback, export/bundle or desktop PowerPoint
acceptance follows from the 11+9 checks. CNN's 194 frozen-scene tests, 679
assertions, additional 95 interaction checks and all-page native inspection
precede YOLO admission. Running the remaining independent CNN reviews alongside
YOLO creation changes scheduling, not either case's final acceptance criteria.

The prepared private directory contains only static ONNX/image/JSON assets,
provenance, exact hashes and declared licenses; normal import requires no
attachment program execution. A future owner-scoped task handoff must clearly
identify these as host-provided test assets. The website still does not allow
`.onnx` or `.pt` uploads, and the measured ONNX size of 12,823,520 bytes exceeds
the 10 MiB attachment limit. This preparation changes neither those rules nor
the runtime, runner, release or website, and it does not encode or rename a model
to evade the attachment rules.
