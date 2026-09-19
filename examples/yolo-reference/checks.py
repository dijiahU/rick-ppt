"""Independent numerical and edge-case checks; Python 3.11+, no packages."""
import argparse
import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import reference as oracle


BASE = Path(__file__).resolve().parent
checks = []


def require(name, condition, **evidence):
    checks.append({"name": name, "passed": bool(condition), **evidence})
    if not condition:
        raise AssertionError(name)


def close(name, actual, expected, tolerance=1e-12):
    require(name, math.isfinite(actual) and abs(actual - expected) <= tolerance,
            actual=actual, expected=expected, tolerance=tolerance, absolute_error=abs(actual - expected))


def rejects(name, action):
    try:
        action()
    except ValueError:
        require(name, True)
    else:
        require(name, False)


def decimal_bce(logits, target=Decimal(1)):
    value = logits[0]
    return (1 + value.exp()).ln() - target * value


def decimal_dfl(logits, target):
    return sum(value.exp() for value in logits).ln() - sum(mass * value for mass, value in zip(target, logits))


def finite_difference(name, logits, analytical, function):
    with localcontext() as context:
        context.prec = 50
        epsilon = Decimal("0.00001")
        point = [Decimal(str(value)) for value in logits]
        numerical = []
        for index in range(len(point)):
            plus, minus = point[:], point[:]
            plus[index] += epsilon
            minus[index] -= epsilon
            numerical.append(float((function(plus) - function(minus)) / (2 * epsilon)))
    errors = [abs(left - right) for left, right in zip(analytical, numerical)]
    require(name, len(analytical) == len(numerical) and max(errors) < 1e-5,
            epsilon=1e-5, count=len(errors), maximum_absolute_error=max(errors))
    return {"name": name, "analytical": analytical, "numerical": numerical,
            "maximum_absolute_error": max(errors)}


def independently_train_decimal():
    """Separate high-precision 80-step recurrence, without calling oracle helpers."""
    with localcontext() as context:
        context.prec = 50
        class_logit, distance = Decimal(0), [Decimal(0)] * 16
        target = [Decimal(0)] * 16
        target[2], target[3] = Decimal("0.75"), Decimal("0.25")
        for _ in range(80):
            p_class = 1 / (1 + (-class_logit).exp())
            exponents = [value.exp() for value in distance]
            total = sum(exponents)
            distance = [value - Decimal("0.5") * (exponent / total - mass)
                        for value, exponent, mass in zip(distance, exponents, target)]
            class_logit -= Decimal("0.5") * (p_class - 1)
        return [float(class_logit), *(float(value) for value in distance)]


