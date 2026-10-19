# Windows WPS compatibility

The default recipient target is Windows WPS. Continue producing one standalone,
editable PPTX. Apply these checks during the existing authoring and visual review;
do not add a review stage, routine full-deck slideshow or a Windows-verified label
without actual target-viewer evidence. Preserve historical files and scoped edits.

## Fonts and text

- New English/Latin text, numbers and ordinary Latin punctuation use **Times New
  Roman**; Chinese text and punctuation use **SimSun (宋体)**. Set explicit run
  fonts and major/minor theme defaults, including inherited text, table cells,
  chart categories, axes and data labels. Preserve explicit user/template choices.
- Measure with genuine selected files in `fonts/index.json`. `simsun-regular` is
  the actual SimSun face, not Songti SC, Noto Serif or a renamed replacement.
  Times New Roman regular/bold/italic faces are listed separately. SimSun Regular
  is not a supplied bold face; use size/spacing for hierarchy. Check actual mixed
  text, punctuation, Greek/math symbols and any missing glyphs.
- Do not acquire new families merely for decorative variety. An explicit user or
  template requirement, or a functional need such as mathematical notation, can
  justify another font. Record its actual family, weight, glyph coverage, source,
  and the recipient-availability or verified editable-embedding route in source
  notes. Honor embedding permissions and no-subsetting flags. A font download or
  a file in the authoring folder is not an embedded font in the PPTX.
- If the selected fonts are unavailable, disclose the actual missing resource;
  never claim a substitute is Times New Roman/SimSun. Prefer a permitted compatible
  fallback only when the user's requirements allow it, and record the substitution.
- Use deliberate text-box margins, spacing and meaningful line breaks with room
  for renderer differences. Avoid symbol-font arrows/icons; use editable native
  geometry for graphical arrows. Keep analytical text and equations editable.

## Arrow and group geometry

- For anchored connectors, ensure `stCxn/endCxn` target the intended shape IDs and
  valid connection sites of their actual geometry. Compare the written endpoint
  coordinates with those sites after all parent/group transforms. Anchors and the
  drawn line must describe the same route. The presence of anchors alone proves
  neither correct geometry nor Windows WPS behavior.
- Prefer simple explicit straight or elbow routes. Check start/end direction,
  arrowhead, nonnegative extents, rotation, flipH/flipV, and child-to-parent units.
  Never assume every preset/group has the same site count or site ordering.
- Keep a diagram's linked elements in a coherent coordinate space. Scale groups
  through off/ext/chOff/chExt consistently; do not independently scale the line
  and its endpoints or rely on a different viewer's automatic rerouting.
- If a binding cannot preserve the intended complex route reliably, use an
  explicit editable native path with the correct arrowhead and no misleading
  bindings. Do not rasterize the whole diagram or remove useful valid anchors
  indiscriminately. Preserve supplied geometry and unrelated source objects.

## Verification scope

Check structure and preview geometry first. Reuse existing previews and repair only
affected objects. If Windows WPS is available, compare the affected pages in its
actual saved/slide-show state; investigate missing fonts, endpoint movement and
unsupported effects. Static Mac/LibreOffice renders do not certify that result.
If it is unavailable, state that Windows WPS is unverified. Keep the existing fast
animation structural/state checks; use targeted actual playback for known failures.

WPS documentation:
- [Embed fonts in a presentation](https://www.wps.cn/learning/question/detail/id/12263.html)
- [Mac font embedding](https://www.wps.cn/learning/question/detail/id/335210.html)
