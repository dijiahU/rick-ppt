# Audited synthetic CNN reference

This standard-library example trains a complete 50-parameter CNN to distinguish
synthetic vertical and horizontal bars. It is a fixed source snapshot used for an
independent numerical review, not acceptance of the final presentation or scenes.

Requires Python 3.11 or later; no packages, downloads, credentials or external
datasets are needed. From the repository root:

```sh
python3 examples/cnn-reference/tiny_cnn.py
python3 examples/cnn-reference/audit.py
```

The audit also runs from any working directory when invoked using its absolute
path. It reads sibling files relative to its own location, prints a compact JSON
result, and writes no report unless requested. To retain all per-parameter
derivatives and assertions, choose a new destination:

```sh
python3 examples/cnn-reference/audit.py --output cnn-audit-results.json
```

An existing output file is never overwritten. A failing assertion exits nonzero.
The audit verifies this exact `tiny_cnn.py` SHA-256:

```text
128425bc16b0b624e472c1ac7e6e933efa238d4b039c20a0630d3fc23f0ac8b6
```

The model uses a 6×6 single-channel input, four valid 3×3 cross-correlation filters,
ReLU, global average pooling, a 4-to-2 affine head, stable softmax cross-entropy,
manual derivatives and per-image SGD. Its 36 kernel weights, 4 convolution biases,
8 head weights and 2 head biases are all trainable. Seed 7, 30 epochs and learning
rate 0.15 perform 480 updates over 16 training images; 8 other images are held out.

| Measurement | Observed value |
| --- | --- |
| Initial training CE | 0.6899881579037386 |
| Final training CE / accuracy | 0.01698117456324391 / 16 of 16 |
| Held-out CE / accuracy | 0.5584269862772627 / 6 of 8 |
| Independently implemented training | Maximum parameter difference 8.881784197001252e-16 |
| 344 centered finite differences | Maximum absolute error 8.434266414621139e-12 |

`audit.py` constructs the images and initialization independently, uses a flat
patch matrix and binary logistic loss, and implements all 480 SGD updates itself.
It compares the subject's manual gradients with centered finite differences at
epsilon 1e-5 for all 50 parameters and 36 input pixels, for both classes at initial
and final parameters. Every perturbation must retain the same ReLU active set.
The finite-difference acceptance tolerance is 1e-5; recorded floating-point maxima
may vary slightly between platforms.

It also runs zero epochs and zero learning rate, confirms every parameter and
loss remains unchanged, and changes the held-out images and labels while tracing
all backward/update calls. Held-out changes must leave learned parameters and
training checkpoints identical, and evaluation must not update parameters.

`expected-metrics.json` is a compact record of observed results. The audit checks
these regression fixtures after independently deriving its reference training
and numerical gradients; the fixture is not used to manufacture model outputs.

Loss initially rises at epochs 1 and 5 before decreasing. The held-out result is
75% on a small synthetic split; it does not establish general image or benchmark
performance. Browser execution, editor interactions, animation, native slides and
Office playback require their own evidence. This portable numerical audit does
not test an OS sandbox. The [review note](../../docs/cases/cnn-numerical-review.md)
separately describes the original host isolation checks and acceptance scope.
