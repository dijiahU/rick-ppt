# Native entrance row repair — 2026-10-19

Rick reported that the weekly-template workflow deck's second and fifth outline
rows were already visible at entry, before the first, third and fourth rows.
The old writer used one preset entrance node containing several different shape
targets per click. The first body-text targets were rows 1, 3 and 4; rows 2 and 5
were later targets in those nodes. This matches the reported viewer behavior.

The writer now emits one preset Appear effect per object. A logical click has
one `clickEffect` followed by explicit zero-delay `withEffect` object rows under
the same click branch. Logical grouping, object IDs, drawing order and native
editability stay intact. No slide objects are grouped/reordered to obtain this.

The old static preview reader treated all actions in the multi-target node as
hidden until the intended click, effectively assuming the behavior being tested.
It now verifies supported sequence/wait/delay structure and one target per effect,
and groups explicit click/with-previous rows. Legacy multi-target, delayed,
automatic, paragraph and unknown timing remain unsupported; they do not generate
optimistic simulated click states. Static previews still do not certify playback.
The existing visual-review index adds readable objects/text for each click, and
the portability report locates legacy multi-target entrance nodes and target IDs.
No additional model review stage or routine whole-deck slideshow is introduced.

For the specific five-page deck a separate repaired candidate was produced.
Only the five slide parts' `p:timing` changed; object trees and every other package
part are unchanged. Actual LibreOffice final render pixels match the original on
all five pages. The logical click counts remain 2/3/2/2/2, and eleven supported
initial/intermediate static frames were produced. Original exported bytes were
recovered exactly (SHA-256 `0ffe4d5e88551c4cd6209afa999f87833c417c54d9adbae863da2afc7e02c257`).

The native-build, review-state/index, batch and compatibility suites pass 53
tests; native-canvas and tool-preparation runner suites pass another 27 tests.
The standalone packager now includes the review-index module imported by its
review-packet helper, avoiding an unresolved runtime dependency.

Mac WPS UI automation failed with `noWindowsAvailable`; this is not a successful
slideshow test. Windows WPS and PowerPoint playback remain unverified. The inferred
failure mechanism and repaired structure must be distinguished from actual
target-viewer confirmation. Preserve historical originals and frozen reviews.
