# YOLO case preparation

Status: **prepared, not submitted**. The CNN delivery and acceptance gate remains
required before creating the second website task.

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
