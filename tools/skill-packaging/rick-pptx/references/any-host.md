# Any agent, any OS

The workflow in SKILL.md needs only four host abilities. Any agent that has them
can run it: Codex, Claude Code, Cursor, Gemini CLI, OpenCode, Cline, an Agents
SDK loop on an API key, and so on.

| Ability | What the workflow uses it for | If the host lacks it |
| --- | --- | --- |
| Run shell commands with a Python 3.11+ | every helper in `scripts/` | cannot run; use a host with a terminal |
| Look at an image file (vision) | viewing renders, inspecting downloaded pictures, visual review | text-only model: build and validate, but say visual checks were not done |
| Web search / fetch | facts, sources, design references, open-licence images | supplied material only; set `"research": "supplied_only"` in decision-plan.json |
| A second fresh context (subagent, new chat, second API call) | independent content and visual review | run reviews yourself in a clean pass and disclose that they were not independent |

Image generation and browser login are optional extras. Without them, use sourced
or native illustration, and choose no `generate` asset route in decision-plan.json.

## Setup per operating system

| | macOS | Windows | Linux |
| --- | --- | --- | --- |
| Python 3.11+ | `brew install python@3.11` | python.org installer or `winget install Python.Python.3.11` | distro package or pyenv |
| Python packages | `python -m pip install -r SKILL_ROOT/scripts/requirements.txt` (all OSes) | same | same |
| LibreOffice | `brew install --cask libreoffice` | `winget install TheDocumentFoundation.LibreOffice` | `apt install libreoffice-impress` |
| Poppler (`pdftoppm`) | `brew install poppler` | `conda install -c conda-forge poppler`, or a Poppler Windows build on PATH | `apt install poppler-utils` |
| Fonts (SimSun, Times New Roman) | present with Office or system | present | install the fonts or `ttf-mscorefonts-installer` |
| Extra | — | `setx PYTHONUTF8 1` once, then reopen the terminal | — |

Executables that are not on PATH can be named with `PPTX_SOFFICE` and
`PPTX_PDFTOPPM`. Run `python SKILL_ROOT/scripts/doctor.py`; every check must be
true before claiming rendered verification.

On Windows use `python` (or `py -3.11`) instead of `python3`, quote paths with
spaces, and use `certutil -hashfile FILE SHA256` (or PowerShell `Get-FileHash`)
instead of `shasum -a 256`. File locks use `msvcrt` there automatically.

## Mapping host words to your tools

The guides say "image channel", "search", "independent reviewer". Translate:

- **View a render**: open the PNG with the host's image/file viewer tool
  (Claude Code `Read`, Codex `view_image`, Cursor/Cline image attach, an API
  loop sending the PNG as an image part). A path or a successful render is not
  viewing.
- **Search**: the host's web search and page-fetch tools. Download permitted
  files into a new task folder, then view them before using them.
- **Independent review**: start a fresh context that receives only the review
  folder (page images, visible text, brief) and the guide
  (`references/content-review.md` or `visual-review.md`). Do not give it your
  outline, design notes or conversation.
- **Host publisher / progress / PREFETCH**: not available outside the website;
  keep files in the task folder and report the export path and SHA-256.

[Claude Code route](claude-code.md) is a worked example of this mapping,
including the font-config step needed on macOS renders.

## Using a model through an API instead of an app

The skill does not hold keys. Choose one of:

1. **An agent app with your API key** (Claude Code with `ANTHROPIC_API_KEY`,
   Codex CLI with `OPENAI_API_KEY`, Cursor/Cline/OpenCode with any provider):
   load this skill folder and follow SKILL.md. Nothing else changes.
2. **The managed engine on DSH** (`portable_workflow.py --backend dsh`): an
   API-key model behind DeepSeek's harness runs the whole pipeline, including
   reviews and repairs. See [full workflow](full-workflow.md).
3. **The website worker** (repository `runner/`): Codex by default, or any
   OpenAI-compatible model through `runner/configure-model.py --protocol
   responses|chat_completions`. Chat Completions providers lose built-in web
   search and image generation; a text-only model cannot do visual review.

Keep keys in environment variables or a private file outside the task and skill.

## What has been verified

- Core helpers: unit tests on macOS; Windows lock and font paths are covered by
  tests that simulate Windows, not by a real Windows run.
- Managed DSH engine: macOS.
- Website worker: macOS (Docker renderer) and the Linux server.
- Browser login research (Pinterest/Google via Edge): macOS and Linux only. On
  Windows the host's normal web search still works.

Say which of these applied to your run in the delivery report.
