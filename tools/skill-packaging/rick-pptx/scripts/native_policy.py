"""Native-only checks with no plugin runtime or external configuration."""
from pathlib import Path
from pptx_core.common import local, parse
from pptx_core.relationships import slide_parts

WE = 'http://schemas.microsoft.com/office/webextensions/webextension/2010/11'


def discover_content_addins(root):
    root = Path(root)
    records = []
    for number, part in enumerate(slide_parts(root), 1):
        for reference in parse(root / part).findall(f'.//{{{WE}}}webextensionref'):
            records.append({'slide': number, 'part': part, 'kind': 'content_addin'})
    return records


def validate_ooxml(root):
    root = Path(root)
    errors = []
    if discover_content_addins(root) or (root / 'ppt/webExtensions').exists():
        errors.append('Single-file PPTX policy rejects Content Add-ins')
    for path in root.rglob('*'):
        if path.is_file() and 'vbaproject' in path.name.lower():
            errors.append('Single-file PPTX policy rejects VBA projects')
        if path.is_file() and path.suffix == '.rels':
            for item in parse(path):
                if (local(item) == 'Relationship' and
                        item.get('TargetMode', '').lower() == 'external' and
                        item.get('Type', '').rsplit('/', 1)[-1] in ('image', 'audio', 'video', 'media', 'webextension')):
                    errors.append('Single-file PPTX policy rejects externally linked media: ' + path.relative_to(root).as_posix())
    return list(dict.fromkeys(errors))


def validate_native(root, **_):
    errors = validate_ooxml(root)
    return {'ok': not errors, 'errors': errors,
            'instances': discover_content_addins(root),
            'runtime_verified': False, 'powerpoint_playback_verified': False}
