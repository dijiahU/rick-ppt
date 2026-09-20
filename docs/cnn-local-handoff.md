# CNN local PowerPoint handoff

The local-only package adds a native whole-shape hyperlink beneath each of the
20 interactive preview regions. The original delivery remains untouched.

`runner/local-handoff/build.py SOURCE DESTINATION --python PYTHON` creates a new
package. `开始演示.command` starts the verified browser runtime on an automatically
assigned loopback port, generates a new session PPTX with that actual origin,
and opens the guide and PowerPoint. `结束演示.command` stops only that package's
own authenticated runtime instance. No website, TLS certificate or Office add-in
is needed for this PPT-to-browser workflow. Session exports never overwrite
previous PPTX files. All scene content and teaching code remain unchanged.

Validation: 20 native hyperlink mappings and their exact scene JSON endpoints
passed; all preview routes returned 200. Repeated startup reused the runtime
without overwriting files. A focused test verifies all mappings, preserved native
bytes, rejection of nonlocal origins and no output overwrite. LibreOffice
rendered all 20 pages; the button's hyperlink-style contrast was corrected and
re-rendered. PowerPoint was opened through Computer Use, but its native pipe
closed before a slideshow click could be verified. Do not claim desktop
click-through verification from these checks.

Usage: launch, present the automatically opened session PPTX, click the green
OPEN INTERACTIVE LAB button, use Run/Play/Step, then Command-Tab back to the
unchanged PowerPoint page. Browser changes do not automatically save to PPT.
The archive excludes session PPTX files so outdated runtime ports are never
presented as reusable links. This Mac's interpreter path is stored only in the
local artifact; exported source code contains no credentials or user deck data.
