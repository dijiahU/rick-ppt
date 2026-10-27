# Runtime reference entry point

Use interactive regions when learner input, executable code or stateful animation
improves the explanation. Ordinary native slides do not require a scene.

The scene schema is `schemas/interactive-slide.schema.json` relative to this skill.
Inspect the plugin's `runtime/examples/` and the following precise references before
inventing a node, component, property, action or expression:

- [Core rendering and state semantics](../../../runtime/docs/runtime-semantics.md)
- [Optional feature packs and their APIs](../../../runtime/docs/feature-packs.md)
- [Architecture and boundaries](../../../docs/interactive-architecture.md)
- [Compatibility evidence](../../../docs/interactive-compatibility.md)
- [Authoring sequence and CLI](interactive-authoring.md)

Scene expressions are bounded declarative ASTs. Executable experiments belong in
the explicit code pack. Remote assets require host-approved origins; custom plugins
require approved IDs and hashes. Prefer declared local asset IDs across component
props and bindings. glTF external buffers/images are copied and their URIs rewritten
during import; original source bytes remain unchanged. Do not modify bundle files
after hashing and claim old verification still applies.

Use `interactive doctor`, `validate-spec`, `attach`, `render`, `update`, `list`,
`inspect`, `resize`, `clone`, `detach`, `serve`, `cert` and `bundle`. Commands return
JSON; pass `--help` for exact flags. Workspace commands accept `-w`. Use paths
returned by commands, not guessed output names. Stop emits the current PPTX/bundle
paths and explicit runtime and desktop verification states.
