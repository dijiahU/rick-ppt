"""Export a fresh complete candidate and atomically declare its exact file.

Reuses native export/render and the existing authored decision check. This is a
candidate checkpoint, not independent review, aesthetic approval or delivery.
"""
import argparse
try:
    from pptx_core import portable_lock as fcntl
except ImportError:
    from .pptx_core import portable_lock as fcntl
import json
import os
from pathlib import Path
import re
import uuid
import zipfile

from lxml import etree

if __package__:
    from . import deck_style
    from .page_design import scoped, read
    from .pptx_core.common import NS, PptxError, sha256
    from .pptx_core.package import select, export
    from .pptx_core.relationships import rels_part, resolve_target
    from .workflow_decisions import validate_plan, MAX_PLAN_BYTES
    from .layout_checks import background, is_cream, plain_pages, slide_size, surface_audit
else:
    import deck_style
    from page_design import scoped, read
    from pptx_core.common import NS, PptxError, sha256
    from pptx_core.package import select, export
    from pptx_core.relationships import rels_part, resolve_target
    from workflow_decisions import validate_plan, MAX_PLAN_BYTES
    from layout_checks import background, is_cream, plain_pages, slide_size, surface_audit

ALLOW_CREAM = ('米白', '奶油', '象牙', '米色', 'cream', 'ivory', 'beige')
# Fonts that ship with Windows and Office for Mac (fonts.md); anything else falls back on recipients' machines.
SHIPPED_FONTS = {'times new roman', 'simsun', '宋体', 'dengxian', 'dengxian light', '等线', '等线 light', 'arial', 'arial black',
                 'microsoft yahei', 'microsoft yahei light', '微软雅黑', '微软雅黑 light', 'simhei', '黑体', 'kaiti', '楷体',
                 'fangsong', '仿宋', 'calibri', 'calibri light', 'cambria', 'cambria math', 'georgia', 'century gothic',
                 'verdana', 'tahoma', 'wingdings', 'wingdings 2', 'wingdings 3', 'webdings', 'symbol'}
# A label line ("来源：…", "Click 2: …"), not a spoken sentence that happens to begin with
# such a word ("Photographs from the lab show…", "点击之后…").
NOTE_LABEL = re.compile(r'(?:来源|出处|Sources?|Credits?|Photo(?: credit)?|图片来源|设计参考|Design references?|'
                        r'阅读顺序|Reading order|点击\s*\d*|Click\s*\d*|备注|Notes?|TODO)\s*[：:]', re.I)
NOTE_LINK = re.compile(r'https?://', re.I)
NOTE_MARKER = re.compile(r'\[PPTX-', re.I)
NOTE_CREDIT = re.compile(r'\b(?:CC[\s-]+BY|CC[\s-]*0|Creative Commons|Wikimedia|Unsplash|Pexels)\b', re.I | re.ASCII)
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\U0002f800-\U0002fa1f\U00030000-\U000323af]')
ENGLISH_WORD = re.compile(r"[a-z]+(?:['’-][a-z]+)*", re.I | re.ASCII)


