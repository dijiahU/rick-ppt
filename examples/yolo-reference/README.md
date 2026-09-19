# Independent YOLO numerical reference

These original standard-library scalar implementations provide deterministic
oracles for the fixed [YOLO brief](../../docs/cases/yolo-prompt.md) and the numerical
parts of Y04–Y12 in its [acceptance checks](../../docs/cases/acceptance-checks.md).
They pin **Ultralytics YOLOv8 detection 8.2.0**, commit
`27836d34fa7b19d38af22200805aa5d25dddaedf`. They do not execute Ultralytics, a full
detector, pretrained weights, a browser, or the future website task. No benchmark
metrics or final scene/deck acceptance are established.

Python 3.11+ is sufficient; no packages, network, credentials or datasets are
needed. From the repository root, print the calculated fixtures or run checks:

```sh
python3 examples/yolo-reference/reference.py
python3 examples/yolo-reference/checks.py --output yolo-reference-checks.json
```

Both scripts also run by absolute path from another directory. The optional full
report must use a new destination; no existing file is overwritten. Checks exit
nonzero on failure. `observed-metrics.json` records one real successful run; it is
not used by the implementation to manufacture expected outputs.

| Fixture | Calculated result |
| --- | --- |
| A/B overlap | Intersection 900, union 2300, IoU 9/23 = 0.391304347826087 |
| Anchor 10.5/12.5, stride 8, ltrb 2/3/4/5 | xyxy `[68,76,116,140]`; xywh `[92,108,48,64]` |
| Increase right distance 4→5 | Right edge 116→124; left edge 68 unchanged |
| Reduced four-bin probabilities .1/.2/.3/.4 | Expectation 2; the model uses 16 bins |
| Class-aware NMS IoU threshold .3→.5 | `[A,C]` → `[A,B,C]` |
| Confidence .85; separately class-agnostic/.3 | `[A]` in each case for different reasons |
| A/B CIoU and box loss | 0.351304347826087 and 0.648695652173913 |
| BCE probability .8 / target 1 | Loss 0.22314355131420976; logit gradient −.2 |
| DFL target 2.25 / p2=.5 / p3=.25 | Loss 0.8664339756999314; target mass .75/.25 |
| Scalar box/cls/mean-DFL gain illustration | 6.276440130511349 |
| Educational head, 80 steps / lr .5 | Final loss 0.6436653621470312; class probability 0.9744346035121731; expected distance 2.55308580494365 |

The observed run passed 75 checks. It compares 64 integer-box pairs against an
independent set-of-unit-cells area oracle. Fifty BCE/DFL logit derivatives are
checked by centered finite differences using 50-digit Decimal losses, with maximum
absolute error 1.6005599623447608e-12. A separate 50-digit Decimal implementation of
all 80 optimizer updates matches all 17 final logits within 8.881784197001252e-16.
Zero learning rate preserves every logit and every reported loss; zero steps
preserve initialization. These checks ran from a directory outside the repository.

Coordinates are continuous xyxy: there is no inclusive-pixel `+1`. Finite ordered
coordinates are required, reversed boxes are rejected, and zero-area IoU is
defined as 0, including two degenerate boxes. NMS and CIoU require positive-area
boxes: zero-area candidates are rejected before score filtering; aspect ratios
would otherwise be undefined. This matches the positive-box precondition of the
selected [Torchvision NMS contract](https://docs.pytorch.org/vision/0.18/generated/torchvision.ops.nms.html).
The oracle has no implicit clipping or coordinate normalization.

Confidence uses `score > confidence`; suppression uses `IoU > threshold` and only
previously retained boxes can suppress later candidates. NMS returns compared
boxes, overlap, class decision and rejection reasons. Equal scores use original
input index, a deliberate stable teaching convention. Torchvision documents that
same-score choices can differ between CPU and GPU; this oracle does not claim
backend parity. Classes and scores are already selected/decoded: no second sigmoid
or objectness multiplication is applied. The pinned [postprocessing source](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/ops.py)
establishes the strict confidence filter and class-aware path.

DFL expectation accepts normalized nonnegative probability mass, including
endpoint point masses. Prediction support is bins 0–15. The training target helper
separately clamps distances to `[0,14.99]`, then interpolates mass between adjacent
bins. Integer targets put all mass in one bin. This keeps the right interpolation
index in range and follows the pinned [distance helper](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/tal.py).
The reduced four-bin chart is explicitly illustrative; the
[Detect head](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/nn/modules/head.py)
uses 16 bins and per-class sigmoid outputs.

CIoU is a forward scalar formula with tiny implementation epsilons omitted so that
the hand calculations remain exact. Its center and aspect terms are exposed;
identical boxes use zero aspect penalty. No derivative of CIoU is claimed: the
actual implementation detaches alpha. See the pinned [CIoU implementation](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/metrics.py).
Assignment ranking uses `sqrt(score) * max(CIoU,0)^6` only; full top-k 10 selection,
geometry constraints, conflicts and normalized target scores are outside scope.

The loss illustration averages four side DFL losses and applies the pinned gains
7.5/.5/1.5, but its boxes and distributions are independent teaching components,
not one internally consistent batch. Full target-score weighting, batch reduction
and loss normalization require the real [loss implementation](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/utils/loss.py)
and [gain configuration](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/ultralytics/cfg/default.yaml).
The runnable optimizer changes only one class logit and 16 distance logits on
BCE plus one-side DFL. It does not train a backbone, assign targets, optimize CIoU
or produce detected objects. Letterbox/image processing, full model tensors,
actual code editing, ONNX inference, evaluation/AP and final presentations remain
separate acceptance work. No YOLO website job is submitted by these files.
