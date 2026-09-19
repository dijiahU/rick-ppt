# Native pictures

`p:pic/p:blipFill/a:blip/@r:embed` resolves through the slide's `.rels` to `ppt/media/…`. Bounds are under `p:spPr/a:xfrm`; cropping uses `a:srcRect` (100000 means 100%). Preserve effects and crop unless changing them is intended.

Replacing bytes in an existing media part changes every consumer. Inspect reverse refs first. For a single picture replacement, add a new media filename and content type if needed, retarget only that picture's relationship (allocate a new rId if shared within the slide). Match the declared image format to actual bytes. For adding a picture, copy a valid p:pic structure, allocate cNvPr ID and image relationship and set bounds. To delete, remove the p:pic and its relationship only when no remaining object uses it. Orphan media is permitted.

SVG commonly has a fallback bitmap and an extension reference. Preserve both and update deliberately. Render to inspect aspect ratio and clipping; never silently replace native objects with screenshots.
