"""Build a portable native PPTX skill; no keys, queue services or browser runtime.

Usage: python tools/build-skill.py --output /path/to/dist
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'pptx-agent/skills/pptx'
OVERLAY = REPO / 'tools/skill-packaging/rick-pptx'
OVERLAY_FILES = ('SKILL.md', 'agents/openai.yaml', 'references/environment.md',
                 'scripts/doctor.py', 'scripts/native_policy.py', 'scripts/requirements.txt')
SCRIPTS = ('pptx.py', 'native_canvas.py', 'native_builds.py', 'native_structure.py',
           'workflow_decisions.py', 'design_references.py', 'review_packet.py', 'inspect_formulas.py')
CORE = ('__init__.py', 'common.py', 'cli.py', 'package.py', 'renderer.py',
        'manifest.py', 'validator.py', 'relationships.py', 'snapshots.py', 'diff.py')
REFERENCES = ('content.md', 'content-review.md', 'visual-review.md', 'research-and-assets.md',
              'workflow-branches.md', 'content-led-composition.md', 'native-canvas.md',
              'animations.md', 'ooxml-overview.md', 'slides-and-shapes.md', 'text.md',
              'images.md', 'charts.md', 'groups.md', 'masters-and-layouts.md',
              'relationships.md', 'safe-mutation-rules.md', 'review-examples.md',
              'technical/native-capabilities.md', 'technical/formula-fidelity.md')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def replace_checked(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError('Production source changed; review standalone adapter: ' + path.name)
    path.write_text(text.replace(before, after))


def build(output):
    output = Path(output).resolve()
    target = output / 'rick-pptx'
    if target.exists():
        raise ValueError('Choose a fresh output directory; existing skill is preserved')
    output.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    inputs = []
    for name in OVERLAY_FILES:
        path = OVERLAY / name
        copy(path, target / name)
        inputs.append(path)
    for directory, names in [('scripts', SCRIPTS), ('scripts/pptx_core', CORE),
                             ('references', REFERENCES),
                             ('assets', ('blank.pptx', 'workflow-choices.json', 'single-file-policy.json'))]:
        for name in names:
            path = SOURCE / directory / name
            copy(path, target / directory / name)
            inputs.append(path)
    # Change only the portable copy; the deployed plugin is untouched.
    core = target / 'scripts/pptx_core'
    replace_checked(core / 'cli.py', 'from .interactive_ooxml import discover_content_addins',
                    'from native_policy import discover_content_addins')
    replace_checked(core / 'cli.py', '''    from .interactive_validate import native_only
    if not native_only():
        from .interactive import add_parser
        add_parser(commands)
''', '')
    replace_checked(core / 'cli.py', '''    if args.command == "interactive":
        from .interactive import dispatch as interactive_dispatch
        return interactive_dispatch(args), 0
''', '')
    for name in ('cli.py', 'package.py'):
        replace_checked(core / name, 'from .interactive_validate import validate_interactive',
                        'from native_policy import validate_native as validate_interactive')
    replace_checked(core / 'validator.py', 'from .interactive_ooxml import validate_ooxml',
                    'from native_policy import validate_ooxml')
    review = target / 'scripts/review_packet.py'
    text = review.read_text()
    start, end = text.index('def scene_inventory('), text.index('def simple_appear_steps(')
    text = text[:start] + '''def collect_interactive(ws, destination):
    from native_policy import validate_native
    return validate_native(ws.root)


''' + text[end:]
    review.write_text(text)
    for path in (target / 'references').rglob('*.md'):
        text = path.read_text().replace('PLUGIN_ROOT/.venv/bin/python PLUGIN_ROOT/skills/pptx/', 'python SKILL_ROOT/')
        text = text.replace('PLUGIN/skills/pptx/', 'SKILL_ROOT/')
        text = text.replace('Task entry is only `create` or `edit`, copied from the host.',
                            'Task entry is only `create` or `edit`, taken from the user request (or host mode when supplied).')
        text = text.replace('Use the host publisher; synchronize revisions.',
                            'Publish through the host when available; keep local outline revisions synchronized.')
        text = text.replace('For video/audio use task-local media-embed.py and its required poster/icon;',
                            'For video/audio use direct native OOXML embedding or an actually available host helper with a poster/icon;')
        path.write_text(text)
    manifest = {'format': 1, 'name': 'rick-pptx', 'native_only': True,
                'source_files': {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (target / 'assets/package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = output / 'rick-pptx.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as packed:
        for path in sorted(target.rglob('*')):
            if path.is_file():
                packed.write(path, path.relative_to(output))
    return {'skill': str(target), 'archive': str(archive),
            'files': sum(p.is_file() for p in target.rglob('*')),
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
