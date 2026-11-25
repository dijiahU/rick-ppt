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
        fonts = unshipped_fonts(artifact) if request.get('mode', 'create') == 'create' else {}
        units = unit_collisions(artifact) if request.get('mode', 'create') == 'create' else []
        blanks = blank_fields(artifact) if request.get('mode', 'create') == 'create' else []
        audit = surfaces(artifact) if request.get('mode', 'create') == 'create' else surfaces(None)
        card_pages = sorted(audit['card_pages'])
        too_many_cards = len(card_pages) > max(2, count // 8) or any(v >= 3 for v in audit['card_pages'].values())
        move_gaps = poster_move_gaps(root, count) if request.get('mode', 'create') == 'create' else []
        digest = sha256(artifact)
        value = {'path': str(artifact), 'workspace': str(ws.root)}
        _declare(root, value, previous)
        return {'ok': True, 'candidate': value, 'sha256': digest, 'pages': count,
                'authored': authored, 'native_render': ws.state.get('last_render'),
                **({'font_warning': {'fonts': fonts, 'meaning': (
                    'These fonts do not ship with Windows/Office for Mac: recipients and the renderer see a fallback face '
                    '(heavy titles turn regular). Unless the user asked for them, switch to an approved font of the same '
                    'weight (fonts.md: 微软雅黑/等线 bold for heavy CJK titles, SimSun/KaiTi, Arial/Georgia) and save again.')}}
                   if fonts else {}),
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
