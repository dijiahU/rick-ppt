"""A complete, standard-library CNN for a small synthetic teaching task.

Run with Python 3: python tiny_cnn.py
Edit EPOCHS or LEARNING_RATE below and run again from the same initialization.
Arrays are nested lists. Image access is X[row][column]; the singleton input
channel and batch axes are omitted only because this model uses one image and
one channel per SGD update. No numerical library or hidden source is required.
"""

import json
import math
from random import Random

# An epoch is one pass through all 16 training images in a fixed order.
EPOCHS = 30
# SGD subtracts this factor times the current per-image gradient.
LEARNING_RATE = 0.15


def make_image(label, position, image_seed):
    """Return X[6][6]; class 0 is vertical, class 1 is horizontal."""
    # Create one generator per image, then draw once per pixel in row-major order.
    rng = Random(image_seed)
    image = []
    for row in range(6):
        pixels = []
        for column in range(6):
            # Position means column for a vertical bar and row for a horizontal bar.
            on_bar = column == position if label == 0 else row == position
            base = 1.0 if on_bar else 0.0
            noisy = base + rng.uniform(-0.04, 0.04)
            pixels.append(min(1.0, max(0.0, noisy)))  # Intensities stay in [0, 1].
        image.append(pixels)
    return image


def make_dataset(held_out=False):
    """Keep held-out positions and seeds distinct; never use them in SGD."""
    positions = [2, 4] if held_out else [1, 3]
    variations = range(2) if held_out else range(4)
    seed_offset = 1000 if held_out else 0
    dataset = []
    for label in [0, 1]:
        for position in positions:
            for variation in variations:
                seed = seed_offset + 100 * label + 10 * position + variation
                dataset.append({
                    "image": make_image(label, position, seed),
                    "label": label,
                    "position": position,
                    "variation": variation,
                    "image_seed": seed,
                })
    return dataset


def initialize():
    """Return K[4][3][3], b[4], W[2][4], a[2]: 36 + 4 + 8 + 2 = 50."""
    # The same generator must initialize kernels first, then classifier weights.
    rng = Random(7)
    kernels = [
        [[rng.uniform(-0.2, 0.2) for _ in range(3)] for _ in range(3)]
        for _ in range(4)
    ]
    weights = [[rng.uniform(-0.3, 0.3) for _ in range(4)] for _ in range(2)]
    return {"K": kernels, "b": [0.1] * 4, "W": weights, "a": [0.0] * 2}


def forward(image, parameters):
    """X[6][6] -> Z/A[4][4][4] -> g[4] -> logits/probabilities[2]."""
    kernels, bias = parameters["K"], parameters["b"]
    weights, head_bias = parameters["W"], parameters["a"]
    # Z contains signed preactivations; use fresh lists so rows never alias.
    preactivation = [[[0.0 for _ in range(4)] for _ in range(4)] for _ in range(4)]
    activation = [[[0.0 for _ in range(4)] for _ in range(4)] for _ in range(4)]
    for feature in range(4):
        for row in range(4):
            for column in range(4):
                # Valid cross-correlation: stride 1, padding 0, dilation 1.
                # Offsets u/v run over kernel rows/columns. Do not flip K.
                value = bias[feature]
                for u in range(3):
                    for v in range(3):
                        value += kernels[feature][u][v] * image[row + u][column + v]
                preactivation[feature][row][column] = value
                activation[feature][row][column] = max(0.0, value)
    # Average 16 spatial cells independently for each of the four features.
    means = [sum(sum(row) for row in feature_map) / 16.0 for feature_map in activation]
    # Each class receives four feature contributions plus its own bias.
    logits = [
        sum(weights[label][feature] * means[feature] for feature in range(4))
        + head_bias[label]
        for label in range(2)
    ]
    # Subtract the largest logit to keep all exponential arguments nonpositive.
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    denominator = sum(exponentials)
    probabilities = [value / denominator for value in exponentials]
    # Cache the exact forward values needed by the manual backward pass.
    return {
        "Z": preactivation, "A": activation, "g": means,
        "logits": logits, "probabilities": probabilities,
        "maximum": maximum, "denominator": denominator,
    }


def cross_entropy(cache, label):
    """Negative log probability of the correct class, measured in nats."""
    # Log-sum-exp avoids taking log(0) if a tiny probability underflows.
    return math.log(cache["denominator"]) + cache["maximum"] - cache["logits"][label]