def run():
    measured = oracle.measurements()
    close("Y06 intersection", measured["overlap"]["intersection"], 900, 0)
    close("Y06 union", measured["overlap"]["union"], 2300, 0)
    close("Y06 exact rational IoU", measured["overlap"]["iou"], float(Fraction(9, 23)))
    for name, box, expected in (("identical", oracle.BOX_A, 1), ("disjoint", [70, 70, 80, 80], 0),
                                ("edge touching", [50, 10, 80, 50], 0), ("zero width", [20, 20, 20, 40], 0)):
        close("IoU " + name, oracle.overlap(oracle.BOX_A, box)["iou"], expected, 0)
    close("two zero-area boxes", oracle.overlap([1, 1, 1, 1], [1, 1, 1, 1])["iou"], 0, 0)
    # Integer cells provide a set-theoretic oracle independent of min/max area code.
    boxes = [[-2, -2, 0, 0], [0, 0, 3, 2], [1, 0, 4, 2], [2, 1, 3, 4],
             [0, 1, 0, 3], [4, 4, 5, 5], [0, 0, 1, 1], [-1, -1, 4, 4]]
    cell_errors = []
    for first in boxes:
        a = {(x, y) for x in range(first[0], first[2]) for y in range(first[1], first[3])}
        for second in boxes:
            b = {(x, y) for x in range(second[0], second[2]) for y in range(second[1], second[3])}
            expected = float(Fraction(len(a & b), len(a | b))) if a and b else 0
            cell_errors.append(abs(oracle.overlap(first, second)["iou"] - expected))
    require("64 independent integer-cell IoU comparisons", max(cell_errors) == 0, comparisons=len(cell_errors))
    rejects("reversed xyxy rejected", lambda: oracle.overlap([2, 0, 1, 3], oracle.BOX_A))
    rejects("nonfinite coordinates rejected", lambda: oracle.overlap([0, 0, math.inf, 3], oracle.BOX_A))

    require("Y05 decoded pixel xyxy", measured["decode"]["xyxy"] == [68, 76, 116, 140])
    require("Y05 decoded pixel xywh", measured["decode"]["xywh"] == [92, 108, 48, 64])
    require("Y05 changed right distance moves only right edge", measured["changed_decode"]["xyxy"] == [68, 76, 124, 140])
    rejects("negative distance rejected", lambda: oracle.decode_ltrb([1, 1], [-1, 0, 2, 2], 8))
    rejects("zero stride rejected", lambda: oracle.decode_ltrb([1, 1], [0, 0, 2, 2], 0))
    close("Y04 reduced four-bin expectation", measured["four_bin_expectation"], 2, 0)
    close("full 16-bin uniform expectation", oracle.distribution_expectation([1 / 16] * 16), 7.5, 0)
    close("inference can put all mass at bin15", oracle.distribution_expectation([0] * 15 + [1]), 15, 0)
    rejects("unnormalized probabilities rejected", lambda: oracle.distribution_expectation([0.2, 0.2]))
    rejects("negative probabilities rejected", lambda: oracle.distribution_expectation([-0.1, 1.1]))

    for name, expected in (("aware_03", ["A", "C"]), ("aware_05", ["A", "B", "C"]),
                           ("confidence_085", ["A"]), ("agnostic_03", ["A"])):
        require("Y07/Y08 " + name, measured["nms"][name]["kept_ids"] == expected,
                actual=measured["nms"][name]["kept_ids"])
    require("NMS records B suppression by retained A", any(row["selected"] == "A" and row["candidate"] == "B"
            and row["same_class"] and row["decision"] == "suppressed" for row in measured["nms"]["aware_03"]["comparisons"]))
    candidates = [{"id": "first", "box": [0, 0, 3, 2], "score": 0.9, "class": 0},
                  {"id": "second", "box": [1, 0, 4, 2], "score": 0.8, "class": 0}]
    original = copy.deepcopy(candidates)
    require("NMS IoU equal to threshold is kept", oracle.greedy_nms(candidates, iou_threshold=0.5)["kept_ids"] == ["first", "second"])
    require("NMS threshold immediately below IoU suppresses", oracle.greedy_nms(candidates, iou_threshold=math.nextafter(0.5, 0))["kept_ids"] == ["first"])
    require("NMS score equal to confidence excluded", oracle.greedy_nms(candidates, confidence=0.9)["kept_ids"] == [])
    require("NMS leaves caller candidates unchanged", candidates == original)
    tied = [{"id": "Z-first", "box": oracle.BOX_A, "score": 0.9, "class": 0},
            {"id": "A-second", "box": oracle.BOX_A, "score": 0.9, "class": 0}]
    require("NMS ties preserve original index, not alphabetical ID", oracle.greedy_nms(tied)["kept_ids"] == ["Z-first"])
    require("IoU threshold1 retains identical boxes", oracle.greedy_nms(tied, iou_threshold=1)["kept_ids"] == ["Z-first", "A-second"])
    cross_class = copy.deepcopy(tied)
    cross_class[1]["class"] = 1
    require("class-aware NMS keeps identical boxes in different classes", oracle.greedy_nms(cross_class)["kept_ids"] == ["Z-first", "A-second"])
    chain = [{"id": str(index), "box": [4 * index, 0, 10 + 4 * index, 10], "score": 0.9 - index * 0.1, "class": 0} for index in range(3)]
    require("greedy NMS never lets a suppressed box suppress a later box", oracle.greedy_nms(chain)["kept_ids"] == ["0", "2"])
    require("empty NMS input returns empty", oracle.greedy_nms([])["kept_ids"] == [])
    rejects("NMS rejects zero-area candidate domain", lambda: oracle.greedy_nms([{"id": "bad", "box": [0, 0, 0, 1], "score": 0.9, "class": 0}]))
    rejects("NMS rejects NaN threshold", lambda: oracle.greedy_nms([], iou_threshold=math.nan))

    close("Y10 center-distance term", measured["ciou"]["center_distance_term"], 0.04)
    close("Y10 equal aspect term", measured["ciou"]["aspect_term"], 0, 0)
    close("Y10 CIoU", measured["ciou"]["ciou"], float(Fraction(9, 23) - Fraction(1, 25)))
    close("Y10 box loss", measured["ciou"]["box_loss"], 0.648695652173913)
    close("CIoU identical box avoids zero-over-zero alpha", oracle.ciou_components(oracle.BOX_A, oracle.BOX_A)["ciou"], 1, 0)
    aspect = 4 / math.pi ** 2 * math.atan(0.75) ** 2
    expected_ciou = 1 / 3 - 1 / 16 - aspect ** 2 / (1 - 1 / 3 + aspect)
    close("nonzero aspect-ratio CIoU", oracle.ciou_components([0, 0, 4, 2], [0, 0, 2, 4])["ciou"], expected_ciou)
    rejects("CIoU zero-area aspect ratio rejected", lambda: oracle.ciou_components([0, 0, 0, 1], oracle.BOX_A))
    close("Y09 first ranking term", measured["ranking"][0], 0.013975424859373685)
    close("Y09 second ranking term", measured["ranking"][1], 0.07440776088822991)
    require("Y09 second candidate ranks higher", measured["ranking"][1] > measured["ranking"][0])
    close("negative CIoU clamps to zero for ranking", oracle.alignment_metric(0.8, -0.4), 0, 0)

    close("Y10 BCE", measured["bce"]["loss"], -math.log(0.8))
    close("Y11 BCE logit gradient", measured["bce"]["gradient"], -0.2)
    target = [Decimal(0)] * 16
    target[2], target[3] = Decimal("0.75"), Decimal("0.25")
    require("Y10 interpolated DFL target mass", measured["dfl"]["target"]["mass"] == [float(value) for value in target])
    close("Y10 DFL", measured["dfl"]["loss"], -0.75 * math.log(0.5) - 0.25 * math.log(0.25))
    close("Y11 DFL gradients sum to zero", math.fsum(measured["dfl"]["gradient"]), 0)
    close("Y10 scalar gain illustration", measured["component_gains"]["total"], 6.27644013051135)
    close("four different DFL side losses are averaged", oracle.component_gain_example(1, 0, [1, 2, 3, 4])["mean_side_dfl"], 2.5, 0)
    close("integer DFL target puts full mass in one bin", oracle.dfl_target(2)["mass"][2], 1, 0)
    close("negative training distance clamps to zero", oracle.dfl_target(-1)["distance"], 0, 0)
    close("pinned training target clamps at14.99", oracle.dfl_target(15)["distance"], 14.99, 0)
    close("upper clamp gives bin15 mass0.99", oracle.dfl_target(100)["mass"][15], 0.99)
    require("extreme finite BCE stays finite", all(math.isfinite(oracle.bce_loss(value, label)["loss"]) for value in (-1000, 1000) for label in (0, 1)))
    require("extreme finite DFL stays finite", math.isfinite(oracle.dfl_loss([1000, -1000] + [0] * 14, 2.25)["loss"]))
    shifted = oracle.softmax([value + 1000 for value in [-3, -1, 0, 2]])
    require("softmax is invariant to a common logit shift", max(abs(a - b) for a, b in zip(shifted, oracle.softmax([-3, -1, 0, 2]))) < 1e-14)

    gradient_reports = [finite_difference("BCE hard-target finite difference", [math.log(4)], [measured["bce"]["gradient"]], decimal_bce),
                        finite_difference("BCE soft-target finite difference", [0.7], [oracle.bce_loss(0.7, 0.3)["gradient"]],
                                          lambda value: decimal_bce(value, Decimal("0.3")))]
    probabilities = [0.25 / 14] * 16
    probabilities[2], probabilities[3] = 0.5, 0.25
    for name, logits in (("fixture", [math.log(value) for value in probabilities]), ("zero", [0.0] * 16),
                         ("trained", measured["educational_head"]["after"][1:])):
        gradient_reports.append(finite_difference("DFL " + name + " 16-logit finite differences", logits,
                                oracle.dfl_loss(logits, 2.25)["gradient"], lambda values: decimal_dfl(values, target)))
    trained = measured["educational_head"]
    close("Y12 initial head loss", trained["initial"]["loss"], math.log(2) + math.log(16))
    close("Y12 final head loss", trained["final"]["loss"], 0.6436653621470311, 1e-6)
    close("Y12 final class probability", trained["final"]["class_probability"], 0.9744346035121731, 1e-6)
    close("Y12 final expected distance", trained["final"]["expected_distance"], 2.55308580494365, 1e-6)
    independent = independently_train_decimal()
    max_difference = max(abs(actual - expected) for actual, expected in zip(trained["after"], independent))
    require("independent 50-digit Decimal 80-step optimizer matches all17 logits", max_difference < 1e-12,
            maximum_absolute_error=max_difference, parameters=len(independent))
    require("all17 educational logits actually change", trained["changed_parameter_count"] == 17)
    zero = oracle.train_educational_head(learning_rate=0)
    require("Y12 lr0 leaves all17 parameters and every loss unchanged", zero["before"] == zero["after"]
            and all(row["loss"] == zero["initial"]["loss"] for row in zero["history"]))
    no_steps = oracle.train_educational_head(steps=0)
    require("zero optimizer steps retain initialization", no_steps["before"] == no_steps["after"] and len(no_steps["history"]) == 1)
    return {"schema": "yolo-reference-checks/v1", "status": "passed", "model_version": oracle.MODEL_VERSION,
            "model_commit": oracle.MODEL_COMMIT, "checks": checks, "measurements": measured,
            "finite_difference_count": sum(len(row["analytical"]) for row in gradient_reports),
            "finite_difference_maximum_absolute_error": max(row["maximum_absolute_error"] for row in gradient_reports),
            "finite_differences": gradient_reports, "decimal_optimizer_maximum_parameter_error": max_difference,
            "source_sha256": hashlib.sha256((BASE / "reference.py").read_bytes()).hexdigest(),
            "scope": "Independent scalar synthetic fixture acceptance only; no full-model execution, browser, live task or final deck approval."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional full report; destination must not exist")
    options = parser.parse_args()
    result = run()
    if options.output:
        with options.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "checks": len(checks), "source_sha256": result["source_sha256"],
                      "finite_difference_count": result["finite_difference_count"],
                      "finite_difference_maximum_absolute_error": result["finite_difference_maximum_absolute_error"],
                      "decimal_optimizer_maximum_parameter_error": result["decimal_optimizer_maximum_parameter_error"],
                      "model_commit": oracle.MODEL_COMMIT}, allow_nan=False))


if __name__ == "__main__":
    main()
