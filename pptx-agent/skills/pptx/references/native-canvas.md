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

## Safe object handles and semantic groups

Python callers can use add_text/add_image/add_bar_chart and add_shape; each returns
workspace, slide and shape_id. Feed those handles directly to add_connector,
semantic_group and reveal. Cross-workspace/page handles, missing targets and
non-adjacent groups are rejected before writing. Grouping preserves coordinates,
member IDs and drawing order; it adds no visible frame. Existing source timing is
preserved unless replacement is explicitly authorized. Keep one author writing
the current page; helpers do not coordinate competing direct XML editors.

add_shape requires explicit geometry, fill (or None), stroke (or None), line_width
and name. It does not assign a card style. add_connector requires actual endpoints,
chosen connection sites, ink/width, arrow and explicit start/end coordinates;
inspect routing and labels in production renders and target PowerPoint. reveal
accepts lists of handles per meaningful click, including separate objects sharing
a click without changing their drawing order.

```python
# Import native_canvas from the exposed plugin scripts directory.
label = canvas.add_text(workspace, 1, actual_text, selected_font_file, chosen_size,
                        chosen_ink, x=x, y=y, width=w, max_height=h)
detail = canvas.add_image(workspace, 1, selected_asset, detail_box,
                          fit='contain', layer='front', task_root=task_root)
# Adjacent objects only; name expresses what the viewer learns on this click.
unit = canvas.semantic_group(workspace, 1, [label, detail], name='Observed result')
canvas.reveal(workspace, 1, [[unit]])
```

Measurements use host fonts and are estimates. render-environment.json records
production renderer version, requested/resolved font families and input SHA when
the host renderer is used. A Mac font file need not exist inside the Linux renderer;
check substitutions and actual output instead of treating font metrics as proof.
Do not install fonts/tools in task jobs or claim PowerPoint compatibility from a
LibreOffice preview. Test actual exported playback when the target player is available.
