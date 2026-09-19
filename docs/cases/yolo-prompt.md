# YOLO acceptance case: authoring brief

Status: researched brief for the post-smoke website run. No job or presentation is
created by this document. Run after CNN's new-version acceptance has been reviewed,
using Rick's existing website account.

## Website fields

- Title: `介绍YOLO — Interactive YOLOv8 Detection`
- Language: `en`, consistent with the CNN case.
- Slides: **18**, matching the submitted outline and final native slide count.
- Audience: understands CNN forward/backpropagation after the CNN lesson.
- Version: **Ultralytics YOLOv8 object detection, v8.2.0**, repository commit
  `27836d34fa7b19d38af22200805aa5d25dddaedf`. This is an explicitly selected
  historical implementation, not a claim to teach the latest YOLO family.

Eighteen pages are sufficient because box manipulation, threshold sweeps, tensor
inspection and editable code show several worked states on one page. Keep the
complete training/inference distinction and version-specific mathematics.

## Prompt to submit

Create an English presentation titled **YOLOv8 Detection: From Pixels to Boxes**.
Teach first principles, explain every symbol and tensor dimension, and connect
each inference/training stage to a runnable, commented experiment. Use exactly
18 native slides with the common interactive scene DSL and existing feature
packs. Keep native editable titles, mathematical definitions, context and summary
outside the live widgets. Use `core`, `code` and `math`; use `ml` only for genuine
local ONNX model execution with documented input/output semantics. Do not create
a topic-specific React application or add a new runtime.

