# Package navigation

A PPTX is an OPC ZIP. `[Content_Types].xml`, `_rels/.rels` and `ppt/presentation.xml` live at archive root. `ppt/presentation.xml` orders slides via `p:sldIdLst`; resolve each `r:id` in `ppt/_rels/presentation.xml.rels`. Never infer user page numbers from filenames.

Common namespace URIs: `p` = `http://schemas.openxmlformats.org/presentationml/2006/main`, `a` = `http://schemas.openxmlformats.org/drawingml/2006/main`, `r` = `http://schemas.openxmlformats.org/officeDocument/2006/relationships`. Prefix spelling is not significant. Strict OOXML uses `http://purl.oclc.org/ooxml/` variants; preserve the input namespace family.

Positions use EMU: 914400 per inch, 360000 per cm. Font sizes are hundredths of a point, rotations 60000ths of a degree. XML element order matters. Copy ordering from a nearby comparable object rather than inventing it. Helpers parse for inspection but do not serialize the source XML.
