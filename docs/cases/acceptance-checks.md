# CNN / YOLO acceptance contract

These are **planned checks**, not completed results. The mathematical fixtures and
the tiny CNN recipe were checked independently during brief preparation. No
website job, presentation, final scene or Office playback was generated or tested
by preparing these files. Case execution begins only after the release smoke gate.

## Gate and evidence

1. Parent records the release commit, runtime/build asset hashes, smoke commands,
   results and capability limitations. All required functionality and smoke tests
   pass before submitting either website case.
2. Submit CNN with the [CNN brief](cnn-prompt.md), English and 20 slides. Preserve
   the prior website task and every earlier output. Record the new task ID,
   account owner, exact prompt, outline revision and timestamps without credentials.
3. Review CNN's native and interactive artifacts, then submit YOLO using its
   [brief](yolo-prompt.md), English and 18 slides. Reuse the release under test.
   After CNN's actual functional tests and native inspection pass, its remaining
   independent audience reviews may continue alongside YOLO creation. Neither
   case is accepted until its own reviews and delivered-pair checks pass.
4. Retain native `.pptx`, matching interactive workspace, portable bundle,
   commented code, model/data provenance when applicable, testPlan reports and
   initial/intermediate/reset captures. Record failures and fixes against the
   artifact revision they actually tested. Fixes require a new matching snapshot.
5. Host freeze verification must independently rerun the scene plans from exact
   frozen scene/assets; an author-written `runtime_verified` is not evidence.
   Native export validation and content/visual reviews also apply.

Use one result table per case: check ID, artifact/scene hash, action, actual value,
expected value/tolerance, pass/fail/unverified, report/capture path and reviewer.
Do not mark a planned assertion green just because its expected answer appears
in a scene file. Check the visible explanation and the actual dependent state.

## Implementable scene contract

The following state paths and node IDs are a suggested authoring contract. They
are not new reserved runtime fields. The author may adapt IDs, but must retain a
mapping in the delivered case report and equivalent checks. Each scene has at
least one changed-input test and a nonempty assertion list. Split tests by actual
scene attachment; do not pretend cross-slide state is automatically shared.

Use the implemented `testPlan` action types (`click`, `slider`, `input`, `select`,
`toggle`, `drag`, `keyboard`, `seekTimeline`, `dispatch`, `snapshot`, `restore`,
`resize`, `wait`). Numeric `state` assertions support absolute `tolerance`;
arrays use exact equality or elementwise scalar checks. `text` uses
`text_content`, so SVG text is testable. Runtime plugin actions are awaited;
dispatching `code.run` can therefore assert real resulting values without a guessed
sleep. JavaScript returns an object; Python's last expression can return a dict.
With `resultPath="run"`, returned program values are under `run.result` and
successful execution is `run.status == "done"`.

Illustrative plan fragment (adapt IDs/state to the actual scene):

```json
{
  "name": "cnn-edit-rerun",
  "reset": true,
  "actions": [
    {"type":"dispatch","actions":[
      {"type":"plugin","name":"code.setCode","target":"cnn-editor",
       "args":{"code":"const X=[[1,2,3],[4,5,6],[7,8,9]]; const K=[[2,-1],[2,0]]; const out=Array.from({length:2},(_,y)=>Array.from({length:2},(_,x)=>K.reduce((s,row,i)=>s+row.reduce((t,w,j)=>t+w*X[y+i][x+j],0),0))); print(JSON.stringify(out)); return {output:out};"}},
      {"type":"plugin","name":"code.run","target":"cnn-editor"}
    ]}
  ],
  "assertions":[
    {"type":"state","path":"run.status","equals":"done"},
    {"type":"state","path":"run.result.output","equals":[[8,11],[17,20]]},
    {"type":"text","target":"output-first-cell","contains":"8"}
  ],
  "capture":true
}
```

Programmatic `code.setCode` proves a changed source is executed. A separate
browser UI check must type into Monaco using its accessible editor surface, run
with the visible Run button and observe changed output. Clicking a fake code
picture, finding a `<textarea>`, or reading a precomputed result is insufficient.
Keep source and all generated fixture data local; do not require user uploads.

