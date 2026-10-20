# Windows WPS portability hardening — 2026-10-19

The native authoring tools now reject contradictory connector bindings before
writing a page. Rectangle/rounded-rectangle/diamond sites differ from ellipse
and triangle sites. Endpoint checks include object flips/rotation and ancestor
group coordinate transforms. Unsupported sites are not guessed; authors can
anchor supported children or retain explicit editable unbound native geometry.
Existing source objects and historical exports are never silently rewritten.

Native text verifies glyph coverage against the actual selected font files,
including separate Chinese/Latin runs, before measurement/writing. It explicitly
sets `noAutofit` and paragraph-end font names. Genuine Times New Roman and SimSun
remain defaults; no fonts were embedded or newly downloaded by this change.

Normal export records static compatibility findings, slide part/object IDs,
font-family inventory and declared embedded-font resource links. The session
report is bound to the exported PPTX SHA-256 and linked from workspace state.
It is not a new audience-review stage or a target-viewer certification gate.
The prepared author tool guide exposes the diagnostic command and explains how
to act on scoped findings without restyling unrelated source material.

Verification:

- 39 focused unit tests passed for native batches, geometry, text, timing/state
  and compatibility reporting; native canvas/quality/tool-preparation/bridge
  runner suites passed another 40 tests.
- The broader unit run passed 134 tests before the final triangle-site addition.
  Three legacy Content Add-in tests failed under the current single-file policy;
  the same three failures were reproduced against an isolated unmodified HEAD.
  The separate historical interactive suite requires unavailable `aiohttp` and
  was excluded. These are not evidence of target-viewer compatibility.
- A real LibreOffice export of a native editable fixture was rendered and
  visually inspected: mixed Chinese/Latin text, rectangle/ellipse endpoints,
  reverse arrow direction, and two native click targets. The static report has
  zero findings and two verified endpoint bindings. Rendering does not verify
  the two clicks in an actual slideshow.
- The rebuilt standalone package passed its doctor check and read-only
  diagnostics on that workspace.

Windows WPS actual viewing/playback is **unverified**. Recipient font availability,
custom geometry beyond supported site checks, arbitrary viewer rerouting, complex
effects and full editable font embedding are not certified by this release.
