# CNN draft interaction, formula and content checks

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
candidate was installed as release `0.1.0+codex.20260919234350`; the author
subsequently restored the saved work under it. The earlier CSP finding remains
part of the evidence for the older runtime.

The formula-region correction has since passed 108 checks on three preserved
v007 scenes at 1280×720, 800×600, 1280×900 and 760×560. All 12 screenshots were
inspected. Unlike the earlier outer-box test, these checks measure every visible
KaTeX character and glyph element against the actual region and footer. Scenes
15/16 retain at least 10.236 px of lower clearance at the tightest viewport.
The exact scene hashes are:

- Scan: `d485adf09d359115cb589a45310ff390a4f73aec6340a5f9f1dffbc31a079bc3`.
- Forward: `913d51988f70006124bb5939652a0718395f72b4b0419146bcd222fdbc2de1ff`.
- Backward: `5b59e26906670b8fade0d72ed9e9141000a87dabde5ea7dc97ca33cec80e1030`.

That check used the retained `be097…` runtime. Font-patched release evidence is
separate. Final acceptance must use the current delivered PPTX/ZIP and their
exact scenes, not infer approval from these preserved drafts.

## All twenty initial formulas on the font-corrected runtime

An independent reviewer inspected all 40 normal captures from 20 preserved v007
scenes at 1280×720 and 800×600, plus 12 targeted diagnostic images. The exact
runtime is `8635c55584176218c6eadbc829d8796531bc99887469f24f6fc2345130222d37`.
Local font loading, CSP, page health and separation from controls/footers pass
throughout. The previously repaired summation subscripts remain complete.

The original strict rectangle report remains **708/720**, with twelve failures
covering character/element bounds in scenes 09, 12 and 14 at both viewports.
Temporary overflow-visible diagnostics clarify the result without rewriting it:

- Scene 09 and 12 diagnostic images are byte-identical to their normal captures.
  The typographic rectangles cross a boundary, but no visible ink is clipped.
- Scene 14 has a real, minor loss of ink at the tops of four numerator
  parentheses: approximately 0.48/0.67 CSS px. Its formula remains readable.
  `Math#math-rule` uses `x28/y600/450×48`, font size 21 and zero padding;
  a small amount of top padding can use the existing lower clearance.

Scene 14 SHA-256 is
`61b6562a27065c8867119db864bdf3451e6f3c1dea825d24ab040579e2782d7d`.
Private proof `cnn-v007-all-formulas-fonts-20260919T235232Z-a21d3e` retains
the unchanged source/runtime hashes, all images, raw report and pixel diagnostics.
Its review document SHA-256 is
`8a3ee63d2608fba166ae7a6566b993f3d3821bb3084eebe7e79fc78455c794ea`.
This initial-state check does not execute training, scene plans or animations.

## Current results versus fixed examples

A separate source review found that scene 19's fixed `6/8 = 75%` Math label is
unqualified even though editable code can change the held-out predictions beside
it. Scene 04 similarly retains the fixed dot-product example ending in 7 when
the kernel control changes. Their baseline arithmetic is correct; the learner
needs either a result bound to the current computation or an explicit baseline
label and a separate current result.

Website v30 submits these two content corrections and the scene 14 padding
correction as one labeled acceptance message, preserving existing work. The
normal worker received it as input revision 7. This is a requested repair, not
proof that the final artifact has applied it. There are five user edit messages;
the other two revision increments are plugin upgrades.

## Larger-kernel edit: required scene repair

A single real Monaco keyboard edit on scene 06 changes only `k=3` to `k=7`,
retaining input size 5, stride 1, padding 0 and dilation 1. Clicking Run causes
the `taps` binding to join a nonexistent first tap row. The whole scene enters
its generic fallback, removing the editor and Reset button. A subsequent actual
Reset click times out. The test did not reload the page or inject state to hide
the failure. Both initial and failure captures were independently viewed.

The scene SHA-256 is
`7abd2f883493e9ee857960389e4c5464db5d42bc0044d7b6d25ed54d6f8ba074`;
its source SHA-256 is
`d8bc27c02d072424a8f6d26b08a627211e301a7f64909a598fee6c575ee204f1`.
Both match the current v009 source checked before submitting the correction.
The failed computation is rolled back to the reference state; this evidence
does not claim that negative dimensions were visibly rendered.

