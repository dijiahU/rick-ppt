# Formula fidelity: semantics, encoding and rendering

Read before authoring or changing mathematical notation. A recognizable formula
is not necessarily correct; XML validation and browser rendering cannot establish
PowerPoint glyph coverage or mathematical meaning.

Before layout, retain the intended equation, definitions, units/assumptions and a
checkable example where relevant in source-notes.md. Keep notation consistent
between text, diagrams, examples and notes. Verify arithmetic and signs separately
from visual appearance. Search authoritative material for uncertain definitions;
do not infer a correct equation from a visually similar web image.

For simple expressions, native text runs with real superscript/subscript formatting
may suffice. For structured fractions, matrices and related notation, prefer a
verified native Office Math representation when supported by the target workflow.
Preserve existing native math. Do not assume a text field converts LaTeX,
MathJax, MathML or CSS positioning into editable Office Math; unsupported content
needs native implementation or an explicitly identified alternative.

Use fonts actually available in the target renderer/editor. A Unicode character's
presence in XML does not mean its glyph exists in that font. Avoid encoding an entire
formula as decorative Unicode “mathematical alphabet” characters merely to get
italics/bold. Use proper runs and supported symbols; distinguish minus/hyphen,
Greek/Latin lookalikes, multiplication, superscripts and subscripts semantically.

Before propagating a math style, render a representative formula at final size in
the native PPT path and inspect all glyphs, baseline, fraction bars, indices and
line breaking. Expand a
box or fix its representation/font before shrinking the entire equation. A vector
or raster fallback loses equation editability: disclose and respect user requirements;
never flatten a whole slide to hide one formula problem.

Optional diagnostic (not an acceptance gate):

```sh
PLUGIN_ROOT/.venv/bin/python PLUGIN_ROOT/skills/pptx/scripts/inspect_formulas.py /absolute/deck.pptx
```

It inventories candidate math text, declared fonts, Office Math and obvious encoding
warnings. It cannot prove equation correctness, font availability, visual fidelity
or that all math was detected. Review every actual formula, not only the candidates.

For an observed failure, record the exact slide, intended expression, XML/run/font
representation and observed native render defect. If only the native render fails,
investigate the conversion/font/layout difference; if XML is already wrong, repair
the source representation. Do not claim to have fixed a reported “garbled formula”
without reproducing and checking that specific file. Static render inspection does
not certify every PowerPoint installation's font compatibility.
