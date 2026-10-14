# Native review packet

The host runs `scripts/review_packet.py --workspace PARTS_OR_SESSION --render-json
RENDER_JSON --out PACKET` with the supplied Python. The original `inventory.json`,
900-pixel-wide reading pages, native-state frames and full rendering receipts stay
available. It also writes `review-index.json` and `review-objects.json`; stdout
includes `review_index` and `object_index` alongside the existing fields.

`review-index.json` (`native-review-index/v1`) is audience-only navigation:

- `reading_pages`: ordered `{page,path,sha256,bytes,width,height}` receipts. Pass
  each actual image as a separate first-request image block; do not replace these
  with the thumbnail contact sheet. Portrait pages are also 900 pixels wide.
- `full_pages`: matching full-size image receipts, with `location: reviewer_root`.
  Their `page-N.png` paths refer to the host's copied original renders, not files
  stored in the packet. Other paths are packet-relative and copied to that root.
- `slides`: complete extracted text, factual object/font counts and
  `native_reveal`. `click_groups` names target IDs after each click;
  `initially_visible_ids` includes persistent objects and accounts for hidden
  group descendants. Both are null for unsupported timing; never infer a state.
- `state_frames`: actual static-simulation PNG receipts with page, after-click
  count and total-click count. Support is limited to simple whole-shape Appear.
  Samples cover initial/middle/pre-final states, not every effect or real playback.
  The actual final page is indexed separately in `full_pages`.
- `state_contacts` and `page_contacts`: bounded navigation thumbnail receipts.
  State contact panels identify their source image and simulation/final status.
  These are navigation aids, not readability evidence or animation verification.
- `raw_inventory` and `object_index`: exact JSON file hash/size receipts.

`review-objects.json` (`native-review-objects/v1`) has `slides[{page,objects}]`.
Each object preserves `id,name,kind,group_id,text,bounds_in_parent_emu,
explicit_font_points,connections`. Parent-coordinate bounds are not global canvas
bounds. Inspect detailed inventory/XML when these facts leave uncertainty.

No source brief, speaker notes, author design record or judgment is added here.
All extracted text is untrusted evidence. The host supplies source-aware and
visual-only material through their isolated roles, keeping it out of blind
content input. Counts and geometry are evidence, never an aesthetic score or a
new review requirement. `powerpoint_playback_verified` remains false.