## Common requirements

| ID | Action / inspection | Acceptance |
| --- | --- | --- |
| G01 | Inspect actual native slide XML and rendered slides. | Exact 20/18 page count; native editable titles, context and equations remain outside each live region. No full-deck screenshot substitution. |
| G02 | Validate and inventory every attached scene. | Matching instance/scene/hash, declared packs, bounded local dependencies; no topic React app, raw eval in slide expressions, unapproved custom plugin or required public CDN. |
| G03 | Run one meaningful changed-input test per scene. | Numerical/geometry/text consequence is visible, correct and derived from the changed input. |
| G04 | Seek a mechanism animation at start, middle and end, then reset. | Patch/box/gradient state is correct at each point, timeline/state returns to initial, and code-line explanation remains synchronized. Replay is deterministic. |
| G05 | Edit actual Monaco source, run, then reset code. | Worker output changes; the diagram uses that output; reset restores original source and clears output. Code Stop interrupts an active run. Hostile/unbounded execution boundary remains covered by release smoke tests. |
| G06 | Exercise a 1280×720 and an 800×600 browser viewport, keyboard controls and reduced motion. | Labels and hit targets stay usable; no clipped scientific symbols or hidden mandatory controls. Reduced motion preserves an understandable endpoint/step path. |
| G07 | Compare initial, changed and reset captures with static PowerPoint renders. | Static fallback has the worked example and takeaway, not an empty/loading editor. Long code remains readable through excerpts/scrolling and a complete source artifact. |
| G08 | Inspect new page errors, runtime errors and failed local assets during normal use. | No unexplained errors, invalid JSON paths or missing WASM/font/worker assets. Genuine capability absence is visible and reported. |
| G09 | Unpack portable bundle and launch its documented local entry point. | Native PPTX, scenes, assets, optional packs and hash manifests match; required lesson code works without external network. |
| G10 | Review conceptual statements and citations independently. | All symbols defined; source version named; synthetic results and genuine model results clearly identified; no invented performance numbers. |

## CNN numerical and interaction checks

Use the fixture in the CNN brief; default scalar tolerance is `1e-9` for original
small arithmetic, `1e-6` for cross-runtime training outputs. Exact integers and
array shapes should be checked exactly.

| ID | Scene / action | Expected evidence |
| --- | --- | --- |
| C01 | `cnn-convolution`: default fixture; step across patch indices 0–3. | Output `[[7,9],[13,15]]`; patch sums `7,9,13,15`, active patch coordinates `(0,0),(0,1),(1,0),(1,1)`. |
| C02 | Change K[0][0] from 1 to 2 using the control and separately via actual code editing. | Output `[[8,11],[17,20]]`; changing source really reruns the worker. Reset returns C01. |
| C03 | `cnn-shape`: n5/k3/p0/d1; stride1→2; then stride1/p1. | Spatial sizes `3→2→5`; valid patch positions and matrix geometry agree. Invalid parameter combinations produce explanatory validation, not negative grid dimensions. |
| C04 | `cnn-channels`: Cin3/Cout4/k3 with bias; change input spatial size. | Parameters 112 before/after spatial resize; output channel count 4. Contributions sum across all three input channels. |
| C05 | `cnn-relu`: preactivations `[-2,0,3]`, upstream `[1,1,1]`. | Forward `[0,0,3]`, backward `[0,0,1]` under explicitly stated derivative-at-zero convention. |
| C06 | `cnn-pool`: window `[[1,3],[2,4]]`; max versus average; upstream gradient 1. | Max4 routes gradient only to bottom-right; average2.5 gives every input gradient.25. Tie policy is stated and tested if editable ties are allowed. |
| C07 | `cnn-receptive-field`: advance conv3/s1, pool2/s2, conv3/s1. | Receptive fields `[3,4,8]`, jumps `[1,2,2]`; input highlight covers corresponding region. |
| C08 | `cnn-softmax`: logits `[2,1,0]`, target0; then add1000 to every logit. | Probabilities and CE match the brief before/after; no overflow/NaN; gradient sum within `1e-12` of0. |
| C09 | `cnn-backward`: accumulate the four patches with dZ all1. | Final dK `[[12,16],[24,28]]`, db4, dX `[[1,0,-1],[3,2,-1],[2,2,0]]`; first patch's dK is `[[1,2],[4,5]]`, showing accumulation rather than replacement. |
| C10 | `cnn-gradient-check`: centered finite difference epsilon1e-5. | Convolution, bias and classifier analytical derivatives match finite differences (max absolute error below1e-5), away from ReLU kinks; test at least one parameter in each group. |
| C11 | `cnn-train`: run the complete recipe at seed7/lr.15/epochs30. | 50 parameters,16 training/8 held-out images; initial CE .6899881579037387, final training CE .016981174563243915, train accuracy1, held-out CE .5584269862772628, held-out accuracy.75. At least one conv weight changes. |
| C12 | Set epochs0; separately set lr0 with epochs30; rerun from fresh initialization. | Initial CE reproduced and all50 parameters unchanged; no fabricated decreasing curve. |
| C13 | Read final code and held-out outputs. | Convolution, ReLU, average pooling, linear head, softmax CE, manual derivatives and SGD are present and commented; held-out data never enters updates. No claim of MNIST/COCO/general-image performance. |