Private proof `cnn-v007-sampling-k7-20260920T001534Z-81416c` preserves source,
screenshots, the expression error, Reset timeout and unchanged runtime hashes.
Website v31 delivers a bounded request to validate dimensions before returning
results, explain an oversized kernel through the code error output, retain the
reference/editor/Reset and guard the absent-tap display. The normal worker
acknowledged it at input revision 8. The repaired invalid-input/Reset path and
existing valid controls require a new actual check; no runtime upgrade is needed
to make this scene correction.

The repaired v009 sampling snapshot subsequently passed **71/71** independent
checks. Seven screenshots were actually viewed. The same real `k=7` edit now
explains that effective kernel 7 exceeds padded input 5, retaining the editor and
Reset without a runtime error. Actual Reset plus Run restores side 3 and nine
positions; real valid controls yield side/positions `2/4`, `5/25` and `1/1`.
The repaired scene SHA-256 is
`ee41226943537d11bb5e88fbbee46bc3a9bca367ef5666205882f5b469657ac7`,
and its source SHA-256 is
`51fd8aa70c4f7ca5da56ad070c89c5019ba9470682e9c7654aeb974d34e4aaf6`.
Private proof `cnn-v009-sampling-k7-20260920T002758Z-8a184a` retains the original
failure and the first new 70/71 report whose lone failure read `innerText` from an
SVG group. The corrected probe reads its internal HTML. The final report SHA-256
is `ba60fa089119b1a5b6a4cf2a52c42bd15aa29104522e7faa95eed992e4ec6e5c`.

## Bounded follow-up on baseline, formula fit and current accuracy

An independent check of v009 scenes 04, 14 and 19 inspected ten captures:

- Scene 04 now labels the fixed arithmetic as the `K[0,0]=1` baseline. A real
  control change to 2 produces contributions `[2,-2,8,0]` and sum 8.
- Scene 14's normal and overflow-visible diagnostic formula captures are
  pixel-identical at 1280×720 and 800×600. The former parenthesis crop is repaired.
- Scene 19 correctly derives its count from the actual worker result: one real
  Monaco learning-rate-zero run gives four correct cases out of eight, and Reset
  restores the six-correct reference. Its new TeX binding, however, over-escapes
  the commands. The visible equations are `6/8=75` and `4/8=50`: the percent sign
  and held-out label disappear despite no KaTeX error. This remains a required
  formatting correction, not a numerical-training failure.

The respective scene hashes are
`7cb99c805f1944f8b454b93a0f8e95925565ba0998f68dc80e959181f6c9c774`,
`85a244ec32d6688da47a9e5ba3b73eba62437436062b68028631912affdbd33f` and
`3cdf7e631d8fd9bc911d51c2eda735e465ed22486b8a50e9724bc5351c9c5123`.
Private proof `cnn-v009-three-repairs-20260920T002920Z` retains **15/18** checks;
all three failures describe the same missing units/label in the initial, changed
and reset views. Website v32 requests the exact escaping correction, adequate
percentage precision and a fresh native fallback. Final scene/artifact approval
remains pending.

The corrected scene 19 snapshot subsequently passed **61/61** independent checks
with three actually inspected screenshots. The initial formula displays
`6/8 = 75% held out`. One real Monaco edit to `LEARNING_RATE=0` and one Run
produce `4/8 = 50% held out`; all eight selected examples match their returned
class, probability, feature value and 36 pixels. Reset restores the complete
original source and reference result. The percent sign and label remain visible
at 800×600. No page, console, CSP or network failure occurred.

The repaired scene SHA-256 is
`ef1c806d7732cdbc7178c2bd0f16b045ac36eeda3f01d65af3c9e2a96bcd8f50`.
Private proof `cnn-v009-scene19-repaired-20260920T004420Z` retains the unchanged
source and runtime fingerprints. Its review SHA-256 is
`b9aaa545e947f70a3a05ba1cf3f5779213e77c5126e3d270b9d03c5debea5495`;
the raw report SHA-256 is
`b34b2c50e13674572b3c94bcf48795df03597bf787ff4cfee980f06cae7b75cd`.
The preceding 15/18 report remains unchanged. Scenes 04 and 14 were not rerun.
This scoped success still requires correspondence with the eventual frozen
and website-delivered artifacts.
