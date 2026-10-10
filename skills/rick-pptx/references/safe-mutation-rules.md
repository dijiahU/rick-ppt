# Invariants and recovery

- Modify only unpacked workspace parts; source and original.pptx are protected.
- Keep untouched part bytes unchanged. Do not globally reserialize XML for a trivial change.
- Inspect relationships before changing referenced objects. Prefer orphaned assets over destructive cleanup.
- Use snapshot before global changes. Rollback first checkpoints the current state and reports its recovery ID.
- After an error, keep broken state and repair locally. Validate cannot prove full ECMA-376 compliance; export also requires an actual open/render test.
- Hooks observe supported local tools and cannot provide a security boundary for arbitrary programs. Export always repeats validation. Never claim that a failed Stop produced a valid new file.
- Inspect rendered affected slides after visual edits. LibreOffice and Microsoft PowerPoint can differ in font metrics, charts and effects; preserve native content and disclose observed fidelity issues.
