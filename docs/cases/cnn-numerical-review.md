# Fixed-source CNN numerical review

The independently reviewed Python source is retained in
[`examples/cnn-reference/tiny_cnn.py`](../../examples/cnn-reference/tiny_cnn.py),
with SHA-256
`128425bc16b0b624e472c1ac7e6e933efa238d4b039c20a0630d3fc23f0ac8b6`.
No mathematical defect was found in this fixed source. This conclusion covers
Python numerical behavior and source inspection; it does not approve the final
CNN scene, editor, deck or Office playback. Later artifacts must be compared with
this SHA or reviewed again.

The original task was only read. A separate private copy was reviewed in full
before execution, and all original task files and evidence were preserved. The
source imports only `json`, `math` and `random`; it uses no external data,
filesystem/network access, subprocesses or credentials. The copied source and
saved author output remained unchanged at the end of that review. A fresh run
matched the complete saved author JSON exactly.

The forward computation is valid cross-correlation, ReLU, global average pooling,
an affine classifier and stable cross-entropy. Backpropagation correctly sums
shared kernel/bias contributions and overlapping input gradients, uses the old
classifier weights throughout the backward pass, and applies SGD only after all
derivatives have been computed. The derivative at a ReLU zero is explicitly zero.

| Acceptance area | Independently observed evidence |
| --- | --- |
| C10: derivatives | 344 centered finite differences at epsilon 1e-5 cover every kernel, convolution bias, head weight, head bias and input pixel, for both classes before and after training. Maximum error 8.434266414621139e-12; all ReLU active sets remain unchanged. |
| C11: complete training | Independent data generation, initialization, flat patch-matrix forward/backward calculation and 480 SGD updates match all 50 final parameters to 8.881784197001252e-16. All 50 parameters change. |
| C12: boundary runs | Zero epochs and, separately, 30 epochs with learning rate zero preserve every parameter and all reported training losses. |
| C13: held-out separation | All 480 backward calls use training images. Held-out generation occurs after update 480; evaluation never updates parameters. Replacing held-out pixels with zeros and inverting labels leaves learned parameters and training checkpoints exactly identical. |

The default run uses seed 7, 30 epochs, learning rate 0.15, 16 training images and
8 held-out images. Initial training CE is 0.6899881579037386. Final training CE is
0.01698117456324391 with 16/16 correct. Held-out CE is 0.5584269862772627 with 6/8
correct. The first convolution weight changes from −0.07046689406673506 to
−0.4201043460487845. The [compact metrics fixture](../../examples/cnn-reference/expected-metrics.json)
retains the real loss checkpoints, including increases at epochs 1 and 5. Teaching
text must not describe this curve as monotonic or imply perfect generalization.
These are small synthetic results, not benchmark performance.

The original host run additionally used the runner's actual `pptx_job` OS
permission profile and an explicit environment allowlist without external
credentials. Read and write canaries outside the audit workspace and an external
network canary were denied. These are separate host-isolation observations. The
portable [audit script](../../examples/cnn-reference/audit.py) contains no host
canaries, private paths or log transcripts, does not contact a service, and makes
no sandbox claim. It recomputes the numerical evidence using Python 3.11+ from any
working directory; [run instructions](../../examples/cnn-reference/README.md)
describe its optional full JSON report.

The published script was checked once from an unrelated temporary working
directory using Python 3.11 and an absolute script path. All 387 assertions passed,
including the 344 derivative comparisons; only the requested JSON report was
created in that directory. The observed maxima match the original review above.

Only the Python/source portions of C10–C13 are established here. The final
acceptance still needs actual scene output, changed-input/editor behavior,
rendered teaching content, matching delivered artifacts and the separately
recorded browser/Office playback checks.

## Revised four-family learner experiment

The restored task now adds a complete-CNN cross-entropy experiment in
`sources/v002/full_cnn_gradient_check.py`, SHA-256
`1546b0e28d4d9f328ac05bfecadbe8af6a84edb67a9aaa5ba8114a8a963125ab`.
Its first 10,757 bytes retain every original model and training function. Only
the entry point changes: an initialized class-0 image (seed 10) checks
`K[0,0,0]`, `b[0]`, `W[0,0]` and `a[0]` with centered epsilon `1e-5`, without
training. Each perturbation uses a fresh parameter copy.

All 34 bounded independent assertions passed. The four analytic gradients are
nonzero; their largest finite-difference error is `1.1628857599088605e-11`.
A separate flat-patch/logistic calculation agrees, with maximum error
`7.544846691853735e-12`. All eight signed perturbations preserve the 64 ReLU
gates (44 active; minimum absolute preactivation `0.030047156202226727`). This
establishes these selected perturbations, not arbitrary future edits.

The reviewed slide-14 scene SHA-256 is
`c1dd132983925b77ad228bf50efd1ae52819c3222f93f56e660d9870e778f7ae`.
Its full-check action embeds the exact reviewed program. This correspondence is
static evidence; actual browser execution remains a separate case check.
The revised training source SHA-256
`80d08c02414ffd7a2a4a40f9df16f7f336eaa7cc054f20c5f1cf94fa3a12b33a`
preserves every original byte and only appends a comment and final `result`
expression for the Python worker. The existing training and 344-gradient
evidence was reused, not rerun or relabeled. The new check executed from copies
inside the actual task sandbox, and all source/scene hashes remained unchanged.
