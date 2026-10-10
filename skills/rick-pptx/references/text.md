# Native text

Give title, body, number, quote, caption and code distinct roles through size, weight,
line width, placement and spacing. Do not use every role on every page or randomly
change fonts. Test actual long titles and CJK/Latin mixed content in the native render.
Use semantic line breaks, keep units with values, and avoid orphaned punctuation.
Inspect font availability and substitution on the target renderer; setting a font
name does not install it. Fix repetition and grouping before shrinking important text.
Body margins, paragraph spacing and hierarchy must work at the intended viewing size.
Short source labels may be quiet; necessary conditions must remain readable.
For dense CJK titles, check actual bold-face availability and adjacent glyph spacing.
Simulated bold can make strokes look merged even without geometric overlap; prefer
a suitable real weight and adjust tracking selectively after inspecting the render.

Text lives under `p:txBody/a:p`, usually in `a:r/a:t`. A visible phrase can span multiple runs or fields. Inspect the actual run boundaries before matching. Preserve `a:rPr`, paragraph properties, `a:endParaRPr`, hyperlinks and fields. Escape `&`, `<` and `>` in text; keep `xml:space="preserve"` when boundary whitespace is meaningful.

For a simple title change replace only the target `a:t` content, checking the match is unique. To add text copy a neighboring run/paragraph with its schema order. Font size `sz="2400"` means 24 pt; `a:latin/@typeface` changes Latin font; `a:ea` controls East Asian fonts. Colors use `a:solidFill/a:srgbClr` or inherited scheme colors. Body insets, wrapping, autofit and line spacing affect overflow; render after changing them.
