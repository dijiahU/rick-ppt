"""Original scalar teaching oracles for the pinned YOLOv8 detection brief.

Python 3.11 standard library only. This is not a detector, a training pipeline,
or a replacement for Ultralytics/Torchvision. See README.md for input conventions.
"""
import json
import math


MODEL_VERSION = "Ultralytics YOLOv8 detection 8.2.0"
MODEL_COMMIT = "27836d34fa7b19d38af22200805aa5d25dddaedf"
REGRESSION_BINS = 16
BOX_A = [10, 10, 50, 50]
BOX_B = [20, 20, 60, 60]
BOX_C = [12, 12, 48, 48]


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A finite numeric value is required")
    return float(value)


def vector(values, count=None):
    if not isinstance(values, (list, tuple)) or not values or count is not None and len(values) != count:
        raise ValueError("Unexpected vector length")
    return [finite(value) for value in values]


def unit(value):
    value = finite(value)
    if not 0 <= value <= 1:
        raise ValueError("Expected a value in [0, 1]")
    return value


def xyxy(box, positive=False):
    x1, y1, x2, y2 = vector(box, 4)
    if x1 > x2 or y1 > y2 or positive and (x1 == x2 or y1 == y2):
        raise ValueError("Ordered xyxy coordinates and the requested positive area are required")
    return x1, y1, x2, y2


