import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

import pytest

import planning_commit as tool


def bundle(mode='create'):
    return {'version': 1, 'source_notes': '# 原始研究\n\n保留限定条件、单位和空白。  \n\n点击说明：先显示入口，点击呈现关系；标题始终可见。\n',
            'outline': {'title': '原生PPT', 'purpose': '解释编辑路径', 'style': '继承模板的字体和背景', 'slides': [
                {'id': 'intro', 'title': '问题', 'summary': '  从用户已有文件开始。\n保持原文换行。 ', 'section': '背景', 'presentationMode': 'native'},
                {'id': 'space', 'title': '关系', 'summary': '展示包、页面与引用之间的关系。'}]},
            'decisions': {'version': 3, 'design_direction': '以提问开篇，再以空间关系解释文件结构。', 'references': [],
                'task': {'operation': mode, 'viewing': 'dual_use', 'research': 'supplied_only', 'references': 'use_available', 'style': 'analytical', 'palette': 'semantic', 'typography': 'installed_role_system'},
                'pages': [
                    {'id': 'intro', 'intent': 'introduce', 'strategy': 'read', 'form': 'typography', 'support': [], 'composition': 'type_statement', 'behavior': 'static', 'assets': [{'route': 'none'}], 'role': '认识问题。', 'visual_action': '主要问题通过大字与留白建立焦点。', 'reference_ids': []},
                    {'id': 'space', 'intent': 'show_space', 'strategy': 'relate', 'form': 'diagram', 'support': ['typography'], 'composition': 'relational_map', 'behavior': 'click_reveal', 'assets': [{'route': 'source_grounded_native'}], 'role': '理解引用关系。', 'visual_action': '按照真实依赖位置布置对象，以连接线和点击顺序解释关系。', 'reference_ids': []}]}}


def write(root, document):
    path = root / 'planning-input.json'
    path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    return path


def originals(root):
    values = {name: ('historical bytes ' + name + '\r\n').encode() for name in tool.OUTPUTS}
    for name, value in values.items():
        (root / name).write_bytes(value)
        (root / name).chmod(0o640)
    return values


def test_valid_create_preserves_all_authored_content_and_input(tmp_path):
    doc = bundle()
    source = write(tmp_path, doc)
    original = source.read_bytes()
    result = tool.commit_bundle(tmp_path, source, expected_pages=2)
    assert result['ok'] and result['stage'] == 'planning'
    assert result['click_reveal_required']
    assert source.read_bytes() == original
    assert json.loads((tmp_path / 'outline.json').read_bytes()) == doc['outline']
    assert json.loads((tmp_path / 'decision-plan.json').read_bytes()) == doc['decisions']
    assert (tmp_path / 'source-notes.md').read_bytes() == doc['source_notes'].encode()
    assert not any(item['replaced'] for item in result['files'])
    assert not list(tmp_path.glob('.planning-commit-*'))


def test_template_scoped_edit_keeps_static_repeated_expression_and_permissions(tmp_path):
    doc = bundle('edit')
    doc['decisions']['task'].update(style='supplied_system', references='preserve_supplied', palette='inherited', typography='inherited')
    second = copy.deepcopy(doc['decisions']['pages'][0])
    second['id'] = 'space'
    doc['decisions']['pages'][1] = second
    old = originals(tmp_path)
    result = tool.commit_bundle(tmp_path, write(tmp_path, doc), mode='edit')
    assert result['ok'] and not result['click_reveal_required']
    assert all(item['replaced'] for item in result['files'])
    for name in old:
        assert (tmp_path / name).stat().st_mode & 0o777 == 0o640
    assert json.loads((tmp_path / 'decision-plan.json').read_bytes()) == doc['decisions']


@pytest.mark.parametrize('change,match', [
    (lambda d: d['outline'].update(pages=d['outline'].pop('slides')), 'missing "slides"'),
    (lambda d: d['decisions']['pages'][1].update(form='invented'), 'Invalid choice'),
    (lambda d: d['decisions']['pages'][1].update(behavior='static'), 'entirely static'),
    (lambda d: d['decisions']['task'].update(operation='edit'), 'Operation must match'),
    (lambda d: d['outline']['slides'][1].update(id='intro'), 'unique'),
    (lambda d: d.update(source_notes='  \n'), 'nonempty Markdown'),
    (lambda d: d['outline']['slides'][0].update(summary='Local file /Users/rick/private.txt'), 'public presentation content'),
])
def test_invalid_planning_never_changes_existing_outputs(tmp_path, change, match):
    old = originals(tmp_path)
    doc = bundle()
    change(doc)
    with pytest.raises(ValueError, match=match):
        tool.commit_bundle(tmp_path, write(tmp_path, doc))
    assert {name: (tmp_path / name).read_bytes() for name in old} == old
    assert not list(tmp_path.glob('.planning-commit-*'))