For C01/C09 code walkthroughs, retain a `source-map.json` containing semantic
markers and final 1-based source lines, for example `CONV_ACCUMULATE`,
`CONV_STORE`, `GRAD_ACCUMULATE` and `SGD_UPDATE`. `lesson.codeLine` must equal the
map's line for the current step, and the visible source statement must match.
Assert that stepping enters the accumulation line and then the store line; do
not hardcode guessed line numbers before final code is written. Bind
`CodeEditor.highlightLines` to the same state. Capture the actual Monaco
decoration, not just a textual line counter. After a learner edits arbitrary
source, invalidate/rebuild the map or label the walkthrough as referring to the
original source; stale highlights must not imply a real debugger trace.

## YOLO numerical and interaction checks

| ID | Scene / action | Expected evidence |
| --- | --- | --- |
| Y01 | Inspect native title, notes, architecture diagram and head labels. | Explicit YOLOv8 detection/v8.2.0 commit; original YOLO grid is separately historical. No v5 objectness, v11 block claims or newer NMS-free claims attributed to this head. |
| Y02 | `yolo-letterbox`: source320×160→640×640, box `[40,20,120,100]`. | Scale2, pad `[0,160]`, transformed `[80,200,240,360]`; inverse exactly restores original. Overlay matches coordinate units. |
| Y03 | `yolo-head`: select raw then decoded and change class count80→2. | 8,400 candidates at640 input; raw channels144→66; decoded channels84→6. Class scores are sigmoid, not mutually exclusive softmax; decoded values are not sigmoid twice. |
| Y04 | `yolo-dfl`: reduced four-bin illustration probabilities `[.1,.2,.3,.4]`; separately inspect16-bin model view and training target15. | Expectation2; explicit four-bin simplification label. Full model support is bins0–15. Probabilities sum1. Training target15 clips to14.99 before interpolation. |
| Y05 | `yolo-decode`: anchor10.5/12.5,stride8,ltrb2/3/4/5. | xyxy `[68,76,116,140]`, xywh `[92,108,48,64]`; moving right distance to5 changes x2 to124, leaving x1 unchanged. |
| Y06 | `yolo-iou`: A/B fixtures; drag B until disjoint, then match A. | Intersection900,union2300,IoU9/23 initially; then0 and1. Handle zero area by declared convention. Real drag updates geometry and values. |
| Y07 | `yolo-nms`: confidence.5, class-aware; threshold.3→.5; separately exercise exact-IoU equality and tied scores on positive-area boxes. | Kept IDs `[A,C]→[A,B,C]` in score order. Show B's suppression reason only in first setting. Equality is retained; original-index tie ordering is a teaching convention, not a guarantee of backend parity. |
| Y08 | Confidence.85; then confidence.5 plus explicit class-agnostic/.3. | `[A]` in each case for different visible reasons; resetting restores default. Boundary fixture score exactly threshold is excluded for strict comparison. |
| Y09 | `yolo-assignment`: score/quality `(.8,.5)` and `(.4,.7)`. | Metrics .013975424859373685 and .07440776088822991; second ranks higher. Label quality=max(CIoU,0); no claim two candidates demonstrate full topk10 assignment. |
| Y10 | `yolo-loss`: A/B CIoU, BCEp.8/y1, DFLtarget2.25/p2.5/p3.25. | CIoU .351304347826087; box loss .648695652173913; BCE .2231435513142097; DFL .8664339756999315. Scalar gain demonstration6.27644013051135 is explicitly a component illustration. |
| Y11 | Inspect BCE/DFL logit gradients; finite differences on smooth scalar losses. | BCE gradient-.2; DFL gradient `p-target_mass`, sum0. Gradient errors below1e-5. |
| Y12 | `yolo-head-training`: 80steps/lr.5, zero initial logits,16 bins,target2.25/class1. | Initial loss3.4657359027997265; final loss.6436653621470311, class probability.9744346035121731, expected distance2.55308580494365 (tolerance1e-6). lr0 preserves logits/loss. Label as partial educational head training. |
| Y13 | `yolo-code`: edit NMS threshold in real Monaco source, run. | Output IDs change according to Y07; program includes original IoU/confidence/class-aware NMS and returns the boxes used in the overlay. |
| Y14 | Inspect host full-model training/inference source and execution status. | Complete dependency/data/setup and train/validation/inference path; `ultralytics==8.2.0` version; unexecuted training explicitly unverified; no PyTorch import inside Pyodide. |
| Y15 | Real pretrained ONNX run, if present. | Provenance/weight/export/model/image hashes, actual tensor dimensions, executor/provider and nonempty recorded raw output; overlay coordinates verified. If absent/incompatible, report this optional demonstration unverified and use honestly labeled synthetic fixtures. |
| Y16 | Inspect evaluation page. | Separate confidence threshold, NMS IoU threshold and ground-truth matching threshold; precision/recall use correct denominators. No synthetic fixture AP presented as COCO performance. |

