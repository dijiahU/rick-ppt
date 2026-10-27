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
Replace HOST_PYTHON with the exact tool-manifest.json.python or supplied host
interpreter; do not invoke bare python/python3. PATH may be session_dir or parts_dir
from the manifest. Keep the global pptx --workspace argument before inspect.

```
HOST_PYTHON scripts/native_builds.py --workspace PATH --slide 2 --steps '[[4,5],[6,7]]'
```

Each group appears on a separate click; other objects are initially visible. The
helper creates native Appear timing on editable objects, snapshots before mutation
and rejects missing/repeated targets or an animated group plus its child. Existing
timing is preserved unless `--replace` is explicitly selected within editing scope.
It is a small convenience, not a restriction to Appear; use verified OOXML for Fade,
emphasis, paths or more complex behavior when the explanation benefits.

Each object receives its own preset entrance row. The first object of a click
uses `clickEffect`; the others use `withEffect` in the same zero-delay click
branch. Never put several different shape targets in one preset entrance row:
some viewers may initialize only the first target as hidden, leaving the others
visible at entry. For example, revealing table rows 1+2, then 3, then 4+5 must not
leave rows 2 and 5 already visible. A valid target ID list alone cannot detect this.

## Animation check within authoring and visual review

Use the fast path by default; a separate slideshow session or animation review
stage is not required for every deck.

While authoring each animated page, inspect native target IDs and the complete
click-group order against the speaking sequence. Check entry context, persistent
orientation, labels/connectors/evidence entering with the relevant object, premature
answers (including translated labels), and the complete final view. Fix a missing
or mistimed semantic group before continuing. Reuse the page's normal final render;
do not rerender the whole deck after each click or page.

At the existing frozen-candidate visual review, reuse the host's animation evidence:
`scripts/review_packet.py --workspace PATH --render-json RENDER_JSON --out DIRECTORY`
collects native timing/click groups and batch-renders initial/middle/pre-final
simulations for supported simple whole-object Appear builds. The final view uses
the existing full-page render. Inspect the state contacts, then open only frames
needed to resolve a concrete issue. These samples do not cover every click; inspect
the complete group list and create a targeted extra state only when it is necessary.
Do not generate another packet or duplicate unchanged evidence. Keep temporary
state copies separate from the deliverable and its page numbering.
The supported-state reader verifies explicit click/with-previous rows, target
identity and wait/delay structure before making simulations. Legacy multi-target
entrance rows, automatic/delayed sequences or unknown timing are unsupported,
not an assumed click sequence or a pass. The index includes readable per-click
object names/text as well as IDs. Compare that list with the intended semantic
units; a correct time tree does not establish that the author's groups are sensible.

Actual WPS/PowerPoint slideshow playback is a targeted diagnostic when explicitly
requested, required by the task's playback contract, or needed to resolve a concrete
compatibility concern (such as a translated label appearing early, triggers, motion,
or embedded media). First check whether the host exposes a suitable player. Test
only affected pages and clicks; do not automatically click through the whole deck,
launch/install a player, or try repeated UI workarounds as routine review. If the
player is unavailable, record the unresolved playback limitation. Unsupported
simulation is unknown, not a pass and not a reason to remove native behavior.

Record native timing inspection, static state simulation and real playback
separately in the existing review/delivery evidence. For real playback record the
PPTX hash, player/version, pages/clicks and observed result; a WPS check verifies
that scope in WPS only. Never infer playback from exported XML or static renders,
or mark unplayed pages as playback-verified. Recheck changed scope only.

Reference: [Microsoft PresentationML animation](https://learn.microsoft.com/en-us/office/open-xml/presentation/working-with-animation).

Timing under `p:timing` uses shape targets such as `p:spTgt/@spid`. Moving or renaming a shape does not require changing its ID. If deleting or duplicating animated shapes, inspect timing target IDs, build lists, connector references and transitions. Preserve unknown extension markup, `mc:AlternateContent`, Morph metadata, SmartArt parts, OLE and embedded workbook bytes unless the user explicitly asks to edit them.

The structural validator is not an animation-semantic validator; LibreOffice is not a PowerPoint animation player. For an animation-specific change that cannot be verified, report that limitation and retain a recoverable snapshot. Never strip long-tail content merely to make rendering pass.
