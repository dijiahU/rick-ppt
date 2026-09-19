#!/usr/bin/env python3
"""Build and prove a synthetic multi-region PPTX without touching user decks.

Use the plugin's Python environment. The output directory must be new and should
be outside the checkout. This is a technical acceptance artifact, not a lesson or
desktop PowerPoint playback certificate.
"""
from __future__ import annotations
import argparse
import asyncio
import copy
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from lxml import etree

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / 'skills/pptx/scripts'))
from pptx_core.common import NS, P, R, CT, PR, atomic_json, parse, sha256
from pptx_core.package import unpack, export
from pptx_core.interactive import attach, scene_render
from pptx_core.interactive_bundle import assemble_bundle
from pptx_core.interactive_validate import read_json, validate_interactive, validate_spec
from pptx_core.interactive_ooxml import discover_content_addins
from pptx_core.manifest import manifest, changed_paths
from pptx_core.validator import validate
from interactive_render import execute, assertion
from playwright.async_api import async_playwright

EMU = 914400
def e(source): return {'expr': source}
def node(ident, kind, **props): return {'id': ident, 'type': kind, 'props': props}
def case(name, actions, assertions, reset=False):
    return {'name': name, 'actions': actions, 'assertions': assertions, 'reset': reset, 'capture': True}
def state(path, value, **extra): return {'type': 'state', 'path': path, 'equals': value, **extra}
def scene(ident, nodes, **extra):
    return {'schemaVersion': 1, 'id': ident, 'viewport': {'width': 700, 'height': 600},
            'theme': {'background': '#f8fafc', 'text': '#172033', 'accent': '#2563eb'}, 'nodes': nodes, **extra}


