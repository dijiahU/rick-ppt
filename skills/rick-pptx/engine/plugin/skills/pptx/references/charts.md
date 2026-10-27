# Chart dependency chain

Choose charts for numeric relationships, tables for same-field comparisons and
diagrams for supported mechanisms. Keep period, unit, baseline, denominator and
uncertainty visible. Long prose inside table cells may still need rewriting.
Native shapes can explain a relationship, but are not a data-bound chart. Use a
real chart plus its workbook when later Edit Data matters. A delivery host may
restrict embedded workbooks; verify the actual policy rather than inventing support.

`p:graphicFrame/a:graphic/a:graphicData/c:chart/@r:id` points to a chart part. That part's `.rels` can point to an embedded workbook, style and color parts. Chart cached values and the workbook may both need changes to keep PowerPoint's Edit Data consistent. Inspect both before a data edit; text/format-only changes need not rewrite the workbook.

Keep unknown chart extensions intact. A duplicate slide may share a chart: fork chart and workbook relationships if independent changes are required. LibreOffice may display advanced charts differently; report inability to reliably edit a requested unsupported feature, with the original intact.
