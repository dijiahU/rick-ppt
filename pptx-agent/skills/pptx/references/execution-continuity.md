# Work from current files

Use the current task directory and task-relative paths; older absolute paths in a
resumed conversation are historical. tool-quickstart.md and tool-manifest.json give
the real interpreter, commands and parts directory. After unpacking the source once,
refresh tool preparation with that workspace and reuse it.

Prefer `native_page_batch` for ordinary native objects; use native_canvas or direct
OOXML for the rest. Read implementation source only for a specific interface error.
Write long batches in pieces per page rather than one huge command.

Build the current page, render it, look at it and refine it, in page order. On
recovery the host may restart the same role in a fresh context with the current
files; continue from what is saved. Report missing material honestly.

For a complete deck or finished repair use manifest save_candidate: it exports,
renders, runs the authored check and declares the file. Keep a fresh checkpoint after
each main correction; older exports are preserved.

Every image you view stays in this conversation and is re-read on each later step. Look
at a reference or template page once and write down what you take from it; reopen an
image only after it changed (a new render).
