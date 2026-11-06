"""Read-only, scenario-based views of the existing prepared tool manifest.

This is tool discovery, not routing, permissions, a layout system or execution.
"""
import copy
from pathlib import Path

SCHEMA = 'native-tool-groups/v1'
GROUPS = {
    'plan': {
        'title': '调研与内容规划 / Research and planning',
        'when': 'Prepare evidence, visual subjects, source notes and the ordered outline.',
        'sections': ('outline_fields', 'decision_contract', 'planning_commit', 'page_design', 'command_outputs', 'plan_check'),
        'commands': ('planning_commit', 'decision_scaffold', 'planning_check', 'publish_outline'),
        'guides': ('content.md', 'planning-commit.md'), 'related': ('images', 'compose'),
        'notes': 'Commit supported evidence and a provisional visual direction; do not finalize every page as prose. Planning commit already checks the supplied records.'},
    'recreate': {
        'title': '图片复刻 / Image recreation',
        'when': 'Faithfully reconstruct an existing image/diagram, retaining native editable structure.',
        'sections': ('image_recreation', 'native_authoring', 'native_batch', 'native_pages'),
        'commands': ('unpack_selected_source', 'native_page_batch', 'ensure_next_page', 'render_page'),
        'cli': ('unpack', 'inspect', 'render', 'snapshot', 'diff'),
        'guides': ('image-recreation.md', 'native-batch.md'), 'related': ('images', 'fonts', 'animate', 'verify'),
        'notes': 'Inspect source pixels, use existing source_frame/crops/paths and comparison receipts. Preserve originals, symbols and source relationships. Native helper geometry is not a limit on OOXML; do not replace the whole diagram with one image.'},
    'compose': {
        'title': '原创设计与原生绘制 / Design and native authoring',
        'when': 'Compose new pages or illustrations, then implement editable text, geometry and groups.',
        'sections': ('native_authoring', 'native_batch', 'native_pages', 'page_design'),
        'commands': ('ensure_next_page', 'native_page_batch', 'page_design_context', 'record_design_observation', 'render_page'),
        'guides': ('native-batch.md', 'native-canvas.md', 'page-design.md'), 'related': ('images', 'fonts', 'animate', 'verify'),
        'notes': 'Choose the visible subject before the medium. Use generation/source images for rich scenes, native drawing for precise editable structure, or combine them. Batch operations are transactional; use stable IDs and returned handles. Render/view each meaningful completed page change.'},
    'images': {
        'title': '图片获取、生成与插入 / Images',
        'when': 'Acquire or generate a visual subject, inspect it and embed/crop it with native labels.',
        'canvas': ('add_image',),
        'guides': ('research-and-assets.md', 'images.md', 'pinterest.md'), 'related': ('compose', 'recreate'),
        'notes': 'Use only services actually exposed in capabilities.json or the current host tool list. This group does not create a provider or authorize another account. Inspect actual image bytes; a path or reference is not viewing or slide embedding. Keep authenticity/rights and native analytical labels.'},
    'edit': {
        'title': '局部修改与模板继承 / Scoped edits',
        'when': 'Inspect and change a supplied PPTX while preserving untouched source objects and behavior.',
        'sections': ('native_authoring', 'page_design'),
        'commands': ('unpack_selected_source', 'list_slides', 'inspect_page', 'render_page'),
        'cli': ('unpack', 'list', 'inspect', 'find', 'refs', 'snapshot', 'diff', 'rollback'),
        'guides': ('safe-mutation-rules.md', 'slides-and-shapes.md', 'masters-and-layouts.md'),
        'related': ('compose', 'images', 'fonts', 'animate', 'verify'),
        'notes': 'Snapshot first. Keep IDs, relationships and untouched bytes. Inspect partial writes before retry. Do not treat a local edit as permission to redesign other pages.'},
    'animate': {
        'title': '原生动画与顺序 / Native animation',
        'when': 'Add/check click reveals, semantic groups and native timing.',
        'canvas': ('semantic_group', 'reveal'),
        'guides': ('animations.md',), 'related': ('compose', 'verify'),
        'notes': 'Reuse verified object handles. One entrance target per effect; clickEffect starts the semantic group and withEffect synchronizes members. Static previews are not target-player playback.'},
    'fonts': {
        'title': '字体与文字测量 / Fonts and text',
        'when': 'Verify glyph coverage, font files, line fit and compatibility without changing source scope.',
        'canvas': ('check_glyphs', 'text_measure', 'add_text'),
        'guides': ('fonts.md', 'text.md', 'windows-wps.md'), 'related': ('compose', 'edit', 'verify'),
        'notes': 'Use the exact interpreter and actual font files. add_text requires finite numeric max_height; native_batch explicitly supports measured auto. Preserve source/user font requirements and do not shrink text just to fit.'},
    'verify': {
        'title': '检查、渲染与交付 / Verify and deliver',
        'when': 'Validate/render a native candidate, compare versions and declare the complete reviewed output.',
        'sections': ('candidate_save',),
        'commands': ('validate', 'compatibility', 'render_page', 'save_candidate', 'export'),
        'cli': ('validate', 'render', 'export', 'diff', 'inspect', 'refs'),
        'guides': ('review-packet.md', 'content-review.md', 'visual-review.md', 'safe-mutation-rules.md'),
        'related': ('edit', 'animate', 'fonts'),
        'notes': 'Candidate save exports/renders/checks a complete deck and updates delivery.json atomically. It is not independent approval. Inspect the exact rendered images and preserve frozen reviewed bytes; inventories are not aesthetic scores.'},
}