def generate_scenes(directory):
    directory.mkdir()
    examples = PLUGIN / 'runtime/examples'
    shutil.copytree(examples / 'assets', directory / 'assets')
    controls = read_json(examples / 'controls.scene.json')
    controls['testPlan'] += [
        case('gain-controls-binding', [{'type': 'slider', 'target': 'gain', 'value': 6}], [state('gain', 6)]),
        case('text-input-is-state', [{'type': 'input', 'target': 'name', 'value': 'Acceptance'}], [state('name', 'Acceptance')]),
        # A 40×20 CSS-pixel gesture is transformed through scale 1.5 and
        # rotation 25°, then snapped to the five-unit parent grid.
        case('drag-constrained-parent', [{'type': 'drag', 'target': 'dragBox', 'dx': 40, 'dy': 20}],
             [{'type': 'attribute', 'target': 'dragBox', 'name': 'transform', 'contains': 'translate(55 20)'},
              state('box.x', 55), state('box.y', 20), state('dragged', True)]),
    ]
    controls.setdefault('derivedState', {})['dragged'] = e('state.box.x !== 25 || state.box.y !== 20')
    controls['testPlan'].append(case('reset-controls', [{'type': 'click', 'target': 'reset'}],
                                    [state('count', 0), state('gain', 2), state('box.x', 25), state('box.y', 20)]))
    charts = read_json(examples / 'charts-map.scene.json')
    charts['testPlan'] += [case('select-geo-feature', [{'type': 'click', 'target': 'map.geo-2'}],
                                    [state('selectedRegion', 'east')]),
                          case('reset-geography', [{'type': 'click', 'target': 'reset'}], [state('zoom', 1), state('mapX', 0)])]
    primitives = read_json(examples / 'primitives.scene.json')
    primitives['testPlan'].append(case('play-local-video', [
        {'type': 'click', 'target': 'videoPlay'}, {'type': 'wait', 'duration': 250},
        {'type': 'media', 'target': 'video', 'method': 'pause'}],
        [{'type': 'property', 'target': 'video', 'selector': 'video', 'name': 'videoWidth', 'equals': 256},
         {'type': 'property', 'target': 'video', 'selector': 'video', 'name': 'paused', 'equals': True}]))
    (directory / 'measurements.csv').write_text('label,value\nA,10\nB,20\nC,30\n')
    motion = scene('time-and-data', [
        node('title', 'Text', x=25, y=20, width=650, height=60, text='One clock, one shared state', fontSize=30),
        {**node('dot', 'Circle', y=160, radius=24, fill='#2563eb'), 'bind': {'x': e('40 + state.x')}},
        {**node('value', 'Text', x=25, y=220, width=650, height=65, fontSize=26), 'bind': {'text': e('"CSV sum = " + state.total + "; timeline x = " + format(state.x, 1)')}},
        node('play', 'Button', x=25, y=320, width=160, height=48, text='Play timeline'),
        node('tick', 'Button', x=215, y=320, width=160, height=48, text='Run compute'),
        node('stop', 'Button', x=405, y=320, width=160, height=48, text='Stop'),
        {**node('elapsed', 'Text', x=25, y=395, width=650, height=70, fontSize=24), 'bind': {'text': e('"Simulation ticks: " + state.frames + "; distance: " + format(state.distance, 2)')}},
        node('reset', 'Button', x=25, y=500, width=180, height=48, text='Reset all'),
    ], initialState={'x': 0, 'frames': 0, 'distance': 0},
       dataSources={'measurements': {'type': 'csv', 'path': 'measurements.csv'}},
       derivedState={'total': e('sum(pluck(data.measurements, "value"))'), 'hasTick': e('state.frames > 0 && state.distance > 0')},
       timelines=[{'id': 'move', 'duration': 1000, 'tracks': [{'path': 'x', 'keyframes': [{'time': 0, 'value': 0}, {'time': 1000, 'value': 180}]}]}],
       runtimeOptions={'loops': {'motion': [{'type': 'increment', 'path': 'frames'}, {'type': 'set', 'path': 'distance', 'value': e('state.distance + event.deltaTime * 10')}] }},
       interactions=[{'target': target, 'event': 'click', 'actions': actions} for target, actions in [
           ('play', [{'type': 'playTimeline', 'timeline': 'move'}]), ('tick', [{'type': 'startLoop', 'name': 'motion'}]),
           ('stop', [{'type': 'stopLoop', 'name': 'motion'}]), ('reset', [{'type': 'reset'}])]],
       testPlan=[case('csv-and-intermediate-timeline', [{'type': 'seekTimeline', 'timeline': 'move', 'time': 250}],
                      [state('total', 60), state('x', 45), {'type': 'timeline', 'timeline': 'move', 'property': 'time', 'equals': 250}]),
                 case('continuous-compute', [{'type': 'click', 'target': 'tick'}, {'type': 'wait', 'duration': 150}, {'type': 'click', 'target': 'stop'}], [state('hasTick', True)]),
                 case('reset-clock-and-state', [{'type': 'click', 'target': 'reset'}], [state('frames', 0), state('x', 0), state('total', 60)])])
    plugin_source = 'export default {id:"proof",version:"1.0.0",functions:{twice:x=>x*2}};\n'
    (directory / 'proof.js').write_text(plugin_source)
    code = scene('editable-code-and-plugin', [
        node('title', 'Text', x=20, y=10, width=660, height=50, text='Editable code → checked result', fontSize=28),
        {**node('editor', 'component', x=20, y=75, width=660, height=375, language='javascript', code='console.log("six times seven");\nreturn 6 * 7;', resultPath='result', outputHeight=70, fontSize=17), 'component': 'CodeEditor'},
        node('run', 'Button', x=20, y=465, width=270, height=48, text='Set seven and run'),
        node('change', 'Button', x=325, y=465, width=355, height=48, text='Change source to twelve'),
        {**node('answer', 'Text', x=20, y=525, width=660, height=55, fontSize=25), 'bind': {'text': e('"Plugin doubles result: " + state.doubled')}},
    ], requires=['code'], initialState={'result': {'result': 0}}, derivedState={'doubled': e('proof_twice(state.result.result)')},
       plugins=[{'id': 'proof', 'version': '1.0.0', 'path': 'proof.js', 'sha256': sha256(directory / 'proof.js'), 'capabilities': ['functions']}],
       runtimeOptions={'allowedPlugins': ['proof']},
       interactions=[{'target': target, 'event': 'click', 'actions': [
           {'type': 'plugin', 'name': 'code.setCode', 'args': {'target': 'editor', 'code': source}},
           {'type': 'plugin', 'name': 'code.run', 'args': {'target': 'editor'}}]} for target, source in [
               ('run', 'console.log("seven"); return 7;'), ('change', 'return 12;')]],
       testPlan=[case('formal-object-arguments-run', [{'type': 'click', 'target': 'run'}, {'type': 'wait', 'duration': 200}],
                      [state('result.status', 'done'), state('result.result', 7), state('doubled', 14)]),
                 case('edited-code-changes-result', [{'type': 'click', 'target': 'change'}, {'type': 'wait', 'duration': 200}],
                      [state('result.result', 12), state('doubled', 24)])])
    model_dir = directory / 'model'
    model_dir.mkdir()
    positions = struct.pack('<9f', -1, -1, 0, 1, -1, 0, 0, 1, 0)
    (model_dir / 'triangle.bin').write_bytes(positions)
    atomic_json(model_dir / 'triangle.gltf', {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
        'nodes': [{'name': 'triangle', 'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
        'buffers': [{'byteLength': len(positions), 'uri': 'triangle.bin'}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(positions), 'target': 34962}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [-1, -1, 0], 'max': [1, 1, 0]}]})
    three = scene('portable-external-gltf', [
        node('title', 'Text', x=20, y=10, width=660, height=55, text='Real glTF + external binary', fontSize=28),
        {**node('model', 'component', x=20, y=80, width=660, height=420, src='model/triangle.gltf', camera={'position': [0, 0, 3], 'target': [0, 0, 0]}, selectionPath='selected'), 'component': 'ThreeScene'},
        {**node('selected', 'Text', x=20, y=515, width=660, height=60, fontSize=25), 'bind': {'text': e('"Raycast selection: " + state.selected')}},
    ], requires=['three'], initialState={'selected': 'none', 'loaded': False},
       interactions=[{'target': 'model', 'event': 'threeReady', 'actions': [{'type': 'set', 'path': 'loaded', 'value': True}]}],
       testPlan=[case('gltf-dependencies-loaded', [{'type': 'wait', 'duration': 500}], [state('loaded', True)]),
                 case('select-real-triangle', [{'type': 'click', 'target': 'model'}], [state('selected', 'triangle')])])
    records = [controls, charts, primitives, motion, code, three]
    for value in records:
        path = directory / (value['id'] + '.json')
        atomic_json(path, value)
        # This exercises the public Python schema path, not debug API dispatch.
        result = subprocess.run([sys.executable, str(PLUGIN / 'skills/pptx/scripts/pptx.py'), 'interactive', 'validate-spec', str(path)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Formal validate-spec failed: ' + result.stderr + result.stdout)
    return {value['id']: directory / (value['id'] + '.json') for value in records}


def native_text(tree, ident, text, x, y, width, height, size=26):
    a = NS['a']; p = NS['p']
    sp = etree.SubElement(tree.find('p:cSld/p:spTree', NS), f'{{{p}}}sp')
    nv = etree.SubElement(sp, f'{{{p}}}nvSpPr'); etree.SubElement(nv, f'{{{p}}}cNvPr', id=str(ident), name='Native context ' + str(ident)); etree.SubElement(nv, f'{{{p}}}cNvSpPr', txBox='1'); etree.SubElement(nv, f'{{{p}}}nvPr')
    pr = etree.SubElement(sp, f'{{{p}}}spPr'); xfrm = etree.SubElement(pr, f'{{{a}}}xfrm'); etree.SubElement(xfrm, f'{{{a}}}off', x=str(round(x*EMU)), y=str(round(y*EMU))); etree.SubElement(xfrm, f'{{{a}}}ext', cx=str(round(width*EMU)), cy=str(round(height*EMU)))
    geom = etree.SubElement(pr, f'{{{a}}}prstGeom', prst='rect'); etree.SubElement(geom, f'{{{a}}}avLst'); etree.SubElement(pr, f'{{{a}}}noFill')
    body = etree.SubElement(sp, f'{{{p}}}txBody'); etree.SubElement(body, f'{{{a}}}bodyPr', wrap='square', lIns='0', rIns='0', tIns='0', bIns='0'); etree.SubElement(body, f'{{{a}}}lstStyle')
    for line in text.split('\n'):
        para = etree.SubElement(body, f'{{{a}}}p'); run = etree.SubElement(para, f'{{{a}}}r'); rp = etree.SubElement(run, f'{{{a}}}rPr', lang='en-US', sz=str(size*100)); fill = etree.SubElement(rp, f'{{{a}}}solidFill'); etree.SubElement(fill, f'{{{a}}}srgbClr', val='172033'); etree.SubElement(rp, f'{{{a}}}latin', typeface='Aptos'); etree.SubElement(run, f'{{{a}}}t').text = line


def prepare_native(ws):
    original_slide = (ws.root / 'ppt/slides/slide1.xml').read_bytes()
    original_rels = (ws.root / 'ppt/slides/_rels/slide1.xml.rels').read_bytes()
    presentation = parse(ws.root / 'ppt/presentation.xml'); ids = presentation.find('p:sldIdLst', NS)
    rels = parse(ws.root / 'ppt/_rels/presentation.xml.rels'); types = parse(ws.root / '[Content_Types].xml')
    titles = ['Controls, state and bindings', 'Data, geography and a shared clock', 'Primitives, components and local media', 'Executable code and portable 3D assets']
    for index, title in enumerate(titles, 1):
        tree = etree.fromstring(original_slide)
        native_text(tree, 2, title, .45, .22, 12.4, .62, 28)
        if index == 1:
            native_text(tree, 3, 'Engineering checks\n\nKeyboard, form input and transformed drag mutate one store.\n\nReset restores the declared initial values.\n\nNative context stays editable.', 8.8, 1.35, 3.9, 4.8, 20)
        if index == 3:
            native_text(tree, 3, 'Composed from the shared runtime\n\nVectors, data charts, table, image comparison and real local video.\n\nNo topic-specific renderer.\n\nStatic fallback remains in this PPTX.', 8.8, 1.35, 3.9, 4.8, 20)
        native_text(tree, 4, 'Synthetic acceptance fixture · Standalone runtime tested · PowerPoint desktop playback not verified', .45, 7.0, 12.4, .3, 11)
        (ws.root / f'ppt/slides/slide{index}.xml').write_bytes(etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True))
        if index > 1:
            (ws.root / f'ppt/slides/_rels/slide{index}.xml.rels').write_bytes(original_rels)
            rid = 'rIdShowcase' + str(index)
            etree.SubElement(ids, f'{{{P}}}sldId', id=str(256+index), **{f'{{{R}}}id': rid})
            etree.SubElement(rels, f'{{{PR}}}Relationship', Id=rid, Type=R+'/slide', Target=f'slides/slide{index}.xml')
            etree.SubElement(types, f'{{{CT}}}Override', PartName=f'/ppt/slides/slide{index}.xml', ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
    for path, tree in [(ws.root/'ppt/presentation.xml', presentation), (ws.root/'ppt/_rels/presentation.xml.rels', rels), (ws.root/'[Content_Types].xml', types)]:
        path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True))
    ws.refresh(); ws.save(); validate(ws.root).require()