def backward(image, label, parameters, cache):
    """Compute every derivative with the unchanged parameters of this forward pass."""
    kernels, weights = parameters["K"], parameters["W"]
    # Softmax plus cross-entropy: dlogits[t] = probability[t] - 1[t == label].
    dlogits = cache["probabilities"][:]
    dlogits[label] -= 1.0
    # Head derivatives have the same shapes as W[2][4] and a[2].
    dweights = [
        [dlogits[target] * cache["g"][feature] for feature in range(4)]
        for target in range(2)
    ]
    dhead_bias = dlogits[:]
    # Sum both class paths into each feature, using the OLD classifier weights.
    dmeans = [
        sum(weights[target][feature] * dlogits[target] for target in range(2))
        for feature in range(4)
    ]
    dkernels = [[[0.0 for _ in range(3)] for _ in range(3)] for _ in range(4)]
    dbias = [0.0 for _ in range(4)]
    dimage = [[0.0 for _ in range(6)] for _ in range(6)]
    for feature in range(4):
        for row in range(4):
            for column in range(4):
                # GAP distributes dmeans over 16 cells; ReLU gates it by Z > 0.
                # At zero, deliberately choose the ReLU derivative to be zero.
                dz = dmeans[feature] / 16.0 if cache["Z"][feature][row][column] > 0 else 0.0
                dbias[feature] += dz  # This same bias was used at every position.
                for u in range(3):
                    for v in range(3):
                        # A shared weight receives a contribution from every patch.
                        dkernels[feature][u][v] += dz * image[row + u][column + v]
                        # Overlapping patches and different filters add into dX.
                        dimage[row + u][column + v] += dz * kernels[feature][u][v]
    # dX explains the chain rule; input pixels themselves are not trainable here.
    return {"K": dkernels, "b": dbias, "W": dweights, "a": dhead_bias, "X": dimage}


def sgd_update(parameters, gradients, learning_rate):
    """Mutate parameters only AFTER backward has computed all their gradients."""
    for feature in range(4):
        for u in range(3):
            for v in range(3):
                parameters["K"][feature][u][v] -= learning_rate * gradients["K"][feature][u][v]
        parameters["b"][feature] -= learning_rate * gradients["b"][feature]
    for target in range(2):
        for feature in range(4):
            parameters["W"][target][feature] -= learning_rate * gradients["W"][target][feature]
        parameters["a"][target] -= learning_rate * gradients["a"][target]


def parameter_vector(parameters):
    """Flatten only to audit changes; model computation keeps explicit axes."""
    return (
        [value for kernel in parameters["K"] for row in kernel for value in row]
        + parameters["b"][:]
        + [value for row in parameters["W"] for value in row]
        + parameters["a"][:]
    )


def evaluate(dataset, parameters):
    """Report mean per-image CE and correct/total without any weight updates."""
    cases = []
    for example in dataset:
        cache = forward(example["image"], parameters)
        # A tie in logits chooses the first class, which is class 0.
        prediction = max(range(2), key=lambda target: cache["logits"][target])
        cases.append({
            **example,
            "prediction": prediction,
            "probabilities": cache["probabilities"],
            "logits": cache["logits"],
            "feature_means": cache["g"],
            "loss": cross_entropy(cache, example["label"]),
        })
    return {
        "mean_ce": sum(case["loss"] for case in cases) / len(cases),
        "accuracy": sum(case["prediction"] == case["label"] for case in cases) / len(cases),
        "count": len(cases),
        "cases": cases,
    }


def train(epochs=EPOCHS, learning_rate=LEARNING_RATE):
    """A fresh, deterministic run. Held-out data are evaluated only after fitting."""
    if type(epochs) is not int or not 0 <= epochs <= 60:
        raise ValueError("EPOCHS must be an integer from 0 through 60.")
    if not math.isfinite(learning_rate) or not 0 <= learning_rate <= 0.3:
        raise ValueError("LEARNING_RATE must be a finite number from 0 through 0.3.")
    train_data = make_dataset()
    parameters = initialize()
    before = parameter_vector(parameters)
    initial = evaluate(train_data, parameters)
    checkpoints = [{"epoch": 0, "mean_ce": initial["mean_ce"], "accuracy": initial["accuracy"]}]
    for epoch in range(1, epochs + 1):
        # Ordinary per-image SGD: no shuffle, momentum, weight decay or averaging.
        for example in train_data:
            cache = forward(example["image"], parameters)
            gradients = backward(example["image"], example["label"], parameters, cache)
            sgd_update(parameters, gradients, learning_rate)
        # Re-evaluate with one fixed parameter state; do not average online losses.
        if epoch == 1 or epoch % 5 == 0 or epoch == epochs:
            measured = evaluate(train_data, parameters)
            checkpoints.append({"epoch": epoch, "mean_ce": measured["mean_ce"], "accuracy": measured["accuracy"]})
    after = parameter_vector(parameters)
    return {
        "task": "Synthetic vertical versus horizontal bars; not a benchmark",
        "epochs": epochs,
        "learning_rate": learning_rate,
        "initialization_seed": 7,
        "parameter_count": len(before),
        "initial_training": {key: initial[key] for key in ["mean_ce", "accuracy", "count"]},
        "checkpoints": checkpoints,
        "training": evaluate(train_data, parameters),
        "held_out": evaluate(make_dataset(held_out=True), parameters),
        "parameters_before": before,
        "parameters_after": after,
        "parameters_final": parameters,
        "changed_parameter_count": sum(old != new for old, new in zip(before, after)),
        "conv_weight": {"index": [0, 0, 0], "before": before[0], "after": after[0]},
    }


if __name__ == "__main__":
    # The visible charts must consume these computed values after a worker run.
    result = train()
    print(json.dumps(result, allow_nan=False))