For Y05/Y07/Y13 walkthroughs, use source markers `DECODE_LTRB`, `FILTER_SCORE`,
`NMS_SELECT` and `NMS_SUPPRESS`, final 1-based lines and the same codeLine rules as
CNN. A visible NMS step must identify the selected candidate, compared candidate,
IoU, threshold, class decision and resulting retained/suppressed set.

## Website interaction, interruption and delivery

These checks belong to the parent workflow integration, not to arbitrary scene
code. Run them after the smoke gate on the authorized new cases while preserving
the original website task and earlier files.

- **Live conversation:** send a concrete modification while authoring is active,
  e.g. “On the convolution walkthrough, retain negative values before ReLU and
  label them.” Record message ID, received/applied status and revision. The final
  actual slide/scene must reflect it; an acknowledgment alone is not completion.
- **Ordinary chat and file upload:** send a non-editing question and upload a small
  neutral text note containing an additional explanatory label. Confirm visible
  conversation history, task-scoped attachment provenance and the requested label
  in the revised artifact. Uploaded text never grants tool/plugin permissions.
- **Resume:** at a supported persisted phase, deliberately stop the test worker
  through the workflow's owned control, then resume. Confirm the same task and
  checkpoint/trajectory lineage, retained artifacts, applied feedback cursor and
  continuation from saved work. Do not interrupt an unrelated user task or delete
  prior outputs. A new conversation that silently starts from scratch fails.
- **Frozen revision:** deliver PPTX and workspace together. Confirm the host tests
  the frozen matching sidecar and rebuilds receipts. Any post-freeze mutation
  requires a new snapshot/review rather than reusing the previous passing report.
- **Final links:** the site must expose the correct task's PPTX and interactive
  ZIP with visible completion/review status. Download and inspect the resulting
  artifacts; an output row without usable files is not sufficient.

## Playback claims

Record separately: standalone browser behavior, native static export/render,
desktop PowerPoint editing, desktop slide show interaction, save/reopen of
Content Add-in settings, Office web and Windows. Mark only actually observed
platforms verified. A browser pass and native readable fallback are useful
deliverables; they do not establish every Office host's playback capability.
