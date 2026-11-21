"""Search a local library of slides (tools/build-reference-library.py for images,
tools/build-template-library.py for editable PPTX templates).

search/deck/browse: a numbered contact sheet for the author to look at. pick: copy chosen
slide images into references/library/ for registration and design critique. template:
copy a template's editable .pptx into references/templates/ to use as an editing base or
to take slides, masters and devices from.
"""
import base64
import io
import json
import re
import shutil
import time
from pathlib import Path

from PIL import Image, ImageDraw

TOOL = 'pptx_reference_library'
# Chinese and common English words mapped to the tag vocabulary (page types and layout words).
SYNONYMS = {
    '封面': 'cover', '首页': 'cover', '团队': 'team founders', '成员': 'team', '创始人': 'founders team',
    '投资人': 'investors backers', '市场': 'market', '市场规模': 'market size tam sam som', '竞品': 'competition comparison',
    '竞争': 'competition', '对比': 'comparison', '增长': 'traction growth', '数据': 'traction chart numbers',
    '大数字': 'big number', '图表': 'chart', '商业模式': 'business model', '定价': 'pricing', '收入': 'revenue',
    '路线图': 'roadmap timeline', '规划': 'roadmap', '时间线': 'timeline', '里程碑': 'milestones', '问题': 'problem',
    '痛点': 'problem pain', '方案': 'solution', '解决': 'solution', '产品': 'product', '截图': 'screenshot',
    '流程': 'how_it_works process steps', '原理': 'how_it_works', '客户': 'testimonial customers', '评价': 'testimonial quote',
    '融资': 'ask funding', '结尾': 'closing', '谢谢': 'closing thanks', '章节': 'section', '目录': 'section',
    'competitors': 'competition', 'pricing': 'business_model pricing', 'timeline': 'roadmap timeline', 'founders': 'team',
    '过渡': 'section', '过渡页': 'section', '目录页': 'agenda', '目录': 'agenda section', '封底': 'closing', '感谢': 'closing thanks',
    '计划': 'plan roadmap timeline', '总结': 'summary', '图片': 'image photo', '图文': 'image text', '照片': 'photo image',
    '文字': 'text', '正文': 'text', '列表': 'list', '要点': 'list points', '步骤': 'process steps', '架构': 'diagram structure',
    '人物': 'team people portrait', '引用': 'quote', '名言': 'quote', '表格': 'table', '柱状图': 'chart bar', '饼图': 'chart pie',
    'kpi': 'big number traction', '指标': 'big number kpi', '大字': 'statement big type',
    # Structural page jobs for action=inspire (2026-11-21).
    '关键数字': 'data big number', '大数字': 'data big number', '数字': 'data', '百分比': 'data big number',
    '流程': 'process steps', '三步': 'process steps', '时间线': 'timeline', '时间轴': 'timeline', '里程碑': 'timeline',
    '引语': 'quote', '人物': 'team quote', '前后': 'comparison', '对比': 'comparison', '图文': 'image',
    '叠压': 'image', '满版': 'image cover', '章节': 'section', '结尾': 'closing', '收尾': 'closing',
}
PAGE_TYPES = ('cover', 'agenda', 'section', 'statement', 'data', 'comparison', 'process', 'timeline', 'image',
              'text', 'team', 'quote', 'summary', 'closing', 'problem', 'solution', 'product', 'how_it_works', 'market',
              'traction', 'business_model', 'competition', 'testimonial', 'roadmap', 'ask', 'other')
TEMPLATE_ROLES = {'cover': ('cover',), 'section': ('agenda', 'section'),
                  'body': ('text', 'image', 'statement', 'team', 'quote'), 'data': ('data', 'comparison'),
                  'process': ('process', 'timeline'), 'closing': ('closing', 'summary')}