def check_speaker_notes(archive, slides):
    names = set(archive.namelist())
    def relations(part):
        path = rels_part(part)
        return etree.fromstring(archive.read(path)) if path in names else []

    targets = {rel.get('Id'): rel.get('Target') for rel in relations('ppt/presentation.xml')}
    errors = []
    for number, slide in enumerate(slides, 1):
        part = resolve_target('ppt/presentation.xml', targets[slide.get('{%s}id' % NS['r'])])
        note = next((rel for rel in relations(part) if rel.get('Type', '').endswith('/notesSlide')
                     and rel.get('TargetMode') != 'External'), None)
        lines, links = [], set()
        if note is not None:
            note_part = resolve_target(part, note.get('Target'))
            tree = etree.fromstring(archive.read(note_part))
            for shape in tree.findall('.//p:sp', NS):
                if shape.find('p:nvSpPr/p:nvPr/p:ph[@type="body"]', NS) is None:
                    continue
                for paragraph in shape.findall('p:txBody/a:p', NS):
                    lines.append(''.join('\n' if node.tag == '{%s}br' % NS['a'] else node.findtext('a:t', '', NS)
                                         for node in paragraph))
                links.update(node.get('{%s}id' % NS['r']) for tag in ('hlinkClick', 'hlinkMouseOver')
                             for node in shape.iter('{%s}%s' % (NS['a'], tag)))
        text = '\n'.join(lines)
        reasons = []
        if not text.strip():
            reasons.append('缺少讲稿备注')
        elif len(HAN.findall(text)) < 60 and len(ENGLISH_WORD.findall(text)) < 25:
            reasons.append('讲稿过短，至少需要 60 个汉字或 25 个英文单词')
        for line in text.splitlines():
            match = NOTE_LABEL.match(line.lstrip())
            if match:
                reasons.append(f'含非讲稿行首标签「{match.group().rstrip("：: ")}」')
                break
        if NOTE_LINK.search(text) or (links and any(rel.get('Id') in links and NOTE_LINK.match(rel.get('Target', ''))
                                                    for rel in relations(note_part))):
            reasons.append('含 HTTP/HTTPS 链接')
        if NOTE_MARKER.search(text):
            reasons.append('含 [PPTX- 标记')
        if NOTE_CREDIT.search(text):
            reasons.append('含许可说明或图库名')
        if reasons:
            errors.append(f'第 {number} 页（' + '、'.join(reasons) + '）')
    if errors:
        raise ValueError('；'.join(errors) + '。备注只写讲者要说的话。来源和许可写在页面上的图注或参考文献页，'
                         '设计记录写在 decision-plan.json 或 page-plans.json。')


def unshipped_fonts(artifact):
    """Text fonts used in the deck that recipients do not have (2026-11-21: a template's 思源黑体 Heavy
    title rendered thin in the renderer and on Windows, and the review missed why)."""
    found = {}
    pattern = re.compile(r'<a:(?:latin|ea|cs)\b[^>]*?typeface="([^"]*)"')
    with zipfile.ZipFile(artifact) as archive:
        for name in archive.namelist():
            if re.match(r'ppt/(slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster|theme/theme)\d+\.xml$', name):
                for family in pattern.findall(archive.read(name).decode('utf-8', 'ignore')):
                    if family and not family.startswith('+') and family.lower() not in SHIPPED_FONTS:
                        found[family] = found.get(family, 0) + 1
    return dict(sorted(found.items(), key=lambda kv: -kv[1]))


CHINESE_FACES = {'simsun', '宋体', 'nsimsun', 'dengxian', 'dengxian light', '等线', '等线 light', 'microsoft yahei',
                 'microsoft yahei light', '微软雅黑', 'simhei', '黑体', 'kaiti', '楷体', 'fangsong', '仿宋', 'songti sc',
                 'pingfang sc', 'noto serif cjk sc', 'noto sans cjk sc', 'source han serif sc', 'source han sans sc'}


def font_report(root, artifact, language):
    """Fonts used per slot, faces the preview cannot find, and Japanese text set in Chinese faces
    (2026-11-26: font choice is open; a Japanese deck shipped in SimSun/DengXian)."""
    import shutil
    import subprocess
    used, wrong_script = {}, set()
    pattern = re.compile(r'<a:(latin|ea|cs)\b[^>]*?typeface="([^"]*)"')
    with zipfile.ZipFile(artifact) as archive:
        for name in archive.namelist():
            if re.match(r'ppt/(slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster|theme/theme)\d+\.xml$', name):
                for slot, family in pattern.findall(archive.read(name).decode('utf-8', 'ignore')):
                    if not family or family.startswith('+'):
                        continue
                    used[family] = used.get(family, 0) + 1
                    if slot == 'ea' and str(language).startswith('ja') and family.lower() in CHINESE_FACES:
                        wrong_script.add(family)
    missing = []
    fc = shutil.which('fc-match') or next((p for p in ('/opt/homebrew/bin/fc-match', '/usr/bin/fc-match')
                                           if Path(p).is_file()), None)
    conf = Path(root) / 'fonts.conf'
    if fc and conf.is_file():
        for family in list(used)[:24]:
            try:
                got = subprocess.run([fc, '-f', '%{family}', family], capture_output=True, text=True, timeout=20,
                                     env={**os.environ, 'FONTCONFIG_FILE': str(conf)}).stdout
            except (OSError, subprocess.SubprocessError):
                break
            names = {n.strip().lower() for n in got.split(',')}
            if got and family.lower() not in names and not any(family.lower() in n or n in family.lower() for n in names if n):
                missing.append({'family': family, 'preview_uses': got.split(',')[0]})
    return {'fonts_used': dict(sorted(used.items(), key=lambda kv: -kv[1])), 'preview_missing': missing,
            'wrong_script': sorted(wrong_script)}


