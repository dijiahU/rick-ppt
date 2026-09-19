# Verified compatibility

Recorded 2026-09-20. `Verified` below means an actual test was run on that target;
it is not inferred from a manifest or another renderer. Desktop UI automation was
unavailable in this execution environment, although macOS PowerPoint is installed.

| Target | Native static / fallback | Runtime | Keyboard / mouse | Media | Optional packs |
| --- | --- | --- | --- | --- | --- |
| Chromium on macOS, standalone | Runtime fallback capture verified | Verified | Verified, including drag/slider | Actual video/audio tests verified | JS/Python, Three GLB, ONNX WASM, local map, math and custom plugin verified |
| LibreOffice on macOS and isolated renderer | Native and snapshot fallback rendered | Not executed | Not applicable to static render | Static preview only | Not executed |
| PDF exported through LibreOffice | Verified static pages | Not interactive | Not applicable | Static preview only | Static fallback only |
| PowerPoint macOS | Not desktop-verified | Not desktop-verified | Not desktop-verified | Not desktop-verified | Not desktop-verified |
| PowerPoint Windows | Not desktop-verified | Not desktop-verified | Not desktop-verified | Not desktop-verified | Not desktop-verified |
| PowerPoint Web | Not verified | Not verified | Not verified | Not verified | Not verified |

The XML ContentApp manifest passed the official validator; the OOXML relationship
graph is checked against the pinned Microsoft fixture. Actual trusted localhost
HTTPS was reached from Chromium without ignoring certificate errors. Neither
check proves Office's settings injection or save/reopen behavior.

The portable macOS start/stop lifecycle was exercised. Windows PowerShell scripts
are supplied but have not been executed on Windows. ONNX WASM was exercised;
WebGPU selection is capability-dependent and is not reported as verified here.
Mac, Windows and Office Web differ in sideloading and loopback connectivity. Do
not infer cross-platform compatibility from a single successful browser run.

Use [the manual checklist](manual-powerpoint-verification.md) to add target-specific
evidence. Preserve screenshots, app/OS versions, tested deck hashes and any error.
Only update a cell after completing the corresponding actual target test.
