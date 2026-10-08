# Native staged explanation

New presentations must include content-led native click reveals. Entirely static
output, slide transitions alone or a decorative title entrance do not fulfill
Rick's presentation requirement. Cover/single-message pages may be static; preserve
existing source behavior for faithful conversions and scoped edits. Historically
admitted tasks retain their protected behavior contract.

For multi-step processes, arguments, worked examples and layered diagrams, select
click_reveal and write a compact speaking sequence in source-notes.md: entry
context → each presenter click's meaningful group → persistent context → final
complete readable view. Group an object with its label/connector, or a reasoning
step with its evidence. Keep orientation and essential conditions visible. Avoid
word-by-word clicks, long automatic sequences, premature answers or hiding the
whole page until one click. The number and effect follow the explanation, not a
fixed click count. All required content remains readable in the final view.

For simple entrance groups, inspect target IDs with `pptx.py inspect N`, then use:

```
python scripts/native_builds.py --workspace PATH --slide 2 --steps '[[4,5],[6,7]]'
```

Each group appears on a separate click; other objects are initially visible. The
helper creates native Appear timing on editable objects, snapshots before mutation
and rejects missing/repeated targets or an animated group plus its child. Existing
timing is preserved unless `--replace` is explicitly selected within editing scope.
It is a small convenience, not a restriction to Appear; use verified OOXML for Fade,
emphasis, paths or more complex behavior when the explanation benefits.

Inspect initial/intermediate/final states and actual playback when available.
Check that contextual objects persist, related elements enter together and exported
targets/click groups survive. `scripts/review_packet.py --workspace PATH --render-json
RENDER_JSON --out DIRECTORY` collects timing and full-deck contact sheets, and renders
separate initial/middle/pre-final simulations for supported simple whole-object Appear
builds. It labels unsupported effects and does not certify playback. A host may run
this automatically; do not duplicate the same state-copy work without a reason.
If using other temporary state copies, keep them separate
from the deliverable and do not publish their page numbers as actual deck pages.

Reference: [Microsoft PresentationML animation](https://learn.microsoft.com/en-us/office/open-xml/presentation/working-with-animation).

Timing under `p:timing` uses shape targets such as `p:spTgt/@spid`. Moving or renaming a shape does not require changing its ID. If deleting or duplicating animated shapes, inspect timing target IDs, build lists, connector references and transitions. Preserve unknown extension markup, `mc:AlternateContent`, Morph metadata, SmartArt parts, OLE and embedded workbook bytes unless the user explicitly asks to edit them.

The structural validator is not an animation-semantic validator; LibreOffice is not a PowerPoint animation player. For an animation-specific change that cannot be verified, report that limitation and retain a recoverable snapshot. Never strip long-tail content merely to make rendering pass.