def test_expected_page_count_and_source_scoped_asset_validation(tmp_path):
    doc = bundle()
    with pytest.raises(ValueError, match='requested count'):
        tool.commit_bundle(tmp_path, write(tmp_path, doc), expected_pages=5)
    doc['decisions']['references'] = [{'id': 'R1', 'kind': 'supplied_system', 'title': '周报', 'creator': 'Rick', 'source': '../outside.pptx', 'inspection': 'read_text', 'evidence': 'Read original source', 'observed': 'Original template', 'borrowed': None, 'applications': []}]
    with pytest.raises(ValueError, match='inside the task'):
        tool.commit_bundle(tmp_path, write(tmp_path, doc))
    assert not any((tmp_path / name).exists() for name in tool.OUTPUTS)


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure_index', [1, 2, 3])
def test_replace_failure_restores_originals_or_removes_partial_new_files(tmp_path, existing, failure_index):
    old = originals(tmp_path) if existing else {}
    source = write(tmp_path, bundle())
    replace = tool.os.replace
    calls = 0
    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == failure_index:
            raise OSError('simulated disk failure')
        return replace(source, target)
    with mock.patch.object(tool.os, 'replace', side_effect=fail_once):
        with pytest.raises(OSError, match='simulated disk failure'):
            tool.commit_bundle(tmp_path, source)
    for name in tool.OUTPUTS:
        if existing:
            assert (tmp_path / name).read_bytes() == old[name]
            assert (tmp_path / name).stat().st_mode & 0o777 == 0o640
        else:
            assert not (tmp_path / name).exists()
    assert not list(tmp_path.glob('.planning-commit-*'))
    assert tool.commit_bundle(tmp_path, source)['ok']


def test_staging_write_failure_leaves_no_partial_files(tmp_path):
    old = originals(tmp_path)
    source = write(tmp_path, bundle())
    with mock.patch.object(tool, '_write', side_effect=OSError('staging write failed')):
        with pytest.raises(OSError, match='staging write failed'):
            tool.commit_bundle(tmp_path, source)
    assert {name: (tmp_path / name).read_bytes() for name in old} == old
    assert not list(tmp_path.glob('.planning-commit-*'))


@pytest.mark.parametrize('raw,match', [
    ('{"version":1,"version":1}', 'Duplicate JSON key'),
    ('{"outline":{"title":"a","title":"b"}}', 'Duplicate JSON key'),
    ('{"version":NaN}', 'Non-finite'),
    ('{"version":Infinity}', 'Non-finite'),
    ('{"version":1e9999}', 'Non-finite'),
])
def test_malformed_json_rejected_without_output(tmp_path, raw, match):
    source = tmp_path / 'planning-input.json'
    source.write_text(raw)
    with pytest.raises(ValueError, match=match):
        tool.commit_bundle(tmp_path, source)
    assert not any((tmp_path / name).exists() for name in tool.OUTPUTS)


def test_oversized_bundle_rejected_before_parsing(tmp_path):
    source = write(tmp_path, bundle())
    with mock.patch.object(tool, 'MAX_INPUT_BYTES', 20):
        with pytest.raises(ValueError, match='regular file within'):
            tool.commit_bundle(tmp_path, source)
    assert not any((tmp_path / name).exists() for name in tool.OUTPUTS)


def test_paths_and_output_symlinks_cannot_escape_task(tmp_path):
    root = tmp_path / 'task'
    root.mkdir()
    outside = write(tmp_path, bundle())
    with pytest.raises(ValueError, match='inside --task-root'):
        tool.commit_bundle(root, outside)
    (root / 'input-link.json').symlink_to(outside)
    with pytest.raises(ValueError, match='symlinks'):
        tool.commit_bundle(root, 'input-link.json')
    source = write(root, bundle())
    (root / 'outline.json').symlink_to(outside)
    old = outside.read_bytes()
    with pytest.raises(ValueError, match='symlinks'):
        tool.commit_bundle(root, source)
    assert outside.read_bytes() == old
    assert not (root / 'decision-plan.json').exists()


def test_legacy_is_explicit_and_original_decision_bytes_meaning_is_retained(tmp_path):
    doc = bundle()
    plan = doc['decisions']
    plan['version'] = 2
    plan.pop('design_direction')
    plan.pop('references')
    for page in plan['pages']:
        for field in ('strategy', 'composition', 'visual_action', 'reference_ids'):
            page.pop(field)
        page.update(layout='focus', density='balanced', behavior='static')
    source = write(tmp_path, doc)
    with pytest.raises(ValueError, match='current design contract'):
        tool.commit_bundle(tmp_path, source)
    assert tool.commit_bundle(tmp_path, source, allow_legacy=True)['legacy_record']
    assert json.loads((tmp_path / 'decision-plan.json').read_bytes()) == plan


def test_outline_validator_matches_host_current_public_contract(tmp_path):
    # Independent host implementation protects this portable helper from drifting
    # when fields such as interaction/bounds or public-text limits change.
    host_path = Path(tool.__file__).resolve().parents[4] / 'runner/outline.py'
    spec = importlib.util.spec_from_file_location('host_outline_contract', host_path)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    outline = bundle()['outline']
    outline['slides'][1].update(presentationMode='hybrid', interaction={'scene': 'scene_1', 'purpose': '演示', 'bounds': {'x': 0, 'y': 10, 'width': 100, 'height': 200}})
    assert tool.validate_outline(outline) is outline
    assert host.validate_outline(outline)['slides'][1]['interaction'] == outline['slides'][1]['interaction']
    mutations = [lambda v: v['slides'][1]['interaction']['bounds'].update(width=True),
                 lambda v: v['slides'][1]['interaction']['bounds'].update(x=1, width=2147483647),
                 lambda v: v['slides'][0].update(presentationMode=[]),
                 lambda v: v['slides'][0].update(summary='password=secret')]
    for mutation in mutations:
        bad = copy.deepcopy(outline)
        mutation(bad)
        with pytest.raises(ValueError):
            host.validate_outline(bad)
        with pytest.raises(ValueError):
            tool.validate_outline(bad)


def test_cli_one_call_commits_all_files_and_reports_hashes(tmp_path):
    source = write(tmp_path, bundle())
    result = subprocess.run([sys.executable, tool.__file__, '--task-root', str(tmp_path), '--input', str(source), '--expected-pages', '2'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report['ok'] and len(report['files']) == 3
    assert all(len(item['sha256']) == 64 for item in report['files'])