def catalog(manifest, script):
    command = [manifest['python'], str(script), '--task-root', manifest['task_root']]
    return {'schema': SCHEMA,
        'list_command': command + ['--list-groups'],
        'open_command': command + ['--group', 'GROUP_ID'],
        'groups': [{'id': key, 'title': spec['title'], 'use_when': spec['when']}
                   for key, spec in GROUPS.items()],
        'policy': 'Choose the relevant group(s), open exact current interfaces once and reuse them. '
                  'No automatic task classification, removed capability or permission change. '
                  'The full tool-manifest.json remains available for compatibility and advanced native work.'}


def select_group(manifest, name, scripts):
    if name not in GROUPS:
        raise ValueError('Unknown tool group: ' + name)
    spec = GROUPS[name]
    result = {k: copy.deepcopy(manifest[k]) for k in
              ('python', 'task_root', 'session_dir', 'parts_dir', 'workspace_status', 'workspace_contract') if k in manifest}
    result.update(group=name, title=spec['title'], use_when=spec['when'], notes=spec['notes'],
                  related_groups=list(spec['related']))
    result.update({k: copy.deepcopy(manifest[k]) for k in spec.get('sections', ()) if k in manifest})
    result['commands'] = {k: copy.deepcopy(manifest['commands'][k]) for k in spec.get('commands', ())
                          if k in manifest.get('commands', {})}
    if spec.get('canvas'):
        result['native_canvas'] = {k: copy.deepcopy(manifest['native_canvas'][k]) for k in spec['canvas']
                                   if k in manifest.get('native_canvas', {})}
    if spec.get('cli'):
        cli = manifest.get('pptx_cli', {})
        result['pptx_cli'] = {'global_workspace_before_subcommand': True,
            'commands': {k: copy.deepcopy(cli.get('commands', {})[k]) for k in spec['cli'] if k in cli.get('commands', {})}}
    result['guides'] = [str(Path(scripts).parent/'references'/name) for name in spec.get('guides', ())
                        if (Path(scripts).parent/'references'/name).is_file()]
    if name == 'images':
        result['capabilities_file'] = str(Path(manifest['task_root'])/'capabilities.json')
        result['capability_status'] = 'Read the current exposed capabilities; no service call is made by opening this group.'
    return result


def quickstart(manifest):
    import shlex
    discovery = manifest['discovery']
    return '\n'.join([
        '# Task tool folders', '', 'Read SKILL.md and the actual task scope first.',
        f'Exact Python: `{manifest["python"]}`; do not substitute bare python/python3.',
        f'Workspace: `{manifest["parts_dir"]}`' if manifest['parts_dir'] else
        'No workspace selected. Choose the actual source/blank file, unpack it, then refresh using the returned workspace.',
        '', 'Open only the useful group(s); the command below is read-only and runs no PPT operation:',
        '```sh', shlex.join(discovery['open_command']), '```',
        *[f'- `{g["id"]}` — {g["title"]}: {g["use_when"]}' for g in discovery['groups']],
        '', 'Workspace bootstrap (replace SELECTED_SOURCE; refresh only after choosing/unpacking the source):',
        '```sh', *[shlex.join(manifest['entry_commands'][name]) for name in
                    ('unpack_selected_source', 'refresh') if name in manifest.get('entry_commands', {})], '```',
        '', 'Commands within a group expose the installed interfaces, not a selected page design.',
        'Reuse opened details. After unpacking/recovery refresh to replace workspace placeholders with actual paths.',
        'The full tool-manifest.json stays available; existing commands and native OOXML editing are unchanged.',
        'Keep authoring in page order, snapshot before risky edits, inspect exact renders, and use independent reviews.',
        'Missing image generation/search must stay unavailable; this directory does not grant a service or account.', ''])