def template_grounds(root):
    """Background colours carried by template decks copied into this task (references/templates)."""
    found = set()
    folder = Path(root) / 'references' / 'templates'
    if not folder.is_dir():
        return found
    for path in folder.glob('*.pptx'):
        try:
            for _, colour in cream_slides(path, every=True):
                found.add(colour.upper())
        except Exception:
            continue
    return found


def template_surfaces(root):
    """Panel colours carried by template decks copied into this task (references/templates)."""
    found = set()
    folder = Path(root) / 'references' / 'templates'
    for path in (folder.glob('*.pptx') if folder.is_dir() else []):
        try:
            with zipfile.ZipFile(path) as archive:
                found |= {c.upper() for _, c, _ in surface_audit(archive)['cream_surfaces']}
        except Exception:
            continue
    return found


def surfaces(artifact):
    try:
        with zipfile.ZipFile(artifact) as archive:
            return surface_audit(archive)
    except Exception:
        return {'cream_surfaces': [], 'card_pages': {}, 'muted_cool_share': 0.0, 'muted_colours': []}


def cream_slides(artifact, every=False):
    """Slide numbers whose visible background (slide, else layout, else master) is cream."""
    import posixpath
    rel_ns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    with zipfile.ZipFile(artifact) as archive:
        names = set(archive.namelist())
        load = lambda part: etree.fromstring(archive.read(part))
        def related(part, kind):
            rels = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
            if rels not in names:
                return None
            for rel in load(rels).iter(rel_ns + 'Relationship'):
                if rel.get('Type', '').endswith('/' + kind):
                    return posixpath.normpath(posixpath.join(posixpath.dirname(part), rel.get('Target')))
            return None
        size = slide_size(load('ppt/presentation.xml'))
        pres_rels = {r.get('Id'): r.get('Target') for r in load('ppt/_rels/presentation.xml.rels').iter(rel_ns + 'Relationship')}
        found = []
        ids = load('ppt/presentation.xml').findall('p:sldIdLst/p:sldId', NS)
        for number, sid in enumerate(ids, 1):
            part = posixpath.normpath(posixpath.join('ppt', pres_rels[sid.get('{%s}id' % NS['r'])]))
            colour, current = None, part
            for kind in (None, 'slideLayout', 'slideMaster'):
                current = current if kind is None else (related(current, kind) if current else None)
                if not current or current not in names:
                    break
                colour = background(load(current), size)
                if colour:
                    break
            if colour and (every or is_cream(colour)):
                found.append((number, colour))
        return found


def unit_collisions(artifact):
    """Pages where layout_checks finds a unit over its number (2026-11-21: seen in every deck
    version, never raised by reviewers, and missed when the page was not re-inspected)."""
    try:
        from .layout_checks import check
    except ImportError:
        from layout_checks import check
    found = []
    try:
        with zipfile.ZipFile(artifact) as z:
            size = slide_size(etree.fromstring(z.read('ppt/presentation.xml')))
            names = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                           key=lambda n: int(re.search(r'(\d+)', n.rsplit('/', 1)[1]).group(1)))
            for name in names:
                issues = check(etree.fromstring(z.read(name)), size)
                objects = [i['object'] for i in issues if i['kind'] == 'unit_over_number']
                if objects:
                    found.append({'slide': int(re.search(r'(\d+)', name.rsplit('/', 1)[1]).group(1)), 'objects': objects})
    except Exception:
        return []
    return found


BLANK_RUN = re.compile(r'_{3,}|＿{2,}|（\s*）|\(\s{2,}\)')