TEMPLATE_ROLE_BY_TYPE = {kind: role for role, kinds in TEMPLATE_ROLES.items() for kind in kinds}
TEXT_KEYS = ('page_type', 'layout', 'description', 'strength', 'deck', 'category', 'keywords')
ROOT = Path.home() / '.rick-ppt' / 'reference-library'
CJK = re.compile(r'[\u3400-\u9fff]+')


def tokens(text):
    """Latin words plus Chinese character bigrams, so Chinese queries match Chinese tags."""
    text = (text or '').lower()
    out = set(re.findall(r'[a-z0-9_]+', text))
    for run in CJK.findall(text):
        out.update(run[i:i + 2] for i in range(len(run) - 1)) if len(run) > 1 else out.add(run)
    return out
COLS, THUMB = 6, (300, 169)


def root(cfg):
    return Path(cfg.get('reference_library_root') or ROOT)


def collections(cfg):
    base = root(cfg)
    return sorted(p.name for p in base.iterdir() if (p / 'index.json').is_file()) if base.is_dir() else []


def enabled(cfg):
    return cfg.get('reference_library', True) is not False and bool(collections(cfg))


class ReferenceLibrary:
    def __init__(self, cfg, job, *, trajectory=None):
        self.cfg = cfg; self.job = Path(job); self.trajectory = trajectory
        self.indexes = {name: json.loads((root(cfg) / name / 'index.json').read_text()) for name in collections(cfg)}

    def specs(self):
        names = ', '.join(f'{n} ({i["count"]} slides' + (f', {len(i["templates"])} editable templates' if i.get('templates') else '') + ')'
                          for n, i in self.indexes.items())
        categories = sorted({t['category'] for i in self.indexes.values() for t in i.get('templates', [])})
        return [{'type': 'function', 'name': TOOL, 'description': (
            'Local library of well-designed slides and editable PPTX templates: ' + names + '. '
            + (('Template categories: ' + '、'.join(categories) + '. ') if categories else '') +
            'Search it while planning every deck, before choosing a direction. Prefer building on a template '
            '(action=template): it is faster than starting blank, and its masters, type and base pages can carry a deck even '
            'when its colours or pictures need replacing; pages from other templates can lend layouts, devices and type systems. '
            "Use the deck's own content and the palette the direction needs; never keep sample text or stock photos. "
            'action=inspire is the inspiration mode for one page: describe the page\'s structural job, not its topic '
            '(e.g. "一个关键数字加两条说明", "三步流程", "人物照片加引语", "封面 品牌主视觉 大图"); it returns well-rated pages '
            '(3-rated only when they match closely) from any genre, one per template, each with what is worth borrowing '
            'and its match share; a note says when the library has little for the job. Pick one and study its composition '
            '(pptx_study_reference) before sketching. Use it for the cover and key pages; '
            'action=templates ranks whole templates by query fit and coverage of six page roles, one row per template '
            '(cover, two matching roles and closing when available): start here to judge a template as a possible base; '
            'action=search finds slides by meaning (Chinese or English query such as "工作汇报 数据页", "目录", "图文 杂志", '
            '"big number", "timeline"; optional category, page_type, surface light/dark/colour, min_quality) and returns a '
            'numbered contact sheet; action=deck shows every page of one template/deck (name from a result) to judge its '
            'whole system; action=browse pages through slides; action=pick copies chosen slide images into '
            'references/library/ for registration; action=template copies a template\'s editable .pptx into '
            'references/templates/ (by template id or name) to unpack as the editing base or to take slides, masters, '
            'shapes and colour/type settings from.'),
            'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['action'], 'properties': {
                'action': {'type': 'string', 'enum': ['inspire', 'templates', 'search', 'deck', 'browse', 'pick', 'template']},
                'query': {'type': 'string', 'maxLength': 200},
                'page_type': {'type': 'string', 'enum': list(PAGE_TYPES)},
                'category': {'type': 'string', 'maxLength': 40},
                'deck': {'type': 'string', 'maxLength': 120},
                'template': {'type': 'string', 'maxLength': 120, 'description': 'Template id (e.g. t1a2b3c4d) or name for action=template.'},
                'min_quality': {'type': 'number', 'minimum': 1, 'maximum': 5,
                                'description': 'Minimum role coverage for templates, minimum page quality for search and inspire.'},
                'collection': {'type': 'string', 'enum': list(self.indexes)},
                'tone': {'type': 'string', 'enum': ['light', 'dark', 'mid']},
                'surface': {'type': 'string', 'enum': ['light', 'dark', 'colour'], 'description': 'Background as seen: white/light, dark, or a saturated colour.'},
                'offset': {'type': 'integer', 'minimum': 0},
                'count': {'type': 'integer', 'minimum': 6, 'maximum': 30},
                'ids': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 8}}}}]

    @staticmethod
    def reply(ok, value, image=None):
        items = [{'type': 'inputText', 'text': json.dumps(value, ensure_ascii=False)}]
        if image:
            items.append({'type': 'inputImage', 'imageUrl': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()})
        return {'success': ok, 'contentItems': items}

    def _items(self, collection=None, tone=None):
        for name, index in self.indexes.items():
            if collection and name != collection:
                continue
            for item in index['pages']:
                if tone is None or item['tone'] == tone:
                    yield name, item

    def _log(self, args, result):
        """One line per call in a cross-task log (and the task trajectory) to judge search quality later."""
        try:
            title = json.loads((self.job / 'request.json').read_text()).get('title')
        except (OSError, ValueError):
            title = None
        row = {'at': round(time.time()), 'task': self.job.name, 'title': title,
               **{k: v for k, v in args.items() if v not in (None, '', [])}, **result}
        try:
            from trajectory import record
            record(self.trajectory, 'emit', 'reference_library.call', row)
        except Exception:
            pass
        try:
            log = Path(self.cfg.get('reference_library_log') or root(self.cfg) / 'search-log.jsonl')
            with open(log, 'a', encoding='utf-8') as out:
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
        except OSError:
            pass

    def handle(self, params):
        args = params.get('arguments') or {}
        reply = self._handle(args)
        try:
            value = json.loads(reply['contentItems'][0]['text'])
        except (KeyError, IndexError, ValueError):
            value = {}
        try:
            slides, files = value.get('slides'), value.get('files')
            ranked = value.get('templates') or value.get('pages')
            if isinstance(slides, list):
                shown = [x['id'] for x in slides][:30]
            elif isinstance(ranked, list):  # templates / inspire: what was recalled, to audit recall later
                shown = [x.get('template') if 'shown_pages' in x else x.get('id') for x in ranked][:30]
            else:
                shown = None
            self._log(args, {'success': reply.get('success'), 'available': value.get('available'),
                             'note': (value.get('note') or '')[:80] or None,
                             'shown': shown,
                             'copied': value.get('file') or ([f['file'] for f in files] if isinstance(files, list) else None)})
        except Exception:
            pass  # logging never affects the tool result
        return reply

    def _handle(self, args):
        if args.get('action') == 'pick':
            return self.pick(args)
        if args.get('action') == 'template':
            return self.template(args)
        if args.get('action') == 'templates':
            return self.templates(args)
        if args.get('action') == 'inspire':
            return self.inspire(args)
        items = list(self._items(args.get('collection'), args.get('tone')))
        if args.get('category'):
            items = [(n, it) for n, it in items if args['category'] in (it.get('category') or '')]
        if args.get('action') == 'deck':
            name = (args.get('deck') or '').strip().lower()
            items = [(n, it) for n, it in items if name and name in ((it.get('deck') or '').lower(), (it.get('template') or '').lower())]
            items.sort(key=lambda row: row[1].get('slide') or 0)
        elif args.get('action') == 'search':
            items = self._search(items, args)
            if items is None:
                return self.reply(False, {'status': 'no_results', 'hint': 'Use page words such as 封面, 目录, 数据, 图文, '
                                          'timeline, team, big number, or a template category.'})
        offset, count = args.get('offset', 0), args.get('count', 24)
        chosen = items[offset:offset + count]
        if not chosen:
            return self.reply(False, {'status': 'no_results', 'available': len(items)})
        rows = (len(chosen) + COLS - 1) // COLS
        sheet = Image.new('RGB', (COLS * THUMB[0], rows * (THUMB[1] + 18)), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, (name, item) in enumerate(chosen):
            with Image.open(root(self.cfg) / name / item['file']) as im:
                im = im.convert('RGB'); im.thumbnail(THUMB)
                sheet.paste(im, ((i % COLS) * THUMB[0], (i // COLS) * (THUMB[1] + 18)))
            draw.text(((i % COLS) * THUMB[0] + 4, (i // COLS) * (THUMB[1] + 18) + THUMB[1] + 2),
                      item['id'], fill=(200, 0, 0))
        buffer = io.BytesIO(); sheet.save(buffer, 'JPEG', quality=80)
        return self.reply(True, {'status': 'results', 'shown': len(chosen), 'available': len(items),
                                 'next_offset': offset + len(chosen) if offset + len(chosen) < len(items) else None,
                                 'slides': [{k: v for k, v in {'id': it['id'], 'collection': n, 'tone': it['tone'],
                                             'deck': it.get('deck'), 'template': it.get('template'), 'category': it.get('category'),
                                             'slide': it.get('slide'), 'page_type': it.get('page_type'), 'layout': it.get('layout'),
                                             'description': it.get('description'), 'quality': it.get('quality')}.items() if v}
                                            for n, it in chosen],
                                 'next': 'pick the slides whose relationships you want to learn from'}, buffer.getvalue())

    @staticmethod
    def _search(items, args, *, diversify=True):
        """Rank by rarity-weighted word matches (IDF), optionally diversifying the results."""
        import math
        query = (args.get('query') or '').lower()
        expanded = query + ' ' + ' '.join(v for k, v in SYNONYMS.items() if k in query)
        words = tokens(expanded)
        if query.strip() and not words:
            return None  # nothing recognisable
        implied = {w for w in words if w in PAGE_TYPES} | ({'business_model'} if {'business', 'model'} <= words else set())
        page_type, min_quality = args.get('page_type'), args.get('min_quality') or 2
        surface = args.get('surface')
        texts = [(name, item, tokens(' '.join(str(item.get(k) or '') for k in TEXT_KEYS))) for name, item in items]
        df = {w: sum(w in t for _, _, t in texts) for w in words}
        weight = {w: math.log((len(texts) + 1) / (df[w] + 1)) + 0.1 for w in words}
        scored = []
        for name, item, text in texts:
            if page_type and item.get('page_type') != page_type:
                continue
            if (item.get('quality') or 3) < min_quality:
                continue
            if surface and item.get('surface', item.get('tone')) != surface:
                continue
            score = sum(weight[w] for w in words & text) if words else 0
            if words and not score:
                continue
            if item.get('page_type') in implied:
                score += max(weight.values())  # a named page type counts like one strong word
            scored.append((round(score, 3), item.get('quality') or 3, name, item))
        scored.sort(key=lambda row: (-row[0], -row[1], row[3]['id']))
        if not diversify:
            return [(name, item) for _, _, name, item in scored]
        first, rest, per_deck, seen = [], [], {}, set()
        for _, _, name, item in scored:
            key = (item.get('deck'), item.get('layout'))
            if item.get('layout') and key in seen:
                continue  # an identical repeated page adds nothing
            seen.add(key)
            deck = item.get('deck')
            per_deck[deck] = per_deck.get(deck, 0) + 1
            (first if per_deck[deck] <= 2 else rest).append((name, item))
        return first + rest

    def pick(self, args):
        wanted = set(args.get('ids') or [])
        found = [(n, it) for n, it in self._items(args.get('collection')) if it['id'] in wanted]
        if not found:
            return self.reply(False, {'status': 'unknown_ids', 'ids': sorted(wanted)})
        folder = self.job / 'references' / 'library'
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for name, item in found:
            target = folder / f'{name}-{item["id"]}.jpg'
            shutil.copyfile(root(self.cfg) / name / item['file'], target)
            files.append({'file': str(target.relative_to(self.job)), 'collection': name,
                          'source': self.indexes[name]['source'], 'license': self.indexes[name]['license'],
                          'tone': item['tone'], 'colors': item['colors']})
        return self.reply(True, {'status': 'copied', 'files': files,
                                 'meaning': 'Register them as local_image references; they are inspiration, not assets for the deck.'})

    def template(self, args):
        wanted = (args.get('template') or args.get('deck') or '').strip().lower()
        for name, index in self.indexes.items():
            for t in index.get('templates', []):
                if wanted and wanted in (t['id'].lower(), t['name'].lower()):
                    folder = self.job / 'references' / 'templates'
                    folder.mkdir(parents=True, exist_ok=True)
                    safe = re.sub(r'[\\/:*?"<>|\s]+', '_', t['name'])[:60]
                    target = folder / f'{t["id"]}-{safe}.pptx'
                    shutil.copyfile(root(self.cfg) / name / t['file'], target)
                    fonts = None
                    if self.cfg.get('template_font_map', True):
                        # WPS cloud fonts fall back to a regular face in the renderer and on recipients'
                        # machines; map them to approved fonts with the same weight (2026-11-21).
                        from template_fonts import map_pptx
                        try:
                            fonts = map_pptx(target)
                        except Exception as error:  # never block the copy; report it instead
                            fonts = {'error': type(error).__name__}
                    pages = [{'id': it['id'], 'slide': it.get('slide'), 'page_type': it.get('page_type'), 'layout': it.get('layout')}
                             for it in index['pages'] if it.get('template') == t['id']]
                    return self.reply(True, {
                        'status': 'copied', 'file': str(target.relative_to(self.job)), 'template': t['id'], 'name': t['name'],
                        'category': t['category'], 'slides': t['slides'], 'slide_size_in': t.get('size'), 'pages': pages,
                        'source': index.get('source'), 'license': index.get('license'),
                        **({'fonts': {**fonts, 'meaning': (
                            'The template\'s cloud fonts were replaced in this copy by approved fonts with the same weight '
                            '(heavy/bold titles stay bold), because recipients and the renderer do not have them. Keep these '
                            'mapped fonts; install the listed ids once with font-proxy.py before rendering.')}}
                           if fonts and fonts.get('mapped') else {}),
                        'meaning': ('An editable source deck from the local template library, not user-supplied material. '
                                    'To build on it, unpack this file as your template instead of blank.pptx, keep the masters, '
                                    'theme and devices you chose, delete unused slides and replace every sample text and stock '
                                    'picture; record the kept elements in template_preservation. To borrow from it, open or '
                                    'unpack it and recreate or copy the chosen slide/elements natively. Register it as a '
                                    'design_work reference (source = this file, evidence = a picked slide image).')})
        return self.reply(False, {'status': 'unknown_template', 'template': wanted,
                                  'hint': 'Use the template id or exact name shown by search/deck results.'})

    def _font_note(self, name, t):
        if not self.cfg.get('template_font_map', True):
            return None
        try:
            from template_fonts import preview_note
            return preview_note(root(self.cfg) / name / t['file'])
        except Exception:
            return None

    def templates(self, args):
        """Rank whole templates by query fit and quality across page roles."""
        import statistics
        query = (args.get('query') or '').lower()
        expanded = query + ' ' + ' '.join(v for k, v in SYNONYMS.items() if k in query)
        words = tokens(expanded)
        min_quality = args.get('min_quality') or 3.4
        category = args.get('category')
        reports = ('周报月报', '工作汇报')
        categories = reports if category in reports else (category,)
        rows = []
        for name, index in self.indexes.items():
            pages = [p for p in index['pages'] if p.get('page_type') != 'other']
            for t in index.get('templates', []):
                if category and not any(c in t['category'] for c in categories):
                    continue
                own = sorted((p for p in pages if p.get('template') == t['id']), key=lambda p: -(p.get('quality') or 3))
                best = {}
                for p in own:
                    role = TEMPLATE_ROLE_BY_TYPE.get(p.get('page_type'))
                    if role:
                        best.setdefault(role, p)
                cover = best.get('cover')
                if not cover or (cover.get('quality') or 3) < 3:
                    continue
                missing = [role for role in TEMPLATE_ROLES if role not in best]
                coverage = (sum(p.get('quality') or 3 for p in best.values()) + 2 * len(missing)) / len(TEMPLATE_ROLES)
                if coverage < min_quality:
                    continue
                page_words = {p['id']: tokens(' '.join(str(p.get(k) or '') for k in TEXT_KEYS)) for p in own}
                text = tokens(t['name'] + ' ' + t['category']).union(*page_words.values())
                fit = len(words & text) / len(words) if words else 1.0
                if words and not fit:
                    continue
                shown, seen = [cover], {'cover', 'closing'}
                for p in sorted(own, key=lambda p: -len(words & page_words[p['id']])):
                    role = TEMPLATE_ROLE_BY_TYPE.get(p.get('page_type'))
                    if role and role not in seen:
                        shown.append(p); seen.add(role)
                        if len(shown) == 3:
                            break
                if 'closing' in best:
                    shown.append(best['closing'])
                average = statistics.mean(p.get('quality') or 3 for p in own)
                score = 0.55 * fit + 0.45 * (coverage - 1) / 4
                rows.append((score, name, t, round(fit, 2), round(coverage, 2), round(average, 2), missing, shown))
        rows.sort(key=lambda r: -r[0])
        rows = rows[:args.get('count') or 6]
        if not rows and category:
            widened = self.templates({**args, 'category': None})
            if widened.get('success'):
                value = json.loads(widened['contentItems'][0]['text'])
                value['note'] = (f"No {category} template matched with coverage at least {min_quality} and a cover rated 3 or higher; "
                                 'these are the best related templates from other categories. Borrow structure from them, or use action=inspire for page ideas.')
                widened['contentItems'][0]['text'] = json.dumps(value, ensure_ascii=False)
                return widened
        if not rows:
            return self.reply(False, {'status': 'no_results', 'hint': 'Try fewer words, or use action=inspire with the page\'s structural job.'})
        width, height = 300, 169
        sheet = Image.new('RGB', (4 * width, len(rows) * (height + 20)), 'white')
        draw = ImageDraw.Draw(sheet)
        for r, (_, name, t, _, coverage, _, _, shown) in enumerate(rows):
            for c, item in enumerate(shown):
                with Image.open(root(self.cfg) / name / item['file']) as im:
                    im = im.convert('RGB'); im.thumbnail((width, height))
                    sheet.paste(im, (c * width, r * (height + 20)))
            draw.text((4, r * (height + 20) + height + 3), f"{t['id']}  C{coverage:.2f}", fill=(200, 0, 0))
        buffer = io.BytesIO(); sheet.save(buffer, 'JPEG', quality=80)
        return self.reply(True, {'status': 'results', 'templates': [
            {k: v for k, v in {'template': t['id'], 'name': t['name'], 'category': t['category'], 'average_quality': average,
             'coverage': coverage, 'roles_missing': missing, 'fit': fit, 'slides': t.get('visible_slides'),
             'shown_pages': [{'id': p['id'], 'page_type': p['page_type']} for p in shown],
             'font_note': self._font_note(name, t)}.items() if v is not None}
            for _, name, t, fit, coverage, average, missing, shown in rows],
            'next': 'Open the best one with action=deck (all pages), then action=template to build on it, replacing colours, pictures and sample content as needed.'},
            buffer.getvalue())

    def inspire(self, args):
        """Cross-genre best pages for a page's structural job, one per template, with the borrowable move and match share."""
        import math
        items = list(self._items(args.get('collection')))
        query = (args.get('query') or '').lower()
        words = tokens(query + ' ' + ' '.join(v for k, v in SYNONYMS.items() if k in query))
        texts = {item['id']: tokens(' '.join(str(item.get(k) or '') for k in TEXT_KEYS)) for _, item in items}
        df = {w: sum(w in t for t in texts.values()) for w in words}
        # Fragments the library never uses (越页, 的地) cannot be matched, so they do not count against a page.
        weight = {w: math.log((len(texts) + 1) / (df[w] + 1)) for w in words if df[w]}
        total = sum(weight.values()) or 1

        def coverage(item):  # share of the query's rarity-weighted words this page actually mentions
            return sum(weight[w] for w in weight.keys() & texts[item['id']]) / total

        # Pages rated 3 compete too, with a penalty, so a rare exact match (a map) beats a vague 4-rated one
        # (2026-11-21: a map query returned only big-title pages because every map page is rated 3).
        floor = args.get('min_quality') or 3
        count = args.get('count') or 8
        ranked = sorted(self._search(items, {**args, 'min_quality': floor}, diversify=False) or [],
                        key=lambda row: -(coverage(row[1]) + 0.04 * ((row[1].get('quality') or 3) - 4)))
        chosen, seen = [], set()
        for name, item in ranked:
            key = item.get('template') or (name, item.get('deck') or item['id'])
            if key in seen or ((item.get('quality') or 3) < 4 and coverage(item) < 0.3):
                continue
            seen.add(key); chosen.append((name, item))
            if len(chosen) >= count:
                break
        best = max((coverage(it) for _, it in chosen), default=0)
        note = None
        if chosen and words and best < 0.3:
            note = ('Weak match: the library has little for this page job. Check each page\'s matched share; borrow '
                    'only a page whose structure truly fits, otherwise design from the content.')
        if not chosen:
            return self.reply(False, {'status': 'no_results', 'hint': 'Describe the structure (大数字, 图文叠压, 三步流程, 引语, 封面大图) rather than the topic.'})
        # Three per row at 480 px (was four at 360): a composition is judged from these
        # thumbnails, and the sheet stays within the width the model sees unscaled.
        cols = 3
        rows = (len(chosen) + cols - 1) // cols
        width, height = 480, 270
        sheet = Image.new('RGB', (cols * width, rows * (height + 18)), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, (name, item) in enumerate(chosen):
            with Image.open(root(self.cfg) / name / item['file']) as im:
                im = im.convert('RGB'); im.thumbnail((width, height))
                sheet.paste(im, ((i % cols) * width, (i // cols) * (height + 18)))
            draw.text(((i % cols) * width + 4, (i // cols) * (height + 18) + height + 2), item['id'], fill=(200, 0, 0))
        buffer = io.BytesIO(); sheet.save(buffer, 'JPEG', quality=82)
        return self.reply(True, {'status': 'results', 'pages': [
            {**{k: v for k, v in {'id': it['id'], 'genre': it.get('category'), 'layout': it.get('layout'),
                                 'borrow': it.get('strength'), 'quality': it.get('quality'), 'surface': it.get('surface'),
                                 'match': round(coverage(it), 2) if words else None}.items() if v},
             'template': it.get('template'), 'slide': it.get('slide'), 'page_type': it.get('page_type')}
            for _, it in chosen],
            **({'note': note} if note else {}),
            'meaning': 'Borrow the composition (where the focus sits, how picture, colour block and type overlap, what is left empty), '
                       'never the genre, colours or content. pick the chosen id, study it, then sketch from its structure.'},
            buffer.getvalue())
