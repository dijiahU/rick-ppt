"""OOXML remains the source of truth; helpers never reserialize user XML."""

__version__ = "0.1.0"

import sys as _sys

if _sys.platform == "win32" and not _sys.flags.utf8_mode:
    # Task files (JSON, notes, outlines) are UTF-8. Chinese Windows defaults to
    # GBK for open()/read_text(), which corrupts them. Run Python with -X utf8
    # or set PYTHONUTF8=1 once for the user (setx PYTHONUTF8 1).
    _sys.stderr.write("rick-pptx: set PYTHONUTF8=1 (or run python -X utf8) on Windows; UTF-8 task files may be misread.\n")
