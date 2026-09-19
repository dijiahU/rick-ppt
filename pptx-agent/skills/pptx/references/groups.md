# Group transforms

`p:grpSpPr/a:xfrm` contains `off/ext` in parent coordinates and `chOff/chExt` in child coordinates. For an unrotated, unflipped group, parentX = offX + (childX - chOffX) * extX/chExtX; Y is analogous. Nested groups compose these transforms. Rotation and flips require their corresponding transforms.

To shrink a whole diagram, change the group extents and offset, preserving child coordinates. Editing each child as though it were in slide coordinates distorts spacing. For child-only resizing work in that group's coordinate system. Do not set chExt to zero. Keep IDs unique across all descendants and render after changes.
