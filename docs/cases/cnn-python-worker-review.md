# Fixed-source CNN Python worker compatibility

The [audited CNN source](../../examples/cnn-reference/tiny_cnn.py) executed in the
release's actual local Pyodide worker under production CSP: **22 of 22 checks
passed**. Default training and learning rate zero each ran exactly once. This
verifies fixed-source worker compatibility; actual Monaco typing, final scenes,
the delivered deck and Office playback still require their own acceptance.

The release was `0.1.0+codex.20260919214127`, using its real loopback HTTP server,
96-file runtime and local Python assets. Production assets and CSP headers were
not mocked. No dependencies were installed or runtime limits changed. The source
SHA-256 is `128425bc16b0b624e472c1ac7e6e933efa238d4b039c20a0630d3fc23f0ac8b6`;
the runtime fingerprint is
`fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de`.
The [measured fixture](../../examples/cnn-reference/browser-observed.json)
records source, wrapper, runtime and returned-result hashes plus actual values.

Both wrappers preserve every source byte, set `__name__` to bypass the CLI-only
entry and end with `train()` or `train(learning_rate=0.0)`. That final Python
expression returns the complete training dictionary through the production
worker's conversion. Default training uses seed 7, 30 epochs and learning rate
0.15. All 50 learned parameters match the independently audited CPython run
within the 1e-6 absolute tolerance; the largest difference is
4.440892098500626e-16. The largest loss difference is 2.220446049250313e-16.

| Browser measurement | Actual value |
| --- | --- |
| Initial training CE | 0.6899881579037387 |
| Final training CE / correct images | 0.01698117456324391 / 16 of 16 |
| Held-out CE / correct images | 0.558426986277263 / 6 of 8 |
| Default changed parameters | 50 of 50 |
| lr0, 30 epochs | All 50 parameters unchanged; all 8 checkpoints retain initial loss |
| Default total / initialization / execution | 1030.4 / 853.5 / 176.8 ms |
| lr0 total / initialization / execution | 1022.5 / 841.2 / 181.8 ms |

Each run creates a new Python VM. Initialization and execution timings are
observed `loading → running → done` DOM intervals that include UI scheduling;
they are not measurements inside the VM. Total elapsed time comes from the
worker controller and spans creation through receipt of the result. Browser
HTTP caching was disabled for this isolated check; the observations do not claim
a cold operating-system cache. The unchanged production limits were 60,000 ms
for Python initialization and 5,000 ms for execution, with no scene override.

The page retained its production CSP without `unsafe-eval`. Only the isolated
code worker response enabled evaluation and prohibited nested workers. No
runtime errors, CSP violations or external requests occurred. Training loss can
rise at epochs 1 and 5, and held-out accuracy is 75% on a small synthetic split;
neither result establishes benchmark performance.

This note and fixture were extracted from the existing successful proof without
another execution. They contain no private workspace paths, credentials or log
transcripts. Original task files and private evidence remain preserved. See the
[independent mathematical review](cnn-numerical-review.md) for the separately
implemented training and finite-difference evidence.
