# Standalone environment and commands

`SKILL_ROOT` means the folder containing SKILL.md, not the current working
directory. Use Python 3.11+ with lxml, Pillow and jsonschema; dependencies are in
scripts/requirements.txt. A supplied venv is fine. No plugin hook, queue service,
site credentials or API profile is required. Work in a separate task directory.

Run `python SKILL_ROOT/scripts/doctor.py` first. Rendering requires LibreOffice
(`soffice`, or `PPTX_SOFFICE` pointing to it) and Poppler (`pdftoppm` on PATH).
Recipients receive only the PPTX; they need none of these author tools. Do not
silently install dependencies. If an available authorized render tool cannot
substitute, disclose the missing capability instead of claiming verification.
The CLI uses POSIX locks and supports macOS/Linux; use a compatible host/WSL on
Windows. Windows-native execution has not been verified.

Model/API/fast-mode selection, search, image generation and independent reviewer
contexts come from the host. This skill does not configure or promise them. Do
not put keys in a task or archive. No server/worker is started by these helpers.

Replace placeholders with actual paths. `--workspace` precedes the subcommand:

```sh
python SKILL_ROOT/scripts/pptx.py unpack SKILL_ROOT/assets/blank.pptx --base TASK_DIR/sessions
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE list slides
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE inspect 1
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE snapshot --label before-edit
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE validate --level 2
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE render 1
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE export TASK_DIR/deck-v1.pptx
```

Unpack returns the workspace path. Page numbers follow presentation order, not
slide filenames. For adding pages update slide/layout relationships,
presentation.xml and content types together; see relationships.md. Never edit
the source or original.pptx. Export always creates a new artifact filename.
Import helpers by adding SKILL_ROOT/scripts to Python's module search path.

Save request.json with mode and language (for example zh-CN); design-reference
notes use this saved language. From the task folder containing outline.json,
decision-plan.json and asset files:

```sh
python SKILL_ROOT/scripts/workflow_decisions.py --stage planning --mode create
python SKILL_ROOT/scripts/design_references.py --workspace WORKSPACE
python SKILL_ROOT/scripts/workflow_decisions.py --stage authored --mode create --artifact TASK_DIR/deck-v1.pptx
```

Use `edit` for edits. Use --template --outline outline.json for an unselected
scaffold, then fill every required choice. Do not use --allow-legacy on new decks.
Any generation route must reflect an actually available host tool. The local CLI
cannot detect host search/generation capability; the author must select permitted
routes truthfully. Hosts integrating validate_plan can pass generation_enabled and
search_enabled explicitly; the branch validator is not a tool-availability probe.

Prepare review evidence with actual full-deck rendering:

```sh
python SKILL_ROOT/scripts/pptx.py --workspace WORKSPACE render > TASK_DIR/render.json
python SKILL_ROOT/scripts/review_packet.py --workspace WORKSPACE --render-json TASK_DIR/render.json --out TASK_DIR/review-packets
```

The helper produces factual inventory, contact sheets, reading previews and static
simulations of supported click states. It does not strip PPTX notes or isolate
reviewer contexts. For the blind content pass provide only actual audience page
images/visible text, then raw brief/sources; withhold author outline, rationale,
reference register and slide notes. For visual review provide the images/state
evidence, then relevant reference evidence. Copy these into separate reviewer input
folders when delegating. Internal packets are not delivery files. Checks and static
renders cannot certify aesthetics, comprehension or real playback.
