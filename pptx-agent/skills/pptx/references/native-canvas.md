# Native canvas capabilities

Use scripts/native_canvas.py when repeated XML, text-fit errors or image composition
work would consume design time. It is an object utility, not a slide template or a
replacement for your composition decision. Snapshot the current native workspace
first; then validate, render and inspect the actual result. Keep page order.

## Text and typography

Select an actual installed font file, point size, color, available width and height.
The helper measures with that font, keeps requested breaks, preserves ordinary
unbreakable Latin terms and estimates glyph height. It does not shrink text or add
card backgrounds. If the allocated height/width cannot fit, edit the wording or
recompose. CJK wrapping is a basic estimate, not full language-layout compliance;
check glyphs, punctuation, line breaks and actual renders.

```
python PLUGIN/skills/pptx/scripts/native_canvas.py measure --text 'Your actual title' --font '/Library/Fonts/Arial.ttf' --size 36 --width 7
python PLUGIN/skills/pptx/scripts/native_canvas.py text --workspace WORKSPACE --slide 1 --text 'Your actual title' --font ACTUAL_FONT_FILE --size 36 --width 7 --x .6 --y .5 --max-height 1.5 --color 202020
```

Paths/fonts, numbers and color above are command examples, not prescribed style.
For a .ttc face, choose --font-index explicitly. Essential qualifiers and explanations
remain visible; the helper cannot judge which words to remove.

## Image and editable-type integration

Use an acquired/generated task-local normalized PNG/JPEG/GIF. Choose `contain` to
retain all of it or `cover` for native cropping; inspect the crop. `back` places the
image behind existing objects, `front` above them. Create editable text separately
with your own focus, scale and contrast. This supports full-field backgrounds,
image beside type, overlapping type, contextual details and illustration/text
relationships without flattening a slide. Ordinary shapes/connectors remain native.

```
python PLUGIN/skills/pptx/scripts/native_canvas.py image --workspace WORKSPACE --slide 1 --file assets/SELECTED.png --box 0 0 13.333 7.5 --fit cover --layer back
```

For video/audio use task-local media-embed.py and its required poster/icon; a static
image does not verify playback. Do not import private source directories.

## Editable quantity comparisons

`bars` adds a native horizontal chart with a passive editable workbook, direct
value labels and a zero baseline. Supply labels, finite nonnegative values, one
explicit unit and chosen colors per category. Different units need separate
appropriate displays; negative/stacked/time-series cases need another faithful
native implementation. Do not invent source values or hide assumptions.

```
{"labels":["Category A","Category B"],"values":[12,9],"unit":"CNY million","colors":["A84D3D","71816B"]}
python PLUGIN/skills/pptx/scripts/native_canvas.py bars --workspace WORKSPACE --slide 1 --data values.json --box .7 2 9 4 --font-family Arial --font-size 18
```

These are example values/colors only. Position an editable unit/title where it
belongs and inspect actual chart labels, scales and chart editability after export.
Existing groups/connectors use native_structure.py. The canvas helper makes no
claim about aesthetic quality, factual provenance or PowerPoint playback.
