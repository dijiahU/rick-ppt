# Pinned YOLOv8n model compatibility evidence

On 2026-09-20, a separate private probe exported official pretrained YOLOv8n
weights, executed the complete ONNX model with CPU ONNX Runtime, and ran the same
model through the existing browser `ModelRunner` using its real **Run model**
button. Browser checks passed **11/11**; formal scene validation and asset import
into a new blank workspace passed **9/9**. The two browser screenshots were
visually reviewed. The [small evidence manifest](real-model-observed.json) records
versions, hashes, tensor shapes and observed results; no model, image, large input
array or executable downloader is committed here.

This is separate from the [75-check scalar teaching reference](README.md). It
establishes one actual-model compatibility result, not dataset accuracy, a
completed YOLO presentation, website delivery or desktop PowerPoint playback.
At this preparation checkpoint, the formal YOLO task has **not been submitted**
and the prepared host-provided static assets have **not been handed to a task**.

## Three distinct version identities

1. **Exporter source:** official Ultralytics tag `v8.2.0`, verified through the
   [GitHub tag API](https://api.github.com/repos/ultralytics/ultralytics/git/ref/tags/v8.2.0),
   points to commit `27836d34fa7b19d38af22200805aa5d25dddaedf`. The
   [commit archive](https://codeload.github.com/ultralytics/ultralytics/zip/27836d34fa7b19d38af22200805aa5d25dddaedf)
   was installed into a new, independent venv.
2. **Weight distribution:** [official assets release v8.2.0](https://github.com/ultralytics/assets/releases/tag/v8.2.0),
   asset [yolov8n.pt](https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt),
   asset ID 178977528, created 2024-07-11. The downloaded bytes are pinned by SHA.
3. **Checkpoint metadata:** the actual weight file records version
   `8.0.0.dev0`, date `2022-12-30T00:12:08.084698`. This evidence must not be
   described as a model trained with v8.2.0. It is the official v8.2.0 release
   attachment exported with the pinned v8.2.0 implementation.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Exporter commit ZIP | 1,637,624 | `49c9e09609b01acd70f6548361a08166c2e2ca7118d2bdcbe49de3e441d686d9` |
| Original official weights | 6,549,796 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| Exported ONNX | 12,823,520 | `2b0f061c461283adafe0706e484af8651e9fea625e616f9bcbf542f9020ebbe3` |
| Original astronaut image | 791,555 | `88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5` |
| Resized input PNG | 647,739 | `c055d078281d8af080bed7480d872e39e66790efc67acb95109bdee7b95dd8c1` |
| Local RGBA JSON data source | 5,796,573 | `55cbdd711cbeb1d77437db8d42e99c5b42b09339bc8b70b60538d24d7d08a1c9` |
| Raw CPU output `.npy` | 2,822,528 | `8035d774e35088023928529b0299f42a5ab42a7ef7d38bad99fa91df30ee01ca` |

The pinned [Ultralytics source license](https://github.com/ultralytics/ultralytics/blob/27836d34fa7b19d38af22200805aa5d25dddaedf/LICENSE),
[assets repository license](https://raw.githubusercontent.com/ultralytics/assets/main/LICENSE),
checkpoint and exported-model metadata declare AGPL-3.0. Full license copies are
retained with the private assets. The input is the [official scikit-image v0.19.3
astronaut image](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/astronaut.png).
Its pinned [`astronaut()` source documentation](https://github.com/scikit-image/scikit-image/blob/v0.19.3/skimage/data/_fetchers.py#L405-L424)
identifies the NASA Eileen Collins photograph and public-domain status. No model
or image distribution occurs through this documentation commit.

## Reproduction contract

Use a new Python 3.11 environment and verify the downloaded source, weights and
image hashes before loading them. The tested platform was macOS 26.2 ARM64 with
Python 3.11.14, pinned-source Ultralytics 8.2.0, PyTorch 2.2.2, torchvision 0.17.2,
NumPy 1.26.4, ONNX 1.16.2, ONNX Runtime 1.18.1 and opencv-python 4.10.0.84. The
manifest records the remaining installed distribution versions as well.

The actual export call used the copied filename
`yolov8n-official-v8.2.0.pt` and these options:

```python
YOLO("yolov8n-official-v8.2.0.pt").export(
    format="onnx", imgsz=640, opset=12, dynamic=False,
    simplify=False, batch=1, device="cpu", half=False,
)
```

The resulting float32 graph passed `onnx.checker.check_model`: IR 7, opset 12,
no external tensor files. Its actual input is `images: [1,3,640,640]` and output
is `output0: [1,84,8400]`. Export metadata includes the export date and source
filename, so a new export is not promised to have the recorded binary hash. The
SHA above identifies the exact model that was tested and retained.

Read the 512×512 image using OpenCV; resize to 640×640 with `INTER_LINEAR`,
convert BGR to RGB, divide float32 values by 255 and transpose to NCHW. The
letterbox transform for this square image is scale 1.25 with zero padding on all
sides. Save the same resized RGB data with alpha 255 as an RGBA integer array
under `{"rgba": [...]}` in a local JSON file. Do not generalize this zero-padding
case to non-square images.

CPU inference used `CPUExecutionProvider`, two intra-op threads and one inter-op
thread. The complete raw output was retained and all values were finite. A
same-input comparison against the PyTorch model had maximum absolute differences
of `1.3828277587890625e-5` in class probabilities and `0.002685546875` input pixels
in decoded coordinates. The smallest observed class value was approximately
`-1.19e-7`; the recorded floating-point output was not clamped to manufacture an
exact range.

## Existing browser interface

The production plugin `0.1.0+codex.20260919234350` used onnxruntime-web 1.30.0,
one WASM thread, Playwright 1.63.0 and its bundled Chromium headless browser.
The original and copied production runtime both retained fingerprint
`8635c55584176218c6eadbc829d8796531bc99887469f24f6fc2345130222d37`
before and after the run. No request mocking, runtime state injection, source
patch or relaxed CSP was used.

Declare the model, resized image and input JSON as local scene assets with their
recorded byte counts and SHA-256 values. This fragment shows the normal interface;
it is not a standalone scene:

```json
{
  "requires": ["core", "ml"],
  "dataSources": {"input": {"type": "json", "path": "input.json"}},
  "nodes": [{
    "id": "model",
    "type": "component",
    "component": "ModelRunner",
    "props": {
      "x": 20, "y": 20, "width": 600, "height": 480,
      "model": "model", "adapter": "yolo",
      "adapterOptions": {
        "width": 640, "height": 640,
        "inputName": "images", "outputName": "output0",
        "confidence": 0.25, "iouThreshold": 0.45
      },
      "preferWebGPU": false, "timeoutMs": 60000,
      "resultPath": "detections"
    },
    "bind": {"inputs": {"expr": "data.input"}}
  }]
}
```

Here `props.model = "model"` resolves the declared asset ID; `dataSources.input.path`
is a relative file path. The ordinary importer rewrites that file path to the
copied hash-addressed asset. Inputs must use this JSON data source: the first
probe incorrectly embedded all 1,638,400 RGBA values in scene props and was
rejected by the scene schema's 10,000-item array limit. That failed attempt is
retained. The successful data source is below the existing 8 MiB data limit;
the scene remains 1,451 bytes. No limit was changed.

The 12.8 MB model fits the existing 256 MiB model limit; the float32 input fits
64 MiB and the output fits 16M elements. The actual successful model execution
establishes operator compatibility for this graph. Its four decoded box channels
and 80 class-probability channels need neither a second sigmoid nor multiplication
by an objectness channel. The current adapter selects the best class, filters
with `score >= confidence`, then applies class-aware NMS. The scalar teaching
reference and pinned upstream postprocessing use strict `score > confidence`;
no candidate here had score exactly 0.25, so the distinction did not affect this
run. The difference remains explicit for boundary exercises.

## Observed result and limits

Ten CPU candidates passed the 0.25 confidence filter; class-aware IoU 0.45 NMS
retained one `person` (class 0). CPU score was `0.714219331741333`. The actual
browser output was score `0.7142198085784912`, xyxy input-pixel coordinates
`[6.562347412109375, 17.1497802734375, 454.34832763671875, 639.257080078125]`.
CPU/browser score difference was `4.76837158203125e-7`; maximum coordinate
difference was `0.00006103515625` pixels. Original-image coordinates require
division by 1.25. A lesson must bind displayed detections to the returned state;
these recorded numbers are evidence, not a substitute for executing the model.

The browser reached `ready wasm` in 1.440 s and `done wasm` 0.429 s after the
button action. CPU inference took 0.0546 s. These are single-run observations,
not general speed or accuracy claims. All 11 browser checks passed, with no
runtime, page, CSP or request errors. The separate 9-check passive import used a
new copy of the trusted blank presentation and confirmed unchanged source files
and native parts, valid scene schema, preserved model/image/data hashes and
correctly rewritten data-source paths. It did not attach, export or bundle a deck.

Private proof ID: `yolo-real-model-20260920T010045Z-a1f4a5`. It retains the original
source archive, weights, input/output tensors, venv, scripts, full reports and
two reviewed screenshots. Report and capture hashes are in the JSON manifest.

The website still rejects `.onnx`/`.pt` attachments and this ONNX also exceeds
its 10 MiB upload limit. A prepared static host asset directory exists, but no
handoff into a live task has occurred at this checkpoint. Any later handoff must
be explicit, preserve provenance and leave those upload rules unchanged; it must
not be described as website ONNX upload support. The normal CNN gate, formal
YOLO submission, author execution, final export/bundle, website delivery and
desktop Office verification remain separate work.
