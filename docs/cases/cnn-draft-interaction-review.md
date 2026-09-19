# CNN draft checks on the repaired editor runtime

These are bounded checks of retained v005 draft scenes and native previews,
not acceptance of the unfinished 20-slide delivery. They use immutable release
`0.1.0+codex.20260919230549`, whose runtime fingerprint is
`be097a482201dd70ecdc8755b2a1c4aee5f0f54402878c42b43caa42365cf5fd`.
The preserved source files were copied into separate proof directories and
rehashed after execution; neither the old attempt nor the live task was edited.

## Multi-channel convolution, ReLU and pooling

All **196 assertions passed** through actual DOM controls and JavaScript
workers. All 14 captured screenshots were opened and inspected. No additional
visible defect, page exception or external request was found in this scope.

| Scene | SHA-256 | Assertions / captures |
| --- | --- | --- |
| 07, channels | `77fd7c55c0b6842f36ee3fb882d0c9e225832ad8f7b057055dc60b3dc5292eac` | 43 / 3 |
| 08, ReLU | `e393d966b921dc478a7bd0e1a2ba2698ffbb69419b2e57cdb8ef788741822645` | 62 / 5 |
| 09, pooling | `bd93a89d18747b6d804accf22ec61f4afb91a4e4d1ea860ce0bfda6257f3ba13` | 91 / 6 |

- Changing the input side from 5 to 7 changes the output from `[4,3,3]` to
  `[4,5,5]`, retaining four filters and 112 parameters. The displayed channel
  contributions `[9,9,0]`, bias `0.5` and result `18.5` match computation.
- ReLU on `[-2,0,3]` with upstream derivative 1 returns `[0,0,1]`. The retained
  upstream-3 example returns `[0,0,3]`; the chosen derivative at zero is stated.
- Pooling `[[1,3],[2,4]]` returns max 4 and average 2.5. With upstream 1, max
  backward assigns 1 only to the bottom-right entry; average backward assigns
  0.25 to each entry. The original upstream-8 example, a changed winner and
  tied maxima also pass, using the documented first row-major tie convention.
- Reset restores each original source/input/reference view, clears the computed
  result and permits a successful new execution. No runtime state was injected.

The private proof is identified as
`cnn-v005-c04-c06-20260919T231554Z-d582a3`; its report includes the harness,
all assertions, worker results, scene/runtime hashes and screenshot hashes.

## First eight native previews

An independent reviewer opened the latest published 1600×900 PNG for each of
pages 1–8. The corrected page 1 and page 7 previews supersede their earlier
drafts without deleting them. No obvious overlap, clipping or arithmetic error
was found in those eight exact images. The reviewed material includes the
50-parameter model, 40/20/5 locality/sharing comparison, cross-correlation 7
versus flipped-kernel 5, sampling sizes 3/2/5/1, 112 channel parameters and ReLU.

The private proof `cnn-native-v005-first8-20260919T231753Z` records all eight
PNG hashes and selection timestamps. Pages 9–20, later changes, final sequencing,
projection-distance code readability and actual PowerPoint playback remain
outside this limited check.

## Full-CNN finite differences through the browser controls

Actual clicks followed `Complete CNN check → Run inputs → Reset → Run inputs`.
Both programs ran exactly once in local Pyodide. Scene SHA-256 is
`1652ad3613de084c15942bf339ef320bbfcdadcc785d11b0e8288fc97d5e7292`;
the embedded complete checker SHA-256 is
`1783033aef5ddc9e3c35598e0dd6bb9c1970f396b5a1201ec709037d730641d1`.
The latter differs from the previously audited source only in its unused
training function's checkpoint collection; executed derivative code is unchanged.

| Parameter family | Actual analytic derivative | Absolute finite-difference error |
| --- | ---: | ---: |
| Convolution weight K | -0.0003116363521444964 | 9.0166e-12 |
| Convolution bias b | -0.03425252389552196 | 1.1629e-11 |
| Classifier weight W | -0.023743121543069224 | 3.5574e-12 |
| Classifier bias a | -0.502496665080199 | 3.3082e-12 |

All derivatives are nonzero, epsilon is `1e-5`, and both signed perturbations
retain the ReLU gates. Reset restores the original small fixture and clears the
result; running again gives analytic 12 and numerical `12.000000000256248`.
Three actual screenshots were inspected; results and controls are readable.

The original private report retains its **43/46** result. One failed QA assertion
incorrectly demanded CPython's rounded text; saved DOM and Pyodide values show
the correct ten-decimal display `12.0000000003`. A separate posthoc record fixes
that assertion without rerunning either program or rewriting the original
evidence. The resulting functional/numerical subset is **40/40**. The other two
failed assertions describe the same real font CSP violation. The proof identifier
is `cnn-full-gradient-browser-review-01`; its original report SHA-256 is
`1f5a291722a62fe80af425e5f7c79991dba92ca1c6c2cef0734ffa6e3998879c`.

## Remaining checks

Vite inlined the 3,624-byte `KaTeX_Size3.woff2`, which production `font-src 'self'`
blocks. Same-origin WOFF/TTF fallbacks remain available and the inspected formula
is readable, but this run is not a zero-CSP pass. A separate
[build correction](../release-smoke-20260920.md#cnn-discovered-local-font-packaging-correction)
now keeps fonts as same-origin files without loosening CSP. Its nine production
pack checks pass, including actual Size3 loading and zero CSP violations. That
candidate remains separate from the immutable runtime used by the running author.

The separately acknowledged formula-region clipping still requires resolution.
Final acceptance must use the current delivered PPTX/ZIP and their exact scenes,
not infer approval from these preserved drafts.