def overlap(first, second):
    """Continuous coordinates: no inclusive pixel +1; zero-area IoU is zero."""
    ax1, ay1, ax2, ay2 = xyxy(first)
    bx1, by1, bx2, by2 = xyxy(second)
    area_a, area_b = (ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = finite(area_a + area_b - intersection)
    return {"area_a": area_a, "area_b": area_b, "intersection": intersection, "union": union,
            "iou": intersection / union if area_a > 0 and area_b > 0 and union > 0 else 0.0}


def ciou_components(first, second):
    """Positive-area scalar CIoU without the implementation's tiny epsilons.

    This is a forward-value oracle. It does not claim to reproduce Ultralytics'
    detached-alpha gradient or handle degenerate aspect ratios.
    """
    ax1, ay1, ax2, ay2 = xyxy(first, positive=True)
    bx1, by1, bx2, by2 = xyxy(second, positive=True)
    iou = overlap(first, second)["iou"]
    center_squared = ((ax1 + ax2 - bx1 - bx2) / 2) ** 2 + ((ay1 + ay2 - by1 - by2) / 2) ** 2
    enclosing_squared = (max(ax2, bx2) - min(ax1, bx1)) ** 2 + (max(ay2, by2) - min(ay1, by1)) ** 2
    center_term = center_squared / enclosing_squared
    angle = math.atan((ax2 - ax1) / (ay2 - ay1)) - math.atan((bx2 - bx1) / (by2 - by1))
    aspect = 4 * angle ** 2 / math.pi ** 2
    alpha = aspect / (1 - iou + aspect) if aspect > 0 else 0.0
    ciou = iou - center_term - alpha * aspect
    return {"iou": iou, "center_distance_term": center_term, "aspect_term": aspect,
            "alpha": alpha, "ciou": ciou, "box_loss": 1 - ciou}


def decode_ltrb(anchor, distances, stride):
    """Anchor and l/t/r/b are feature-grid units; returned boxes are pixels."""
    x, y = vector(anchor, 2)
    left, top, right, bottom = vector(distances, 4)
    stride = finite(stride)
    if min(left, top, right, bottom) < 0 or stride <= 0:
        raise ValueError("Distances must be nonnegative and stride positive")
    box = [(x - left) * stride, (y - top) * stride, (x + right) * stride, (y + bottom) * stride]  # DECODE_LTRB
    return {"xyxy": box, "xywh": [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2,
                                   box[2] - box[0], box[3] - box[1]]}


def distribution_expectation(probabilities):
    """Input must already be normalized; invalid mass is not silently repaired."""
    probabilities = vector(probabilities)
    if len(probabilities) < 2 or min(probabilities) < 0 or not math.isclose(math.fsum(probabilities), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Nonnegative probabilities must sum to one")
    return math.fsum(index * value for index, value in enumerate(probabilities))


def softmax(logits):
    values = vector(logits)
    if len(values) < 2:
        raise ValueError("At least two logits are required")
    maximum = max(values)
    exponents = [math.exp(value - maximum) for value in values]
    denominator = math.fsum(exponents)
    return [value / denominator for value in exponents]


def dfl_target(distance, bins=REGRESSION_BINS):
    """Pinned bbox2dist training clamp: [0, bins-1-0.01], hence [0,14.99]."""
    if type(bins) is not int or bins < 2:
        raise ValueError("At least two integer bins are required")
    raw = finite(distance)
    target = min(max(raw, 0.0), bins - 1 - 0.01)
    lower = math.floor(target)
    fraction = target - lower
    mass = [0.0] * bins
    mass[lower], mass[lower + 1] = 1 - fraction, fraction
    return {"input_distance": raw, "distance": target, "lower": lower, "upper": lower + 1, "mass": mass}


def dfl_loss(logits, distance):
    """One side's interpolated cross-entropy and derivative w.r.t. every logit."""
    logits = vector(logits)
    target = dfl_target(distance, len(logits))
    probabilities = softmax(logits)
    maximum = max(logits)
    log_normalizer = math.log(math.fsum(math.exp(value - maximum) for value in logits))
    # Work with shifted logits, avoiding log(0) on underflowed probabilities.
    loss = math.fsum(mass * (log_normalizer - (logit - maximum))
                     for mass, logit in zip(target["mass"], logits) if mass)
    return {"loss": loss, "probabilities": probabilities, "target": target,
            "expectation": distribution_expectation(probabilities),
            "gradient": [probability - mass for probability, mass in zip(probabilities, target["mass"])]}


def sigmoid(logit):
    logit = finite(logit)
    small = math.exp(-abs(logit))
    return 1 / (1 + small) if logit >= 0 else small / (1 + small)


def bce_loss(logit, target):
    """Stable binary cross-entropy, including soft targets, and logit derivative."""
    logit, target = finite(logit), unit(target)
    probability = sigmoid(logit)
    return {"loss": max(logit, 0) - logit * target + math.log1p(math.exp(-abs(logit))),
            "probability": probability, "gradient": probability - target}


def component_gain_example(ciou, classification_loss, four_side_losses):
    """Scalar component/gain illustration only, not a consistent training batch."""
    sides = vector(four_side_losses, 4)
    classification_loss = finite(classification_loss)
    box_loss = 1 - finite(ciou)
    if min(sides) < 0 or min(classification_loss, box_loss) < 0:
        raise ValueError("Loss values must be nonnegative")
    mean_dfl = math.fsum(sides) / 4
    weighted = {"box": 7.5 * box_loss, "cls": 0.5 * classification_loss, "dfl": 1.5 * mean_dfl}
    return {"box_loss": box_loss, "classification_loss": classification_loss, "mean_side_dfl": mean_dfl,
            "gains": {"box": 7.5, "cls": 0.5, "dfl": 1.5}, "weighted": weighted,
            "total": math.fsum(weighted.values()), "scope": "unrelated component illustrations, not a training batch"}


def alignment_metric(score, ciou):
    """The scalar ranking term only; no geometry/top-k/assignment normalization."""
    score, ciou = unit(score), finite(ciou)
    if ciou > 1:
        raise ValueError("CIoU cannot exceed one")
    return math.sqrt(score) * max(ciou, 0.0) ** 6


def greedy_nms(candidates, confidence=0.5, iou_threshold=0.3, class_agnostic=False):
    """Greedy kept-box comparisons, strict thresholds, stable original-index ties.

    Candidate classes/scores are already selected decoded results. No objectness,
    second sigmoid, multi-label expansion, backend time limit or max_det is added.
    Zero-area candidates are rejected before filtering, as NMS requires boxes.
    """
    confidence, iou_threshold = unit(confidence), unit(iou_threshold)
    if type(class_agnostic) is not bool:
        raise ValueError("class_agnostic must be boolean")
    pool, filtered, seen = [], [], set()
    for index, candidate in enumerate(candidates):
        identifier, label = candidate["id"], candidate["class"]
        if not isinstance(identifier, str) or not identifier or identifier in seen or type(label) is not int or label < 0:
            raise ValueError("Unique IDs and nonnegative integer class labels required")
        seen.add(identifier)
        clean = {"id": identifier, "class": label, "score": unit(candidate["score"]),
                 "box": list(xyxy(candidate["box"], positive=True)), "original_index": index}
        if clean["score"] > confidence:  # FILTER_SCORE
            pool.append(clean)
        else:
            filtered.append({"id": identifier, "reason": "score_not_strictly_above_confidence"})
    pool.sort(key=lambda row: (-row["score"], row["original_index"]))
    kept, comparisons = [], []
    while pool:
        chosen, *remaining = pool  # NMS_SELECT
        kept.append(chosen)
        pool = []
        for candidate in remaining:
            same_class = chosen["class"] == candidate["class"]
            iou = overlap(chosen["box"], candidate["box"])["iou"]
            suppress = (same_class or class_agnostic) and iou > iou_threshold  # NMS_SUPPRESS
            comparisons.append({"selected": chosen["id"], "candidate": candidate["id"], "iou": iou,
                                "threshold": iou_threshold, "same_class": same_class,
                                "decision": "suppressed" if suppress else "retained"})
            if not suppress:
                pool.append(candidate)
    return {"kept_ids": [row["id"] for row in kept], "kept": kept,
            "confidence_rejections": filtered, "comparisons": comparisons}


def train_educational_head(steps=80, learning_rate=0.5):
    """Optimize 17 logits on BCE+one-side DFL; no YOLO network/CIoU/assignment."""
    if type(steps) is not int or not 0 <= steps <= 10000:
        raise ValueError("steps must be an integer from 0 through 10000")
    learning_rate = finite(learning_rate)
    if not 0 <= learning_rate <= 1:
        raise ValueError("learning_rate must be in [0,1]")
    class_logit, distances = 0.0, [0.0] * REGRESSION_BINS
    before = [class_logit, *distances]
    history = []
    for step in range(steps + 1):
        classification, distribution = bce_loss(class_logit, 1), dfl_loss(distances, 2.25)
        history.append({"step": step, "loss": classification["loss"] + distribution["loss"],
                        "class_probability": classification["probability"], "expected_distance": distribution["expectation"]})
        if step == steps:
            break
        class_logit -= learning_rate * classification["gradient"]
        distances = [value - learning_rate * gradient for value, gradient in zip(distances, distribution["gradient"])]
    after = [class_logit, *distances]
    return {"scope": "educational class/distance-head optimizer, not YOLOv8 training", "steps": steps,
            "learning_rate": learning_rate, "parameter_count": len(before), "before": before, "after": after,
            "initial": history[0], "final": history[-1], "history": history,
            "changed_parameter_count": sum(old != new for old, new in zip(before, after))}


def measurements():
    candidates = [{"id": name, "box": box, "score": score, "class": label}
                  for name, box, score, label in (("A", BOX_A, 0.9, 0), ("B", BOX_B, 0.8, 0), ("C", BOX_C, 0.7, 1))]
    probabilities = [0.25 / 14] * 16
    probabilities[2], probabilities[3] = 0.5, 0.25
    dfl = dfl_loss([math.log(value) for value in probabilities], 2.25)
    bce, ciou = bce_loss(math.log(4), 1), ciou_components(BOX_A, BOX_B)
    trained, frozen = train_educational_head(), train_educational_head(learning_rate=0)
    return {"model_version": MODEL_VERSION, "model_commit": MODEL_COMMIT,
            "scope": "synthetic numerical reference only; no model, browser or deck acceptance",
            "overlap": overlap(BOX_A, BOX_B), "decode": decode_ltrb([10.5, 12.5], [2, 3, 4, 5], 8),
            "changed_decode": decode_ltrb([10.5, 12.5], [2, 3, 5, 5], 8),
            "four_bin_expectation": distribution_expectation([0.1, 0.2, 0.3, 0.4]),
            "nms": {"aware_03": greedy_nms(candidates), "aware_05": greedy_nms(candidates, iou_threshold=0.5),
                    "confidence_085": greedy_nms(candidates, confidence=0.85), "agnostic_03": greedy_nms(candidates, class_agnostic=True)},
            "ciou": ciou, "bce": bce, "dfl": dfl,
            "component_gains": component_gain_example(ciou["ciou"], bce["loss"], [dfl["loss"]] * 4),
            "ranking": [alignment_metric(0.8, 0.5), alignment_metric(0.4, 0.7)],
            "educational_head": {key: trained[key] for key in trained if key != "history"},
            "zero_learning_rate": {key: frozen[key] for key in ("parameter_count", "changed_parameter_count", "initial", "final")}}


if __name__ == "__main__":
    print(json.dumps(measurements(), indent=2, allow_nan=False))
