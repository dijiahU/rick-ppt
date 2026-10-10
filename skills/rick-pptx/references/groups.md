# Group transforms

`p:grpSpPr/a:xfrm` contains `off/ext` in parent coordinates and `chOff/chExt` in child coordinates. For an unrotated, unflipped group, parentX = offX + (childX - chOffX) * extX/chExtX; Y is analogous. Nested groups compose these transforms. Rotation and flips require their corresponding transforms.

To shrink a whole diagram, change the group extents and offset, preserving child coordinates. Editing each child as though it were in slide coordinates distorts spacing. For child-only resizing work in that group's coordinate system. Do not set chExt to zero. Keep IDs unique across all descendants and render after changes.

Name semantic units, such as a process node with its label or a complete comparison card. Keep independently editable text/shapes inside each group. A group is useful when the unit should move or resize together; a group count alone does not measure quality. Preserve unrelated inherited template objects during a scoped edit.

Use the explicit helper after creating native objects:

```sh
python scripts/native_structure.py --workspace WORKSPACE --slide 1 group --ids 12 13 14 --name 'Input node'
python scripts/native_structure.py --workspace WORKSPACE --slide 1 anchor --connector 20 --start 12 --end 17 --start-site 3 --end-site 1
```

Use the configured Python and the installed absolute script path. Group members must have one parent and be adjacent in drawing order; the helper rejects ambiguous changes. It preserves child coordinates, IDs, relationships and animation targets. Anchoring requires an actual `p:cxnSp` connector and connection sites valid for the endpoint shape geometry; choose those indices explicitly. Preserve its existing native path/geometry. Export and render afterward, checking the original coordinates and connector direction. Anchors support later editing; static rendering is not proof of PowerPoint drag behavior.
