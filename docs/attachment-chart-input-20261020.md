# Native chart PPTX attachment repair · 2026-10-20

The upload receiver rejected every Office `embeddings` part before any model
phase. Native PowerPoint charts normally store passive XLSX data in that folder,
so a valid chart-bearing reference deck failed immediately after upload.

PPTX inputs now use the existing content-aware `office_policy.validate_delivery`
policy after the unchanged attachment count, size, checksum, path and compression
checks. Only internally referenced chart XLSX data is permitted. Unreferenced or
arbitrary embedded payloads, OLE objects, macros, ActiveX, active workbook links and
unsafe nested archives remain rejected. DOCX embedding policy is unchanged.
Original uploaded bytes are validated and published without rewriting or stripping
the chart data. No new dependency or change to output policy was introduced.

Validation: 7 focused chart-attachment tests, 14 existing attachment tests and 12
content-workflow tests passed. The exact failing uploaded deck also passed the
updated validation and an isolated receive/checksum test with all bytes preserved.
Regression fixtures are synthetic and include no user documents or credentials.

The worker was gracefully reloaded before an explicitly authorized, version-bound
retry of the failed task. The retry preserves its existing execution backend and
original attachments. Runtime plugin remains the design-craft release; this fix
is in host-side attachment admission.