Clearly distinguish historical intuition from the selected implementation.
The [original YOLO paper](https://www.cv-foundation.org/openaccess/content_cvpr_2016/html/Redmon_You_Only_Look_CVPR_2016_paper.html)
introduces joint detection with one network. Its grid/objectness parameterization
is historical context, not the head to implement here. Pin architecture, head,
assignment and loss claims to the selected v8.2.0 source. Avoid blending v1, v5,
YOLO11 or newer NMS-free families into an imaginary universal YOLO algorithm.

| Slide | Teaching question and required content | Learner experiment |
| --- | --- | --- |
| 1 | What is detection, and which YOLO are we studying? Label the exact version and task. | Compare class-only output with multiple class/box detections. |
| 2 | How is a box represented? Explain xyxy, center/width/height, pixels and normalized coordinates. | Drag/resize boxes; display both representations and units. |
| 3 | What survives from the original YOLO idea? Contrast one-network intuition with this version's actual multi-scale head. | Follow an image through one shared network; separately label the historical grid illustration. |
| 4 | How does preprocessing preserve geometry? Explain resize, letterbox, normalization, channel order and inverse coordinates. | Toggle original/padded coordinates; follow one exact box through both transforms. |
| 5 | What do backbone, neck and head contribute? Explain C2f, SPPF and feature aggregation at a conceptual level. | Select P3/P4/P5; expose stride, resolution and information sources. |
| 6 | What does the detection head predict? Show raw versus decoded tensors, branch separation and no separate objectness channel. | Switch raw/decoded views and count channels/candidates. |
| 7 | Why represent an edge distance as a distribution? Explain 16 bins, softmax and expectation. | Move probability mass among bins; show the expected distance. |
| 8 | How do four distances become a box? Define anchor point, stride and l/t/r/b units. | Step through decoding; update the visible box and highlight the matching source statement. |
| 9 | What does overlap mean? Derive IoU and explain disjoint, identical and degenerate cases. | Drag two boxes; update intersection, union and IoU. |
| 10 | What does the confidence threshold remove? Explain class sigmoid scores and filtering. | Sweep confidence and track every candidate's retained/rejected reason. |
| 11 | Why suppress duplicate boxes? Explain greedy, class-aware NMS and its tradeoffs. | Step NMS, change its threshold, toggle explicitly labeled class-agnostic mode. |
| 12 | Which predictions receive training targets? Explain candidate geometry, task-aligned ranking, top-k and conflict resolution. | Compare two candidates' score/alignment terms; label the reduced illustrative subset. |
| 13 | What is optimized? Distinguish BCE classification, CIoU box loss and DFL; define reductions and gains. | Change a class probability or distance distribution and show each loss component. |
| 14 | How do gradients improve these outputs? Derive BCE/DFL logit gradients and the SGD update. | Run a small trainable class/distance-head experiment and plot returned losses. |
| 15 | Write inference postprocessing yourself. Fully comment decoding, clipping, confidence filtering and class-aware NMS. | Edit and run real Python; compare returned boxes with the visual overlay. |
| 16 | What does full-model training require? Explain labeled images, dataset split, augmentation, matching, losses, backprop and evaluation. | Inspect labels and actual runnable host Python training/inference source; contrast its dependency/runtime with the in-slide pure-Python experiment. |
| 17 | Can a real model detect an object? Use a genuine local trained YOLOv8 ONNX model if its provenance/export can be established. | Run the model on one bundled authorized image; inspect actual tensors and overlay; provide an honest capability fallback. |
| 18 | How do we judge detection and debug failures? Explain precision/recall, IoU matching and AP conceptually, limitations and next experiments. | Compare a false positive, miss and duplicate; reset and replay thresholds/code. |

The pinned [model configuration](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/cfg/models/v8/yolov8.yaml)
supports the architecture page. For a 640×640 input and three scales at strides
8/16/32, show 80×80, 40×40 and 20×20 locations: 8,400 in total. These dimensions
assume the ordinary three-scale detection configuration, not every YOLO variant.

Follow the selected [Detect head](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/nn/modules/head.py):
4×16 raw distance logits and C class logits per location; for C=80 this is 144
raw channels. After distribution decoding, the usual pre-NMS inference tensor
is `[batch,4+C,N]`, hence `[1,84,8400]` in this example. Its first four channels
are center x/y and width/height in input-image pixels; class channels have already
passed sigmoid. There is no extra objectness factor to multiply into scores.
Do not softmax classes or apply sigmoid to already decoded class scores again.

For assignment, v8.2.0 uses class score to power .5 times **clamped CIoU** to
power 6, then candidate/target logic; `topk=10` comes from its loss construction.
Show the distinction between this quality term and plain IoU used by NMS. A
two-candidate explanation illustrates ranking, not the complete matching algorithm.
Consult [assignment source](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/tal.py).

Explain classification BCE with possibly soft assigned targets, target-score
weighting/normalization, positive-only box/DFL terms, four-side DFL averaging and
the batch-size scaling in the actual implementation. Use an explicitly labeled
one-positive numerical simplification for hand calculations. Default gains in
this version are box 7.5, cls .5 and dfl 1.5. Sources:
[loss implementation](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/loss.py),
[gain configuration](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/cfg/default.yaml),
[DFL paper](https://arxiv.org/abs/2006.04388) and
[DIoU/CIoU paper](https://arxiv.org/abs/1911.08287).

Use the exact numerical fixtures below. Write original pure-Python/JavaScript
implementations of the algorithms rather than copying large source fragments:

- Fixed square letterbox: source width/height `320,160`, destination `640,640`,
  centered padding, `auto=False`, scaling up allowed. Scale 2, top/bottom padding
  160, left/right 0. Original xyxy `[40,20,120,100]` becomes
  `[80,200,240,360]`; inverse conversion must recover the original. General
  odd-size rounding must be documented separately. See
  [LetterBox source](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/data/augment.py).
- Anchor `(10.5,12.5)` in feature-grid units, stride 8 and distances
  `[2,3,4,5]` yield xyxy `[68,76,116,140]`, or xywh `[92,108,48,64]`.
- Four-bin illustration `[.1,.2,.3,.4]` has expectation 2. Model bins are
  0–15; clip DFL training targets to `[0,14.99]` before interpolation.
- Boxes `A=[10,10,50,50]`, `B=[20,20,60,60]` have intersection 900,
  union 2300 and IoU `9/23 = .391304347826087`. Identical positive-area
  boxes give 1; disjoint/zero-area boxes give 0. NMS/CIoU require positive area.
- NMS candidates: `A` score .9/class 0; `B` score .8/class 0;
  `C=[12,12,48,48]` score .7/class 1. With confidence .5 and class-aware
  NMS, IoU threshold .3 keeps `A,C`; threshold .5 keeps `A,B,C`.
  Confidence .85 keeps `A` only. Explicit class-agnostic NMS at .3 keeps `A`.
  Sort descending score, then original index: a teaching tie convention,
  not backend parity. Keep `score > confidence`; suppress only when a
  retained same-class box has `IoU > threshold` (any class if agnostic). See
  [postprocessing source](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/ops.py).
- The two same-size boxes A/B have center-distance term `.04` and zero
  aspect-ratio term, so CIoU is `.351304347826087` and box loss
  `.648695652173913`. Values ignore the implementation's tiny numerical
  epsilon; compare with tolerance. Define all general CIoU terms using
  [its implementation](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/metrics.py).
- Class probability .8 with target 1 gives BCE `.2231435513142097` and
  derivative with respect to the logit `-.2`. DFL target `2.25` has target
  mass `.75` at bin 2 and `.25` at bin 3. Predicted probability .5 at bin 2,
  .25 at bin 3, and the remaining .25 distributed across other bins gives
  DFL `.8664339756999315`; logit gradient is predicted minus target mass.
- Use all four identical side losses only in the labeled scalar reduction
  demonstration: `7.5*.648695652173913 + .5*.2231435513142097 +
  1.5*.8664339756999315 = 6.27644013051135`. This demonstrates the gains;
  it is not a claim that unrelated fixture boxes/distributions form one
  complete, internally consistent training batch.
- Ranking illustration: score/quality `(.8,.5)` gives `.013975424859373685`;
  `(.4,.7)` gives `.07440776088822991`. Here “quality” is already clamped
  CIoU, not ordinary IoU and not an unlabelled substitute for it.

The in-slide training experiment must truly optimize parameters: initialize one
class logit and 16 distance logits to zero, use class target 1 and distance target
2.25, and perform 80 SGD steps at learning rate .5 on BCE+DFL. Compute sigmoid,
stable softmax, loss and analytic gradients directly in pure Python. Label this
**an educational class/distance-head optimizer**, not YOLOv8 training. Its initial
loss is `log(2)+log(16) = 3.4657359027997265`. After 80 steps the combined loss is
`.6436653621470311`, class probability `.9744346035121731` and expected distance
`2.55308580494365` (tolerance `1e-6`; finite optimization does not equal the target
exactly). Return the before/after parameters,
probability, expected distance and loss history; `learning_rate=0` must preserve
all parameters. This illustrates two gradient terms, without claiming to train
the backbone, match targets or optimize the CIoU term.

Provide separate complete commented host Python for actual `ultralytics==8.2.0`
model training and inference: declared environment, locally generated labeled
images, train/validation split, data YAML, explicit device/seed, `.train`, `.val`,
`.predict`, and export. This source must be runnable after installing its declared
dependencies, but PyTorch/Ultralytics cannot run inside the slide's standard-library
Pyodide worker. Any unexecuted host training must be marked as such. Do not show
invented metrics. Local generated shapes are an instructional dataset, not COCO.

For slide 17, prefer a genuine pretrained YOLOv8n ONNX model exported from the
selected implementation on the host, with source/weight/export hashes, labels,
input normalization and output shape retained. Keep the model under the runtime
limit and all assets local. Use a bundled permitted test image with explicit
attribution. The current `ml` adapter expects already-resized RGBA and decoded
`[1,4+C,N]` tensors; prepare letterboxing/unmapping in lesson code rather than
pretending the adapter does them. Run and display actual outputs. If genuine
weights or compatible inference cannot be established, show a transparent
**synthetic postprocessing fixture** and mark real pretrained inference unverified;
the acceptance report must list that gap. Never relabel a tiny identity model,
fixed boxes or the toy optimizer as a trained YOLO detector.

Use stable state names `lesson.step`, `lesson.codeLine`, `letterbox.box`,
`decode.xyxy`, `overlap.iou`, `nms.keptIds`, `loss.total`, and `headTraining.result`.
Bind Monaco line highlighting to the walkthrough's source line and show the
current statement/explanation. This is a guided walkthrough, not a Python debugger.
Results and box overlays must derive from current inputs or actual worker output.
All sliders, drag operations, NMS steps, code edits/runs and reset behavior need
real `testPlan` assertions and captures under [acceptance checks](acceptance-checks.md).
Keep readable native fallbacks, source citations and a version-specific glossary.
Deliver native PPTX, matching workspace, portable bundle, complete sources and
honest host-generated verification evidence.