async def served_proof(bundle, url, output):
    output.mkdir()
    deck = read_json(bundle / 'deck/bundle.json'); evidence = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        for ident, entry in deck['scenes'].items():
            spec = read_json(bundle / 'deck' / entry['path'])
            page = await browser.new_page(viewport=spec['viewport'], reduced_motion='reduce')
            errors = []; requests = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: requests.append({'url': response.url, 'status': response.status}))
            await page.goto(url + '/preview.html?deck=' + deck['deckId'] + '&scene=' + ident)
            await page.locator('[data-ready=true]').wait_for()
            assert await page.evaluate('window.__interactive.ready')
            print('served', ident, flush=True)
            assertions = 0
            for test in spec['testPlan']:
                if test.get('reset'): await page.evaluate('window.__interactive.dispatch([{type:"reset"}])')
                for action in test['actions']: await execute(page, action)
                for item in test['assertions']: await assertion(page, item); assertions += 1
            assert not errors, errors
            assert await page.evaluate('window.__interactive.runtime.error') is None
            await page.screenshot(path=str(output / (ident + '.png')))
            evidence.append({'scene': ident, 'tests': len(spec['testPlan']), 'assertions': assertions,
                             'successfulExternalBinRequests': sum(r['status'] == 200 and r['url'].endswith('.bin') for r in requests)})
            await page.close()
        await browser.close()
    assert next(row for row in evidence if row['scene'] == 'portable-external-gltf')['successfulExternalBinRequests'] >= 1
    return evidence


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    output = Path(args.out).absolute(); output.mkdir(parents=True, exist_ok=False)
    sources = generate_scenes(output / 'scenes'); source_inventory = manifest(output / 'scenes')
    atomic_json(output / 'outline.json', {'title': 'Interactive Runtime Technical Acceptance', 'purpose': 'Verify shared mechanisms across a real native package and its portable runtime.', 'slides': [
        {'id': 'controls', 'title': 'Controls and state', 'summary': 'Keyboard, drag and form inputs update bound values; reset restores initial state.', 'presentationMode': 'hybrid'},
        {'id': 'data', 'title': 'Data and time', 'summary': 'Two independent regions expose data/GeoJSON selection and timeline/compute state.', 'presentationMode': 'hybrid'},
        {'id': 'primitives', 'title': 'Composition and media', 'summary': 'Shared primitives/components render real local media and meaningful static fallback.', 'presentationMode': 'hybrid'},
        {'id': 'extensions', 'title': 'Code and 3D', 'summary': 'Formal plugin actions edit/run real code; a hashed custom function and external glTF resource survive packaging.', 'presentationMode': 'hybrid'}]})
    blank = PLUGIN / 'skills/pptx/assets/blank.pptx'; blank_hash = sha256(blank)
    ws = unpack(blank, output / 'authoring'); prepare_native(ws)
    placements = [(1, 'controls-showcase', .45, 1.0, 7.9, 5.53),
                  (2, 'charts-and-geography', .45, 1.05, 7.2, 5.04), (2, 'time-and-data', 7.9, 1.05, 4.98, 4.269),
                  (3, 'primitive-component-gallery', .45, 1.0, 7.9, 5.596),
                  (4, 'editable-code-and-plugin', .45, 1.0, 6.08, 5.211), (4, 'portable-external-gltf', 6.82, 1.0, 6.08, 5.211)]
    attachments = []
    for slide, ident, x, y, width, height in placements:
        print('attach', ident, flush=True)
        result = attach(ws, slide, sources[ident], {k: round(v*EMU) for k, v in {'x': x, 'y': y, 'width': width, 'height': height}.items()})
        assert result['runtime_verified']; attachments.append(result)
    validate(ws.root).require(); assert validate_interactive(ws.root, require_runtime=True)['runtime_verified']
    native_before = manifest(ws.root); sidecar_before = manifest(ws.home / 'interactive/deck')
    exported = export(ws, output / 'showcase-before-bundle.pptx'); native_render = copy.deepcopy(ws.state['last_render'])
    reopened = unpack(exported, output / 'reopened'); shutil.copytree(ws.home / 'interactive', reopened.home / 'interactive')
    validate(reopened.root).require()
    for ident in sources: scene_render(reopened, ident)
    assert validate_interactive(reopened.root, require_runtime=True)['runtime_verified']
    print('bundle', flush=True)
    distribution = assemble_bundle(ws, output / 'showcase-interactive', zip_output=True); bundle = Path(distribution['bundle'])
    assert not changed_paths(native_before, manifest(ws.root)) and not changed_paths(sidecar_before, manifest(ws.home / 'interactive/deck'))
    assert not changed_paths(source_inventory, manifest(output / 'scenes')) and sha256(blank) == blank_hash
    controller = [sys.executable, str(bundle / 'scripts/bundle_control.py')]
    checked = subprocess.run(controller + ['verify'], capture_output=True, text=True, check=True)
    started = subprocess.run(controller + ['start', '--http', '--port', '0'], capture_output=True, text=True, check=True)
    status = json.loads(started.stdout)
    try: served = asyncio.run(served_proof(bundle, status['url'], output / 'served-preview'))
    finally: subprocess.run(controller + ['stop'], capture_output=True, text=True, check=True)
    report = {'ok': True, 'purpose': 'Synthetic engineering acceptance; not CNN/YOLO', 'slides': 4, 'regions': len(attachments),
              'bundle': distribution, 'integrity': json.loads(checked.stdout), 'servedTests': served, 'nativeRender': native_render,
              'nativePartsPreservedByBundle': True, 'sidecarsPreservedByBundle': True, 'sourceAssetsUnchanged': True,
              'reopenedInstances': len(discover_content_addins(reopened.root)), 'formalSchemaValidated': True,
              'runtime_verified': True, 'powerpoint_playback_verified': False,
              'browserReports': {ident: read_json(ws.home / 'interactive/tests' / (ident + '.json')) for ident in sources}}
    atomic_json(output / 'acceptance-evidence.json', report)
    print(json.dumps({'ok': True, 'evidence': str(output / 'acceptance-evidence.json'), 'bundle': str(bundle), 'regions': 6}, indent=2))


if __name__ == '__main__': main()
