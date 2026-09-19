"""Portable independent audit of the fixed CNN example; Python 3.11+, no dependencies."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from random import Random
import sys
import time

sys.dont_write_bytecode = True
import tiny_cnn as subject


BASE = Path(__file__).resolve().parent
SOURCE_SHA256 = "128425bc16b0b624e472c1ac7e6e933efa238d4b039c20a0630d3fc23f0ac8b6"


checks = []


def check(name, condition, **evidence):
    checks.append({"name": name, "passed": bool(condition), **evidence})
    if not condition:
        raise AssertionError(name)


def maximum_difference(left, right):
    return max(abs(a - b) for a, b in zip(left, right))


def image_fingerprint(image):
    return hashlib.sha256(json.dumps(image, separators=(",", ":")).encode()).hexdigest()


def independent_dataset(held_out=False):
    data = []
    for label in (0, 1):
        for position in ((2, 4) if held_out else (1, 3)):
            for variation in range(2 if held_out else 4):
                seed = (1000 if held_out else 0) + label * 100 + position * 10 + variation
                rng = Random(seed)
                pixels = [min(1.0, max(0.0, float((i // 6 if label else i % 6) == position)
                                      + rng.uniform(-0.04, 0.04))) for i in range(36)]
                data.append({"image": [pixels[i:i + 6] for i in range(0, 36, 6)],
                             "label": label, "position": position, "variation": variation,
                             "image_seed": seed})
    return data


def independent_initialization():
    rng = Random(7)
    return [rng.uniform(-0.2, 0.2) for _ in range(36)] + [0.1] * 4 + [rng.uniform(-0.3, 0.3) for _ in range(8)] + [0.0] * 2


def reference(image, theta, label, gradients=False):
    """Flat patch matrix and binary logistic loss, independent of subject helpers."""
    patches = [[image[y + k // 3][x + k % 3] for k in range(9)]
               for y in range(4) for x in range(4)]
    z = [[sum(theta[f * 9 + k] * patch[k] for k in range(9)) + theta[36 + f]
          for patch in patches] for f in range(4)]
    pooled = [sum(max(0.0, value) for value in row) / 16 for row in z]
    scores = [sum(theta[40 + target * 4 + f] * pooled[f] for f in range(4)) + theta[48 + target]
              for target in range(2)]
    delta = scores[1] - scores[0]
    exp_delta = math.exp(-abs(delta))
    p1 = 1 / (1 + exp_delta) if delta >= 0 else exp_delta / (1 + exp_delta)
    wrong_minus_right = delta if label == 0 else -delta
    loss = max(wrong_minus_right, 0.0) + math.log1p(math.exp(-abs(wrong_minus_right)))
    output = {"loss": loss, "probabilities": [1 - p1, p1], "g": pooled, "logits": scores,
              "prediction": int(delta > 0), "mask": [value > 0 for row in z for value in row],
              "minimum_relu_margin": min(abs(value) for row in z for value in row)}
    if gradients:
        residual = p1 - label
        d = [0.0] * 50
        for f in range(4):
            downstream = residual * (theta[44 + f] - theta[40 + f]) / 16
            active = [index for index, value in enumerate(z[f]) if value > 0]
            for k in range(9):
                d[f * 9 + k] = downstream * sum(patches[index][k] for index in active)
            d[36 + f] = downstream * len(active)
            d[40 + f] = -residual * pooled[f]
            d[44 + f] = residual * pooled[f]
        d[48], d[49] = -residual, residual
        output["gradient"] = d
    return output


def reference_evaluate(data, theta):
    rows = [reference(example["image"], theta, example["label"]) for example in data]
    return {"mean_ce": sum(row["loss"] for row in rows) / len(rows),
            "accuracy": sum(row["prediction"] == sample["label"] for row, sample in zip(rows, data)) / len(rows),
            "count": len(rows)}


def numerical_gradients(parameters, example, state_name):
    theta = subject.parameter_vector(parameters)
    image, label = example["image"], example["label"]
    cache = subject.forward(image, parameters)
    analytical = subject.backward(image, label, parameters, cache)
    flat = subject.parameter_vector(analytical)
    base = reference(image, theta, label, gradients=True)
    check("independent analytical derivatives " + state_name,
          maximum_difference(flat, base["gradient"]) < 1e-12,
          maximum_absolute_error=maximum_difference(flat, base["gradient"]))
    epsilon = 1e-5
    rows = []
    groups = ["conv_kernel"] * 36 + ["conv_bias"] * 4 + ["head_weight"] * 8 + ["head_bias"] * 2
    for index in range(50):
        upper, lower = theta[:], theta[:]
        upper[index] += epsilon
        lower[index] -= epsilon
        plus = reference(image, upper, label)
        minus = reference(image, lower, label)
        check("smooth parameter perturbation " + state_name + "/" + str(index),
              plus["mask"] == minus["mask"] == base["mask"])
        numerical = (plus["loss"] - minus["loss"]) / (2 * epsilon)
        rows.append({"group": groups[index], "index": index, "analytical": flat[index],
                     "numerical": numerical, "absolute_error": abs(flat[index] - numerical)})
    for index in range(36):
        upper, lower = copy.deepcopy(image), copy.deepcopy(image)
        y, x = divmod(index, 6)
        upper[y][x] += epsilon
        lower[y][x] -= epsilon
        plus = reference(upper, theta, label)
        minus = reference(lower, theta, label)
        check("smooth input perturbation " + state_name + "/" + str(index),
              plus["mask"] == minus["mask"] == base["mask"])
        numerical = (plus["loss"] - minus["loss"]) / (2 * epsilon)
        rows.append({"group": "input_pixel", "index": index, "analytical": analytical["X"][y][x],
                     "numerical": numerical, "absolute_error": abs(analytical["X"][y][x] - numerical)})
    summary = {group: max(row["absolute_error"] for row in rows if row["group"] == group)
               for group in (*dict.fromkeys(groups), "input_pixel")}
    check("centered finite differences " + state_name, max(summary.values()) < 1e-5,
          epsilon=epsilon, count=len(rows), group_maximum_absolute_error=summary,
          minimum_relu_margin=base["minimum_relu_margin"])
    return {"state": state_name, "image_seed": example["image_seed"], "label": label,
            "minimum_relu_margin": base["minimum_relu_margin"], "epsilon": epsilon,
            "group_maximum_absolute_error": summary, "derivatives": rows}


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write full evidence to a new JSON file; never overwrite an existing file")
    args = parser.parse_args()
    source_sha256 = hashlib.sha256((BASE / "tiny_cnn.py").read_bytes()).hexdigest()
    check("source matches the reviewed immutable example", source_sha256 == SOURCE_SHA256,
          source_sha256=source_sha256)

    training, held = independent_dataset(), independent_dataset(True)
    check("training data independently reconstructed", training == subject.make_dataset())
    check("held-out data independently reconstructed", held == subject.make_dataset(True))
    check("train held-out positions and seeds disjoint",
          not ({x["image_seed"] for x in training} & {x["image_seed"] for x in held})
          and not ({x["position"] for x in training} & {x["position"] for x in held}),
          train_count=len(training), held_out_count=len(held))
    initial = independent_initialization()
    check("all 50 initial parameters independently reconstructed",
          len(initial) == 50 and initial == subject.parameter_vector(subject.initialize()))
    result = subject.train()
    check("all 50 trainable values updated", result["changed_parameter_count"] == 50)

    theta = initial[:]
    checkpoints = [{"epoch": 0, **reference_evaluate(training, theta)}]
    for epoch in range(1, 31):
        for sample in training:
            gradient = reference(sample["image"], theta, sample["label"], gradients=True)["gradient"]
            theta = [old - 0.15 * d for old, d in zip(theta, gradient)]
        if epoch == 1 or epoch % 5 == 0:
            checkpoints.append({"epoch": epoch, **reference_evaluate(training, theta)})
    final_difference = maximum_difference(theta, result["parameters_after"])
    independent_metrics = {"training": reference_evaluate(training, theta), "held_out": reference_evaluate(held, theta)}
    check("independent 480-update flat implementation matches full training", final_difference < 1e-12,
          updates=480, maximum_parameter_absolute_error=final_difference,
          independently_computed_metrics=independent_metrics)
    for expected, actual in zip(checkpoints, result["checkpoints"]):
        check("independent fixed-state evaluation epoch " + str(expected["epoch"]),
              expected["epoch"] == actual["epoch"] and abs(expected["mean_ce"] - actual["mean_ce"]) < 1e-12
              and expected["accuracy"] == actual["accuracy"], absolute_loss_error=abs(expected["mean_ce"] - actual["mean_ce"]))
    for split in ("training", "held_out"):
        check("independent " + split + " metrics", abs(independent_metrics[split]["mean_ce"] - result[split]["mean_ce"]) < 1e-12
              and independent_metrics[split]["accuracy"] == result[split]["accuracy"], actual=independent_metrics[split])

    boundary_results = {}
    for name, options in (("epochs_zero", {"epochs": 0}), ("learning_rate_zero", {"learning_rate": 0.0})):
        boundary = subject.train(**options)
        check(name + " leaves every parameter and training loss unchanged", boundary["parameters_after"] == initial
              and boundary["changed_parameter_count"] == 0
              and all(row["mean_ce"] == boundary["initial_training"]["mean_ce"] for row in boundary["checkpoints"]),
              initial_loss=boundary["initial_training"]["mean_ce"], final_loss=boundary["training"]["mean_ce"],
              maximum_parameter_absolute_error=maximum_difference(initial, boundary["parameters_after"]),
              checkpoint_count=len(boundary["checkpoints"]))
        boundary_results[name] = {key: boundary[key] for key in ("epochs", "learning_rate", "changed_parameter_count")}

    train_fingerprints = {image_fingerprint(x["image"]) for x in training}
    held_fingerprints = {image_fingerprint(x["image"]) for x in held}
    check("training and held-out image bytes disjoint", not train_fingerprints & held_fingerprints)
    saved_functions = {name: getattr(subject, name) for name in ("make_dataset", "backward", "sgd_update", "evaluate")}
    instrumentation = {"backward_calls": 0, "sgd_calls": 0, "evaluation_depth": 0,
                       "held_out_generation_after_updates": [], "backward_non_training_images": 0}

    def observed_backward(image, label, parameters, cache):
        instrumentation["backward_calls"] += 1
        if image_fingerprint(image) not in train_fingerprints:
            instrumentation["backward_non_training_images"] += 1
        return saved_functions["backward"](image, label, parameters, cache)

    def observed_sgd(parameters, gradients, learning_rate):
        if instrumentation["evaluation_depth"]:
            raise AssertionError("An evaluation performed an SGD update")
        instrumentation["sgd_calls"] += 1
        return saved_functions["sgd_update"](parameters, gradients, learning_rate)

    def observed_evaluate(dataset, parameters):
        before = copy.deepcopy(parameters)
        instrumentation["evaluation_depth"] += 1
        output = saved_functions["evaluate"](dataset, parameters)
        instrumentation["evaluation_depth"] -= 1
        if before != parameters:
            raise AssertionError("Evaluation changed parameters")
        return output

    def poisoned_held_out(held_out=False):
        if not held_out:
            return saved_functions["make_dataset"]()
        instrumentation["held_out_generation_after_updates"].append(instrumentation["sgd_calls"])
        return [{**example, "image": [[0.0] * 6 for _ in range(6)], "label": 1 - example["label"]}
                for example in saved_functions["make_dataset"](True)]

    try:
        subject.backward, subject.sgd_update = observed_backward, observed_sgd
        subject.evaluate, subject.make_dataset = observed_evaluate, poisoned_held_out
        poisoned = subject.train()
    finally:
        for name, function in saved_functions.items():
            setattr(subject, name, function)
    check("held-out poisoning cannot affect learned parameters or training checkpoints",
          poisoned["parameters_after"] == result["parameters_after"] and poisoned["checkpoints"] == result["checkpoints"]
          and instrumentation["backward_calls"] == instrumentation["sgd_calls"] == 480
          and instrumentation["held_out_generation_after_updates"] == [480]
          and instrumentation["backward_non_training_images"] == 0, instrumentation=instrumentation,
          poisoned_held_out_mean_ce=poisoned["held_out"]["mean_ce"], original_held_out_mean_ce=result["held_out"]["mean_ce"])

    gradient_reports = []
    for state, parameters in (("initial", subject.initialize()), ("trained", result["parameters_final"])):
        for label in (0, 1):
            example = next(x for x in training if x["label"] == label)
            gradient_reports.append(numerical_gradients(parameters, example, state + "-class-" + str(label)))
    output = {"schema": "cnn-independent-numerical-review/v1", "status": "passed", "checks": checks,
              "source_sha256": source_sha256,
              "executed_python": sys.version, "elapsed_seconds": time.monotonic() - started,
              "default_metrics": {split: {key: result[split][key] for key in ("mean_ce", "accuracy", "count")}
                                  for split in ("initial_training", "training", "held_out")},
              "parameter_count": 50, "changed_parameter_count": result["changed_parameter_count"],
              "conv_weight": result["conv_weight"], "boundary_results": boundary_results,
              "independent_training_maximum_parameter_absolute_error": final_difference,
              "finite_difference_count": sum(len(row["derivatives"]) for row in gradient_reports),
              "finite_difference_maximum_absolute_error": max(d["absolute_error"] for row in gradient_reports for d in row["derivatives"]),
              "finite_differences": gradient_reports,
              "scope": "Fixed Python source numerical behavior only; not final scenes, editor UI, rendered PPTX, browser Python, OS sandbox or Office playback.",
              "observations": ["Training loss increases at epochs 1 and 5 before falling; do not label loss as monotonic.",
                               "Held-out accuracy is 6/8, not perfect; this synthetic task does not establish benchmark performance."]}
    # Archived observations are regression fixtures, not the mathematical oracle.
    # The full reference training and finite differences above are independently computed.
    expected = json.loads((BASE / "expected-metrics.json").read_text())
    check("expected metrics identify this source", expected["source_sha256"] == source_sha256)
    check("expected fixed recipe size", result["parameter_count"] == expected["parameter_count"]
          and result["epochs"] == expected["epochs"] and result["learning_rate"] == expected["learning_rate"])
    for split, metrics in expected["default_metrics"].items():
        actual = output["default_metrics"][split]
        check("archived observed " + split + " metrics", abs(actual["mean_ce"] - metrics["mean_ce"]) < 1e-12
              and actual["accuracy"] == metrics["accuracy"] and actual["count"] == metrics["count"])
    check("all archived loss checkpoints are present", len(result["checkpoints"]) == len(expected["checkpoints"]))
    for actual, recorded in zip(result["checkpoints"], expected["checkpoints"]):
        check("archived checkpoint " + str(recorded["epoch"]), actual["epoch"] == recorded["epoch"]
              and actual["accuracy"] == recorded["accuracy"] and abs(actual["mean_ce"] - recorded["mean_ce"]) < 1e-12)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": output["status"], "checks": len(checks), "metrics": output["default_metrics"],
                      "finite_differences": output["finite_difference_count"],
                      "finite_difference_maximum_absolute_error": output["finite_difference_maximum_absolute_error"],
                      "independent_training_maximum_parameter_absolute_error": final_difference,
                      "elapsed_seconds": output["elapsed_seconds"]}, allow_nan=False))


if __name__ == "__main__":
    main()
