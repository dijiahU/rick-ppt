# Relationship edits

For `ppt/slides/slide4.xml`, relationships live in `ppt/slides/_rels/slide4.xml.rels`; package relationships live in `_rels/.rels`. Each Relationship has a unique local `Id`, a Type URI and Target. Relative targets resolve against the owning part directory, not `_rels/`. `/ppt/media/image1.png` is package-root-relative. URI-escaped characters must be decoded when resolving filenames. `TargetMode="External"` denotes a URL and is never a local existence check.

Use `refs PART`, `refs rId3 --from PART`, and `refs ppt/media/image1.png --reverse`. Keep `r:id`, `r:embed` and `r:link` synchronized with the owning `.rels`. Some relationships (layout, theme, notes) are implicit and need no XML attribute reference. An unused relationship is only a warning.

For adding a part, allocate a previously unused filename and relationship ID, add its content type Default or Override, and patch the owner's XML. For deletion, first remove the referencing object/attribute. A media part may be shared by other slides or embedded content: leave harmless orphans unless explicitly cleaning up, and inspect reverse references before deleting anything.