def blank_fields(artifact):
    """Pages whose text holds fill-in blanks (2026-11-22: a brand deck shown on screen carried
    ____ in every formula slot and empty form lines; reviewers called them a practical form)."""
    found = []
    try:
        with zipfile.ZipFile(artifact) as z:
            for name in z.namelist():
                match = re.fullmatch(r'ppt/slides/slide(\d+)\.xml', name)
                if not match:
                    continue
                text = ''.join(etree.fromstring(z.read(name)).itertext())
                if BLANK_RUN.search(text):
                    found.append(int(match.group(1)))
    except Exception:
        return []
    return sorted(found)


def _declare(root, value, previous):
    target = scoped(root, 'delivery.json')
    current = read(root, 'delivery.json', 10000) if target.exists() else None
    if current != previous:
        raise ValueError('Delivery declaration changed while saving candidate')
    pending = root / ('.delivery-' + uuid.uuid4().hex + '.json')
    try:
        with pending.open('xb') as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def _slide_order(archive):
    tree = etree.fromstring(archive.read('ppt/presentation.xml'))
    rels = etree.fromstring(archive.read('ppt/_rels/presentation.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in rels}
    rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    return ['ppt/' + targets[s.get(rid)].lstrip('/').replace('ppt/', '', 1)
            for s in tree.findall('p:sldIdLst/p:sldId', NS)]


def skeleton_report(artifact):
    """Consecutive pages with the same skeleton and the most common page opener (2026-11-26:
    four seasonal pages and most report pages repeated one layout)."""
    a, p = NS['a'], NS['p']
    with zipfile.ZipFile(artifact) as archive:
        size = etree.fromstring(archive.read('ppt/presentation.xml')).find('p:sldSz', NS)
        sw, sh = int(size.get('cx')), int(size.get('cy'))
        sigs, openers = [], []
        for name in _slide_order(archive):
            tree = etree.fromstring(archive.read(name))
            pictures, texts, rules = [], [], 0
            for shape in tree.find('p:cSld/p:spTree', NS):
                off = shape.find('.//a:xfrm/a:off', NS); ext = shape.find('.//a:xfrm/a:ext', NS)
                if off is None or ext is None:
                    continue
                x, y, w, h = (int(off.get('x')) / sw, int(off.get('y')) / sh, int(ext.get('cx')) / sw, int(ext.get('cy')) / sh)
                if w * h < 0.0005 and not (y < 0.25 and (w > 0.05 or h > 0.05)):
                    continue
                is_picture = shape.tag == f'{{{p}}}pic' or shape.find('.//a:blipFill', NS) is not None
                text = ''.join(shape.itertext()).strip() if shape.find('.//a:t', NS) is not None else ''
                if is_picture and w * h > 0.06:
                    pictures.append((round(x * 5), round(w * 5), round(y * 4), round(h * 4)))
                elif text:
                    sizes = [int(r.get('sz')) for r in shape.iter(f'{{{a}}}rPr') if r.get('sz')]
                    texts.append((y, x, max(sizes or [1800]), w * h, w))
                elif y < 0.25 and (h < 0.012 or w < 0.012):
                    rules += 1
            texts.sort()
            big = sorted(texts, key=lambda t: -t[2])[:2]
            # A mirrored copy (picture left on one page, right on the next) is the same skeleton.
            flip = bool(pictures) and max(pictures, key=lambda r: r[1] * r[3])[0] + max(pictures, key=lambda r: r[1] * r[3])[1] / 2 > 2.5
            mirror = (lambda gx, gw: 5 - gx - gw) if flip else (lambda gx, gw: gx)
            centre = (lambda t: round((1 - t[1] - t[4] / 2) * 5)) if flip else (lambda t: round((t[1] + t[4] / 2) * 5))
            sigs.append((tuple(sorted((mirror(px, pw), pw, py, ph) for px, pw, py, ph in pictures)),
                         tuple((centre(t), round(t[0] * 5), round(t[3] * 10)) for t in big)))
            top = [t for t in texts if t[0] < 0.3][:2]
            openers.append(tuple((round(t[1] * 10), round(t[0] * 10), t[2] // 800) for t in top))
    runs, start = [], 0
    for i in range(1, len(sigs) + 1):
        if i == len(sigs) or sigs[i] != sigs[start]:
            if i - start >= 3:
                runs.append(list(range(start + 1, i + 1)))
            start = i
    body = openers[1:-1] if len(openers) > 2 else []
    common = max(set(body), key=body.count) if body else None
    share = body.count(common) / len(body) if body else 0
    same_opener = [i + 2 for i, o in enumerate(body) if o == common] if len(body) >= 6 and share > 0.8 and len(common) >= 2 else []
    return {'runs': runs, 'same_opener': same_opener}


def upscaled_pictures(artifact, slide_px=1920, limit=1.5):
    """Pictures shown well beyond their source pixels (2026-11-26: a 250 px reproduction
    stretched to half a slide went out blurred)."""
    import io as _io
    from PIL import Image
    r_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    found = []
    with zipfile.ZipFile(artifact) as archive:
        size = etree.fromstring(archive.read('ppt/presentation.xml')).find('p:sldSz', NS)
        sw = int(size.get('cx'))
        for number, name in enumerate(_slide_order(archive), 1):
            tree = etree.fromstring(archive.read(name))
            rels_name = name.replace('slides/', 'slides/_rels/') + '.rels'
            if rels_name not in archive.namelist():
                continue
            rels = {r.get('Id'): r.get('Target') for r in etree.fromstring(archive.read(rels_name))}
            for pic in tree.iter(f'{{{NS["p"]}}}pic'):
                blip = pic.find('.//a:blip', NS); ext = pic.find('.//a:xfrm/a:ext', NS)
                if blip is None or ext is None or blip.get(f'{{{r_ns}}}embed') not in rels:
                    continue
                target = rels[blip.get(f'{{{r_ns}}}embed')]
                media = 'ppt/' + target.replace('../', '') if not target.startswith('/') else target.lstrip('/')
                if media not in archive.namelist() or not media.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                try:
                    with Image.open(_io.BytesIO(archive.read(media))) as image:
                        width = image.size[0]
                except OSError:
                    continue
                crop = pic.find('.//a:srcRect', NS)
                keep = 1.0
                if crop is not None:
                    keep -= (int(crop.get('l', 0)) + int(crop.get('r', 0))) / 100000
                shown = int(ext.get('cx')) / sw * slide_px
                source = width * max(keep, 0.01)
                if shown > 360 and shown / source > limit:
                    found.append({'page': number, 'media': media.split('/')[-1], 'source_px': round(source),
                                  'shown_px_at_1920': round(shown), 'scale': round(shown / source, 1)})
    return found


def generic_palette(root):
    """Dark navy/teal plus an orange/coral accent: the most common generated palette."""
    import colorsys
    path = Path(root) / 'deck-style.json'
    try:
        colors = json.loads(path.read_text()).get('colors') or {}
    except (OSError, ValueError):
        return None
    hls = []
    for value in colors.values():
        if isinstance(value, str) and re.fullmatch(r'#?[0-9A-Fa-f]{6}', value.strip()):
            v = value.strip().lstrip('#')
            r, g, b = (int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))
            hls.append((value, *colorsys.rgb_to_hls(r, g, b)))
    navy = [c for c, h, l, s in hls if 0.5 <= h <= 0.67 and l < 0.32 and s > 0.25]
    orange = [c for c, h, l, s in hls if (h <= 0.1 or h >= 0.97) and 0.3 < l < 0.72 and s > 0.45]
    return {'dark': navy[:2], 'accent': orange[:2]} if navy and orange else None


def outside_reference_missing(plan):
    """True when every applied reference is a library template or the user's own attachment
    (2026-11-26: decks borrowed only from commercial templates read as templates)."""
    refs = [r for r in plan.get('references') or [] if isinstance(r, dict) and r.get('applications')]
    if not refs:
        return False
    def outside(r):
        source = str(r.get('source') or '')
        if r.get('kind') == 'supplied_system':
            return False
        return not source.startswith(('references/library/', 'references/templates/'))
    return not any(outside(r) for r in refs)


def research_searches(plan):
    """Whether the plan says research was allowed to look outside the supplied material.
    Only then can an outside reference be required (2026-11-27)."""
    return (plan.get('task') or {}).get('research') in ('targeted_verification', 'topic_research')


def poster_move_gaps(root, count):
    """Cover and closing pages should name the page's poster move (2026-11-24)."""
    path = Path(root) / 'design-task.json'
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    gaps = []
    for page in data.get('pages') or []:
        if not isinstance(page, dict) or page.get('page') not in (1, count):
            continue
        move = (page.get('handoff') or {}).get('poster_move')
        if not (isinstance(move, str) and move.strip()):
            gaps.append(page['page'])
    return sorted(set(gaps))


def save_candidate(task_root, workspace, output, *, allow_legacy=False):
    root = Path(task_root).resolve(strict=True)
    ws = select(scoped(root, workspace))
    scoped(root, ws.home)
    scoped(root, ws.root)
    destination = scoped(root, output)
    declaration = scoped(root, 'delivery.json')
    lock = scoped(root, '.candidate-save.lock')
    with os.fdopen(os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600), 'r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        previous = read(root, 'delivery.json', 10000) if declaration.exists() else None
        request = json.loads(read(root, 'request.json')) if scoped(root, 'request.json').exists() else {}
        has_plan = scoped(root, 'decision-plan.json').exists()
        has_outline = scoped(root, 'outline.json').exists()
        if has_plan != has_outline:
            raise ValueError('Retain and reconcile both outline and decision plan before declaring a candidate')
        plan = json.loads(read(root, 'decision-plan.json', MAX_PLAN_BYTES)) if has_plan else {}
        mode = request.get('mode') or plan.get('task', {}).get('operation') or 'create'
        new_deck = mode == 'create' and not allow_legacy
        if new_deck:
            scoped(root, deck_style.FILE)
            deck_style.load(root, require_quiet=True)
        # A new path is created by native export; existing exports are immutable.
        artifact = export(ws, destination)
        plain = []
        with zipfile.ZipFile(artifact) as archive:
            tree = etree.fromstring(archive.read('ppt/presentation.xml'))
            slides = tree.findall('p:sldIdLst/p:sldId', NS)
            count = len(slides)
            expected = request.get('pages')
            if type(expected) is int and expected > 0 and count != expected:
                raise ValueError('Complete candidate page count differs from request')
            if mode == 'create':
                check_speaker_notes(archive, slides)
            if new_deck:
                try:
                    plain = plain_pages(archive)
                except Exception:
                    pass
        wording = ' '.join(str(request.get(k) or '') for k in ('brief', 'style')).lower()
        if request.get('mode', 'create') == 'create' and not any(w in wording for w in ALLOW_CREAM):
            # 2026-11-21 (Rick): no self-declared exemption. An author once declared #FAF5EA as the
            # deck ground in deck-style.json and shipped a cream deck. Only the brief, or a template
            # base whose own masters carry the colour, may bring a cream ground.
            cream = cream_slides(artifact)
            inherited = template_grounds(root)
            cream = [(n, c) for n, c in cream if c.upper() not in inherited]
            panels = [(n, c, pct) for n, c, pct in surfaces(artifact)['cream_surfaces']
                      if c.upper() not in inherited | template_surfaces(root)]
            if panels and not cream:
                raise ValueError('Warm-white/cream/beige panels are excluded for new decks (2026-11-22: cream cards '
                    'read as generated): ' + ', '.join(f'slide {n} #{c} ({pct}% of the page)' for n, c, pct in panels)
                    + '. Put the text on the page ground, on white, on a photo field or on a colour at clearly '
                    'visible strength, or group it with space and a rule instead of a box, and save again.')
            if cream:
                raise ValueError('Warm-white/cream/beige backgrounds are excluded for new decks: ' + ', '.join(
                    f'slide {n} #{c}' for n, c in cream) + '. Use white, a cool or neutral light grey, a colour taken '
                    'from the subject at clearly visible strength, or a dark ground, and save again.')
        authored = None
        if has_plan:
            outline = json.loads(read(root, 'outline.json'))
            authored = validate_plan(plan, outline, stage='authored', root=root,
                                     artifact=artifact, mode=mode,
                                     allow_legacy=allow_legacy,
                                     require_click_reveal=False if allow_legacy else None)
        try:
            fonts = font_report(root, artifact, request.get('language') or '') if request.get('mode', 'create') == 'create' else {}
        except (OSError, ValueError, zipfile.BadZipFile):
            fonts = {}
        units = unit_collisions(artifact) if request.get('mode', 'create') == 'create' else []
        blanks = blank_fields(artifact) if request.get('mode', 'create') == 'create' else []
        audit = surfaces(artifact) if request.get('mode', 'create') == 'create' else surfaces(None)
        card_pages = sorted(audit['card_pages'])
        too_many_cards = len(card_pages) > max(2, count // 8) or any(v >= 3 for v in audit['card_pages'].values())
        move_gaps = poster_move_gaps(root, count) if request.get('mode', 'create') == 'create' else []
        library_only = new_deck and outside_reference_missing(plan)
        if library_only and research_searches(plan):
            # A warning was ignored in every 2026-11-26 deck: each one borrowed only
            # templates or the user's attachment and read as a commercial template.
            raise ValueError('Every borrowed reference comes from the template library or the user\'s own attachment, '
                             'and this plan allows research. The library is a structure source, not a craft standard: '
                             'find at least one work from outside it (exhibition or identity system, poster, editorial '
                             'page, painting, photograph, film still, printed matter), inspect it, register it in '
                             'decision-plan.json with the decision you borrow, apply it where this content needs it, '
                             'then save again. For a supplied-only brief, set task.research to supplied_only.')
        try:
            skeleton = skeleton_report(artifact) if new_deck else {'runs': [], 'same_opener': []}
        except (KeyError, ValueError, etree.XMLSyntaxError, zipfile.BadZipFile):
            skeleton = {'runs': [], 'same_opener': []}
        palette = generic_palette(root) if new_deck else None
        try:
            upscaled = upscaled_pictures(artifact) if request.get('mode', 'create') == 'create' else []
        except (KeyError, ValueError, etree.XMLSyntaxError, zipfile.BadZipFile):
            upscaled = []
        digest = sha256(artifact)
        value = {'path': str(artifact), 'workspace': str(ws.root)}
        _declare(root, value, previous)
        return {'ok': True, 'candidate': value, 'sha256': digest, 'pages': count,
                'authored': authored, 'native_render': ws.state.get('last_render'),
                **({'fonts_used': fonts['fonts_used'],
                    'fonts_meaning': 'Font choice is open. List these families in the completion summary so recipients '
                                     'can install any they lack.'} if fonts.get('fonts_used') else {}),
                **({'font_warning': {'preview_missing': fonts['preview_missing'], 'meaning': (
                    'The preview cannot find these families and draws a fallback, so renders and reviews do not show '
                    'your type. Install the actual file (font-proxy.py host --family NAME, or an OFL download), render '
                    'and save again; or choose another family.')}} if fonts.get('preview_missing') else {}),
                **({'script_font_warning': {'families': fonts['wrong_script'], 'meaning': (
                    'Japanese text is set in a Chinese face: kanji take Chinese forms and kana look wrong. Use a '
                    'Japanese face (Yu Mincho / Yu Gothic, Hiragino Mincho ProN / Hiragino Sans, Meiryo, BIZ UD), set '
                    'run lang ja-JP, render and save again.')}} if fonts.get('wrong_script') else {}),
                **({'unit_warning': {'pages': units, 'meaning': (
                    'A unit is printed over its large number on these pages (e.g. 单 over the 3 of +23). Move the unit '
                    'right of the digits on their baseline, render the page, and save again.')}} if units else {}),
                **({'blank_warning': {'pages': blanks, 'meaning': (
                    '这些页有空白填写线（____ 或空括号）。演示稿投在屏幕上会像没做完：改成标明“示例”的具体数字或内容；'
                    '只有用户明确要打印的练习纸或讲义才保留空格。')}} if blanks else {}),
                **({'card_warning': {'pages': card_pages, 'meaning': (
                    '这些页把文字放在浅色底的矩形卡片里（浅灰绿、米色、浅蓝这类低饱和底块）。这种卡片一套里出现一两次可以，'
                    '大面积出现就是典型的 AI 味。改用版式本身分组：留白、一条细线、字号和字重的层级、对齐到同一条线；'
                    '确实需要一个面时，用照片、页面主色的整块面或明确的颜色，而不是一排浅色小卡。')}} if too_many_cards else {}),
                **({'muted_palette_warning': {'share': audit['muted_cool_share'], 'colours': audit['muted_colours'], 'meaning': (
                    '这套的主要颜色是低饱和的灰绿/灰蓝（鼠尾草绿、灰青、雾蓝一类），这是生成稿最常见的配色。除非颜色取自主题本身'
                    '（画作、产品、品牌），需要对比的地方用饱和度正常、看得清的颜色，不必全部压成灰调。')}}
                   if audit['muted_cool_share'] >= 0.5 else {}),
                **({'plain_pages_warning': {'pages': plain, 'meaning': (
                    '这些页只有白底和小字。用 deck-style.json 的 quiet_system 给每页加上第二个面、展示字或标记中的至少一样。')}}
                   if len(plain) * 4 > count or any(b == a + 1 for a, b in zip(plain, plain[1:])) else {}),
                **({'resolution_warning': {'pictures': upscaled, 'meaning': (
                    '这些图片被放大到原图分辨率的 1.5 倍以上，全屏和投影时会发糊。换一个更大的原图（博物馆和图库通常有高清版本），'
                    '或者把图缩小到不超过原图尺寸，渲染后再保存。')}} if upscaled else {}),
                **({'skeleton_warning': {'runs': skeleton['runs'], 'meaning': (
                    '这些连续页用的是同一个版式骨架（左右镜像也算）。系列页可以共用一套语言，但要在裁切、比例、位置或密度上'
                    '拉开，或者合并成一页总览、再给其中一页单独大图。至少改掉中间的页，渲染后再保存；视觉审核会把它判为必改。')}}
                   if skeleton['runs'] else {}),
                **({'opener_warning': {'pages': skeleton['same_opener'], 'meaning': (
                    '这些页的开头完全一样（同样位置的小标签加标题）。统一的页眉可以保留，但封面、章节、陈述和关键页要打破它：'
                    '标题放进画面、做成展示字、或者干脆不要标题栏。')}} if skeleton['same_opener'] else {}),
                **({'palette_warning': {'colours': palette, 'meaning': (
                    '配色是"深海军蓝/深青 + 橙色/珊瑚色"，这是生成稿最常见的组合。如果主题本身有颜色（画作、产品、地方、材料），'
                    '从图片和主题里取色重定 deck-style.json；确实来自主题就保留，并在设计说明里写明来源。')}} if palette else {}),
                **({'outside_reference_warning': {'meaning': (
                    '本套所有借鉴都来自模板库或用户附图。模板库是商业 PPT 模板，适合借结构，不适合作为工艺标准。'
                    '封面和关键页请自己再找至少一件库外的真实作品（展览视觉、海报、书刊版面、摄影、电影画面、品牌实物印刷品），'
                    '借它最与众不同的那个决定，登记后再保存。')}} if library_only and research_searches(plan) else {}),
                **({'poster_move_warning': {'pages': move_gaps, 'meaning': (
                    '封面或结尾页没有写 poster_move：这一页作为海报的那一个动作。在页面任务块里写一句能指着画面认出来的决定'
                    '（例如：整幅静物出血；深色文字面用 S 形曲边与图表相接；22.8% 与柱顶共用同一亮绿）。'
                    '视觉审核会按这句话核对画面。')}} if move_gaps else {}),
                'meaning': 'Complete exported candidate declared. Independent review and host delivery checks remain required.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', default='.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--output', required=True, help='Fresh task-local PPTX; native export preserves existing versions')
    parser.add_argument('--allow-legacy', action='store_true', help='Only for an explicitly historically admitted contract')
    args = parser.parse_args()
    try:
        result = save_candidate(args.task_root, args.workspace, args.output, allow_legacy=args.allow_legacy)
    except (OSError, ValueError, KeyError, PptxError, zipfile.BadZipFile) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
