# Native staged explanation

For live/dual-use multi-idea explanations, plan what is visible on entry, what each
presenter click introduces, what stays as context, and the final readable view.
Group by meaning: an object with its label/connector, a reasoning step with its
evidence. Keep orientation visible. Avoid word-by-word clicks, long automatic
sequences and premature answers. Static briefs, simultaneous comparisons, covers
and single-message pages can remain complete without invented exceptions paperwork.

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
