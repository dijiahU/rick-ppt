# Slide and shape mutations

Shapes live in `p:cSld/p:spTree`: `p:sp` (text/geometry), `p:pic`, `p:graphicFrame` (tables/charts), `p:cxnSp`, `p:grpSp`. `p:cNvPr/@id` must be unique within the slide, including group descendants. Names are useful navigation aids, not stable IDs.

Move/resize by targeted changes to `a:xfrm/a:off` and `a:ext`; graphic frames use `p:xfrm`. Preserve rotations and flips. To align three nodes set their x positions from widths and a common gap; retain all IDs and content. Fill and border edits belong in shape properties. Copying a shape requires a new cNvPr ID and adjustment of internal connector/timing references. Deletion also requires checking connectors and animations.

To duplicate a slide, snapshot first; copy slide XML and its `.rels` to new filenames, allocate a new presentation rId and p:sldId numeric ID, insert in presentation order and add a content-type Override. Shared images/charts may remain shared unless the user needs independent editing. Notes often point back to their slide and must be copied with their relationships or omitted consistently. To delete a slide remove its p:sldId, presentation relationship, part, part relationships and content-type Override; inspect notes/back-references. Do not globally renumber IDs. Validate and render the deck.
