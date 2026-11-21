"""Accept deck and page plans and deliver page context through the existing multimodal tool channel.

No acquisition, selection, new model, inspection verdict or native edit happens
here. A CLI-only harness keeps its existing context + image-viewer path.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from threading import Lock

from outline import MAX_OUTLINE_BYTES
from progress import read_scoped
from trajectory import record

TOOL = 'pptx_page_design_context'
# Leave room inside the existing 8 MiB app-server frame, including text/metadata.
MAX_RESPONSE = 7 * 1024 * 1024
PLAN_FILE = 'page-plans.json'
MAX_PLAN_FILE = 2 * 1024 * 1024
DECK_PLAN_FILE = 'deck-plan.json'
MAX_SHEET_BYTES = 16 * 1024
PLAN_LOCK = Lock()
PLAN_TEXT = ('takeaway', 'relationship', 'steps', 'hero', 'cut', 'visual_idea', 'rejected')
PLAN_FIELDS = {*PLAN_TEXT, 'reading_order'}
DECK_TEXT = ('occasion', 'audience', 'feeling', 'subject')
DECK_LISTS = {
    'expectations': (2, 5, 'What this audience expects to see, at least six characters per item; include people for social occasions.'),
    'wrong_looks': (1, 4, 'Looks that would feel wrong for this audience and occasion.'),
    'references': (0, 3, 'Titles or URLs of excellent examples you have seen for this occasion.'),
}
DECK_PLAN_MISSING = '先用 action=deck_plan 提交整套场合与观众单'
FEELING_STYLE = re.compile(
    r'高级|简洁|简约|克制|专业|现代|极简|低调|商务|大气|时尚|精致|干净|沉稳|典雅|优雅|华丽|留白|编辑设计|'
    r'整体|风格|感觉|感|气质|并且|以及|而且|且|与|和|的|很|非常|有|'
    r'\b(?:premium|sleek|clean|simple|minimal(?:ist)?|restrained|professional|modern|elegant|and|or|very)\b', re.I)
SOCIAL_OCCASION = re.compile(r'婚|寿|生日|年会|庆|招新|迎新|晚会|派对|节日|团建|颁奖')
SOCIAL_FEELING = re.compile(r'克制|冷静|极简|低调')
# Festive occasions need the celebration itself, not only warmth (2026-11-22: a wedding plan
# with 温暖、亲切、会心 passed and the deck came out as a muted nostalgic film).
FESTIVE_OCCASION = re.compile(r'婚|寿|生日|年会|庆|晚会|派对|节日|颁奖|典礼')
FESTIVE_FEELING = re.compile(r'喜庆|欢乐|喜悦|热闹|庆祝|欢庆|欢快|开心|快乐|幸福|甜蜜|祝福|喜气|celebrat|joy|festive|happy', re.I)
PEOPLE = re.compile(r'人|成员|社员|队员|同学|大家|团队|合影|群像|新郎|新娘|亲友|朋友|宾客|嘉宾|师生|学生|员工|观众')
PLAN_MISSING = '这页是封面、收尾或关键页，先提交 page_plan，再判断渲染是否达到设计单，不合格就按设计单重做'
PLAN_CHECK = ('对照这张图检查三件事——主角是否就是 hero、视线是否按 reading_order 走、visual_idea 是否真的做出来了；'
              '没有做到就改，不要改写设计单去迁就现状。')
GENERIC_STYLE = re.compile(
    r'简洁|简约|高级|留白|对比|对照|大字|低饱和|高饱和|静物|风格|突出|主角|重点|形成|采用|使用|呈现|大标题|标题|文字|画面'
    r'|背景|视觉|内容|信息|这页|页面|本页|通过|元素|大面积|大图|质感|营造出|营造|布局|层次|排版|配色'
    r'|搭配|强烈|衬托|极简|干净|克制|清晰|柔和|现代|精致|醒目|图片|图像'
    r'|\b(?:a|an|the|of|is|it|its|be|in|on|with|to|and|or|for|from|this|that|by|as|at|use|using|show|page|'
    r'slide|title|text|style|visual|contrast|minimal|minimalist|simple|clean|premium|elegant|white|whitespace|space|'
    r'large|big|bold|low|high|muted|saturated|saturation|background|layout|element|data|content|focus|about|percent)\b', re.I)
REJECTION_SPLIT = re.compile(
    r'[：:，,。；;]|因为|因此|导致|会(?=让|使|把|遮|掩|混|分散)|\b(?:because|since|so|making|which|would|but)\b', re.I)
READING_COST = re.compile(
    r'难|乱|散|挤|淹没|掩盖|遮|抢|混|显眼|注意|视线|顺序|读|看|观众|误|分辨|找|一样|反复|'
    r'\b(?:hard|difficult|confus\w*|hid\w*|obscur\w*|crowd\w*|distract\w*|unclear|'
    r'compete\w*|bur\w*|order|read\w*|scan\w*|find|mislead\w*)\b', re.I)


def outline_pages(job):
    try:
        outline = json.loads(read_scoped(job, 'outline.json', MAX_OUTLINE_BYTES))
    except (OSError, ValueError):
        return []
    pages = outline.get('slides') if isinstance(outline, dict) else None
    return pages if isinstance(pages, list) and all(isinstance(p, dict) and isinstance(p.get('id'), str)
                                                    for p in pages) else []


def read_page_plans(job):
    try:
        plans = json.loads(read_scoped(job, PLAN_FILE, MAX_PLAN_FILE))
    except FileNotFoundError:
        return {}
    if not isinstance(plans, dict) or any(not isinstance(plan, dict) for plan in plans.values()):
        raise ValueError('Invalid page-plans.json')
    return plans


def read_deck_plan(job):
    try:
        plan = json.loads(read_scoped(job, DECK_PLAN_FILE, MAX_SHEET_BYTES))
    except FileNotFoundError:
        return {}
    if not isinstance(plan, dict):
        raise ValueError('Invalid deck-plan.json')
    return plan


def write_plan_file(job, filename, data):
    stream = tempfile.NamedTemporaryFile(dir=job, prefix='.' + Path(filename).stem + '-', delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(data)
        temporary.replace(job / filename)
    finally:
        temporary.unlink(missing_ok=True)


def deck_plan_issues(plan):
    issues = []
    for field in ('occasion', 'audience', 'subject'):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            issues.append(field + ' 必须是非空文字。')
    feeling = plan.get('feeling')
    if not isinstance(feeling, str) or not any(ch.isalpha() for ch in FEELING_STYLE.sub('', feeling)):
        issues.append('feeling 至少要有一个具体的情绪或气氛词，不能只有风格词。')
    for field, (minimum, maximum, _) in DECK_LISTS.items():
        values = plan.get(field, [] if field == 'references' else None)
        if not isinstance(values, list) or not minimum <= len(values) <= maximum:
            issues.append(f'{field} 必须是包含 {minimum}–{maximum} 条的数组。')
        if isinstance(values, list):
            size = 6 if field == 'expectations' else 1
            for n, value in enumerate(values, 1):
                if not isinstance(value, str) or sum(ch.isalnum() for ch in value) < size:
                    issues.append(f'{field} 第 {n} 条必须是至少 {size} 个字的文字。')
    if any(isinstance(plan.get(field), str) and SOCIAL_OCCASION.search(plan[field])
           for field in ('occasion', 'audience', 'feeling')):
        expectations = plan.get('expectations')
        if ((isinstance(feeling, str) and SOCIAL_FEELING.search(feeling))
                or not (isinstance(expectations, list) and any(
                    isinstance(value, str) and PEOPLE.search(re.sub(r'无人|人工|机器人', '', value))
                    for value in expectations))):
            issues.append('这是庆典或社交场合，观众期待热闹和看到人')
        if (any(isinstance(plan.get(field), str) and FESTIVE_OCCASION.search(plan[field]) for field in ('occasion', 'audience'))
                and not (isinstance(feeling, str) and FESTIVE_FEELING.search(feeling))):
            issues.append('这是庆典场合：feeling 里要写出庆祝类情绪（喜庆、欢乐、喜悦、热闹、幸福等），温馨可以和它们并存。')
    return issues


def content_words(value):
    words = set()
    for token in re.findall(r'[\u3400-\u9fff]+|[a-z]+|\d+(?:[.,]\d+)*',
                            GENERIC_STYLE.sub(' ', value.casefold())):
        if '\u3400' <= token[0] <= '\u9fff':
            words.update(token[i:i + 2] for i in range(len(token) - 1))
        elif len(token) > 1 or token.isdecimal():
            words.add(token)
    return words


def plan_issues(plan):
    issues = []
    kind = plan.get('kind')
    if kind not in ('key', 'ordinary'):
        issues.append('kind 必须是 key 或 ordinary。')
    required = PLAN_TEXT if kind == 'key' else ('takeaway', 'relationship')
    for field in required:
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            issues.append(field + ' 必须是非空文字。')
    order = plan.get('reading_order')
    if not isinstance(order, list) or not 1 <= len(order) <= 3 or any(
            not isinstance(phrase, str) or not phrase.strip() for phrase in order):
        issues.append('reading_order 必须包含 1–3 个非空短语。')
    if kind == 'key':
        hero, idea, rejected = (plan[field].strip() if isinstance(plan.get(field), str) else ''
                                for field in ('hero', 'visual_idea', 'rejected'))
        takeaway = plan.get('takeaway') if isinstance(plan.get('takeaway'), str) else ''
        if hero and not re.search(r'[\d%％占约]', hero):
            issues.append('hero 须说明主角所占面积或比例。')
        if idea and (sum(ch.isalnum() for ch in idea) < 12
                     or not (content_words(idea) & content_words(' '.join(
                         str(plan.get(k) or '') for k in ('takeaway', 'hero', 'relationship', 'steps'))))):
            issues.append('visual_idea 至少 12 个字，且须落到本页内容：用上 takeaway、hero、relationship 或 steps 里的具体词或数字，不能只写风格。')
        if rejected:
            option = re.search(r'[^\W_]', rejected)
            separator = REJECTION_SPLIT.search(rejected, option.end()) if option else None
            if (sum(ch.isalnum() for ch in rejected) < 8 or not separator
                    or not READING_COST.search(rejected, separator.end())):
                issues.append('rejected 至少 8 个字，须写明备选方案以及它为什么更难读。')
    return issues


class PageDesignInputs:
    def __init__(self, cfg, job, trajectory=None):
        self.cfg, self.job, self.trajectory = cfg, Path(job).resolve(strict=True), trajectory
        self.script = Path(cfg['plugin']) / 'skills/pptx/scripts/page_design.py'
        self.delivered = {}  # Only successful writes; scoped to the actual thread.
        self.previews = {}  # Last successfully supplied page version, not a review.

    def specs(self):
        if not self.script.is_file() or self.cfg.get('_harness_transport') == 'dsh-sdk':
            return []
        return [{'type': 'function', 'name': TOOL,
                 'description': "Submit the deck's occasion and audience sheet with action=deck_plan before submitting any key page_plan. Read a stable page ID's evidence, materials and applicable design references with actual supported images, or submit its design sheet with action=page_plan. Before composition use its actual materials; after rendering pass workspace to receive this page's current rendered preview first. After a design change render that page again and inspect the new preview. Stale/missing previews stay unattached. Image delivery is not proof of understanding or design quality. No search, rendering or native changes happen in this tool.",
                 'inputSchema': {'type': 'object', 'properties': {
                                  'page_id': {'type': 'string', 'description': 'Required for context and page_plan. Omit for deck_plan.'},
                                  'action': {'type': 'string', 'enum': ['context', 'deck_plan', 'page_plan'],
                                             'description': 'Default context. For deck_plan provide occasion, audience, feeling, expectations, subject and wrong_looks, with optional references. Submit page_plan before building the cover, key pages and closing page. Key plans require all eight fields. Ordinary plans require takeaway, relationship and reading_order.'},
                                  'occasion': {'type': 'string', 'description': 'Deck occasion and how the slides will be shown.'},
                                  'audience': {'type': 'string', 'description': 'Who is watching and their relationship to the speaker.'},
                                  'feeling': {'type': 'string', 'description': 'Two to four words for how the audience should feel. Social occasions cannot use 克制、冷静、极简 or 低调.'},
                                  'subject': {'type': 'string', 'description': 'The people or real subject at the centre of this deck.'},
                                  **{field: {'type': 'array', 'minItems': minimum, 'maxItems': maximum,
                                             'items': {'type': 'string'}, 'description': description}
                                     for field, (minimum, maximum, description) in DECK_LISTS.items()},
                                  'kind': {'type': 'string', 'enum': ['key', 'ordinary'],
                                           'description': 'Required for page_plan. On a context call, key flags a page that needs a key plan.'},
                                  'reading_order': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'type': 'string'}},
                                  **{field: {'type': 'string'} for field in PLAN_TEXT},
                                  'hero': {'type': 'string', 'description': 'Name the focal element and how much of the page it occupies.'},
                                  'visual_idea': {'type': 'string', 'description': 'Describe the visible idea in at least 12 characters and name a concrete word or number from takeaway or hero.'},
                                  'rejected': {'type': 'string', 'description': 'In at least 8 characters, name an alternative and why it makes the page harder to read.'},
                                  'workspace': {'type': 'string', 'description': 'Existing task-local native parts/session directory. Supplies actual current-page object IDs/text/transforms for edits, and after render N its current preview. Large indexes explicitly defer to inspect. No automatic unpack/render.'},
                                  'repeat_images': {'type': 'boolean', 'description': 'Resupply when an earlier image is no longer available in context; normally reuse the same-thread delivery receipt.'},
                                  'compare_previous': {'type': 'boolean', 'description': 'With workspace and a current render, attach the last successfully supplied preview of this same page/workspace/thread as historical comparison. No rendering or automatic verdict.'}},
                                 'additionalProperties': False}}]

    def context(self, page_id, workspace=None):
        # Match tool preparation: exact selected interpreter/plugin, bounded
        # task files, and no inherited provider credentials or PYTHONPATH.
        env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR')
               if key in os.environ}
        env['PYTHONPATH'] = str(self.script.parent)
        command = [self.cfg['python'], str(self.script), 'context',
                   '--task-root', str(self.job), '--page-id', page_id]
        if workspace is not None:
            command += ['--workspace', workspace]
        output = subprocess.run(command,
                                cwd=self.job, env=env, capture_output=True, timeout=30, check=True)
        if len(output.stdout) > 2 * 1024 * 1024:
            raise ValueError('Page context exceeds its existing task-file limit')
        return json.loads(output.stdout)

    def submit_deck_plan(self, args):
        issues = deck_plan_issues(args)
        unexpected = set(args) - {*DECK_TEXT, *DECK_LISTS, 'action'}
        if unexpected:
            issues.append('未知设计单字段：' + ', '.join(sorted(unexpected)))
        if issues:
            return self.reply(False, {'status': 'invalid', 'issues': issues})
        plan = {field: args[field].strip() for field in DECK_TEXT}
        plan.update({field: [value.strip() for value in args.get(field, [])] for field in DECK_LISTS})
        try:
            data = json.dumps(plan, ensure_ascii=False, indent=2).encode()
            if len(data) > MAX_SHEET_BYTES:
                return self.reply(False, {'status': 'invalid', 'issues': ['请将设计单精简到 16 KiB 以内。']})
            with PLAN_LOCK:
                write_plan_file(self.job, DECK_PLAN_FILE, data)
        except (OSError, ValueError):
            return self.reply(False, {'status': 'unavailable', 'error': '无法保存 deck-plan.json，已有设计单未替换。'})
        return self.reply(True, {'status': 'accepted', 'instruction': '页面设计单的主角和视觉想法都要服务于 feeling 和 expectations。'})

    def submit_plan(self, args):
        page_id = args.get('page_id')
        issues = plan_issues(args)
        try:
            deck_plan = read_deck_plan(self.job)
        except (OSError, ValueError):
            deck_plan = {}
        if args.get('kind') == 'key' and not deck_plan:
            issues.insert(0, DECK_PLAN_MISSING)
        unexpected = set(args) - (PLAN_FIELDS | {'action', 'page_id', 'kind'})
        if unexpected:
            issues.append('未知设计单字段：' + ', '.join(sorted(unexpected)))
        if (not isinstance(page_id, str) or not 1 <= len(page_id) <= 200
                or sum(page['id'] == page_id for page in outline_pages(self.job)) != 1):
            issues.append('page_id 必须对应大纲中的唯一页面。')
        if issues:
            return self.reply(False, {'status': 'invalid', 'issues': issues})
        plan = {field: args[field].strip() for field in PLAN_TEXT
                if isinstance(args.get(field), str) and args[field].strip()}
        plan.update(kind=args['kind'], reading_order=[phrase.strip() for phrase in args['reading_order']])
        try:
            if len(json.dumps(plan, ensure_ascii=False).encode()) > MAX_SHEET_BYTES:
                return self.reply(False, {'status': 'invalid', 'issues': ['请将设计单精简到 16 KiB 以内。']})
            with PLAN_LOCK:
                plans = read_page_plans(self.job)
                plans[page_id] = plan
                data = json.dumps(plans, ensure_ascii=False, indent=2).encode()
                if len(data) > MAX_PLAN_FILE:
                    raise ValueError('Page plans exceed the task-file limit')
                write_plan_file(self.job, PLAN_FILE, data)
        except (OSError, ValueError):
            return self.reply(False, {'status': 'unavailable', 'error': '无法保存 page-plans.json，已有设计单未替换。'})
        note = '阅读顺序：' + ' '.join(f'{n} {phrase}' for n, phrase in zip('①②③', plan['reading_order']))
        result = {'status': 'accepted', 'reading_order_note': note,
                  'instruction': '把 reading_order_note 原样写进该页的讲稿备注。'}
        if deck_plan:
            result['deck_plan'] = {field: deck_plan.get(field) for field in ('feeling', 'expectations')}
        return self.reply(True, result)

    def plan_context(self, args, context):
        page_id, number = args['page_id'], context.get('page_number')
        pages = outline_pages(self.job)
        outlined = next((page for page in pages if page['id'] == page_id), {})
        key = (number == 1 or (pages and pages[-1]['id'] == page_id and number == len(pages))
               or outlined.get('kind') == 'key' or args.get('kind') == 'key')
        try:
            plan = read_page_plans(self.job).get(page_id, {})
        except (OSError, ValueError):
            plan = {}
        details = {}
        if key and plan.get('kind') != 'key':
            details['plan_missing'] = PLAN_MISSING
        if plan:
            details['plan'] = {field: plan.get(field) for field in ('takeaway', 'hero', 'reading_order', 'visual_idea')}
            details['plan_check'] = PLAN_CHECK
        return {**details, **context}

    def handle(self, params):
        args = params.get('arguments')
        if (params.get('namespace') is not None or params.get('tool') != TOOL
                or not isinstance(args, dict)):
            return self.reply(False, {'error': 'Specify one existing stable outline page_id'})
        action = args.get('action', 'context')
        if action == 'deck_plan':
            return self.submit_deck_plan(args)
        if action == 'page_plan':
            return self.submit_plan(args)
        if (action != 'context' or set(args) - {'action', 'page_id', 'kind', 'workspace', 'repeat_images', 'compare_previous'}
                or not isinstance(args.get('page_id'), str) or not 1 <= len(args['page_id']) <= 200
                or ('kind' in args and args['kind'] not in ('key', 'ordinary'))
                or ('workspace' in args and (not isinstance(args['workspace'], str)
                                            or not 1 <= len(args['workspace']) <= 4096))
                or type(args.get('repeat_images', False)) is not bool
                or type(args.get('compare_previous', False)) is not bool):
            return self.reply(False, {'error': 'Specify one existing stable outline page_id'})
        try:
            context = self.context(args['page_id'], args['workspace']) if 'workspace' in args else self.context(args['page_id'])
        except (OSError, ValueError, subprocess.SubprocessError):
            return self.reply(False, {'error': 'Current page context unavailable; retain saved work and use the existing notes/image tools'})
        candidates = []
        if 'workspace' in args:
            context = self.plan_context(args, context)
            native = context.get('native', {})
            preview = native.get('preview', {})
            check = preview.get('file_check', {}) if preview.get('status') == 'current' else {
                'source': preview.get('image'),
                'availability': preview.get('status', native.get('availability', 'not_recorded'))}
            # The page being designed has priority over supporting material in
            # the bounded image response. Never deliver an old render as current.
            candidates.append(('page_preview', check))
            context['previous_preview_input'] = self.previews.get(
                (params.get('threadId'), context['page']['id'], native.get('workspace')))
            if args.get('compare_previous'):
                prior = context['previous_preview_input']
                context['comparison'] = {'status': 'no_previous_input'}
                if preview.get('status') != 'current':
                    context['comparison']['status'] = 'current_preview_unavailable'
                elif prior and prior['native']['workspace_fingerprint'] == native.get('workspace_fingerprint'):
                    context['comparison']['status'] = 'same_native_version'
                elif prior:
                    # Historical pixels are allowed only as an explicitly
                    # requested comparison, never relabelled as a current render.
                    context['comparison'] = {'status': 'previous_input_requested',
                        'previous_call_id': prior['call_id'], 'native': prior['native'],
                        'meaning': 'Historical earlier input of this page, not the current render or an aesthetic verdict.'}
                    candidates.append(('previous_page_preview', {
                        **prior['file'], 'source': prior['file']['file'],
                        'availability': 'file_present'}))
        for item in context.get('resources', []):
            # Handoff materials explicitly belong to this page. Unselected,
            # pending decision assets and search evidence are not selected images.
            if (item['role'] == 'materials' or item['role'] == 'planned_asset'
                    and item['declared'].get('status') == 'ready'):
                candidates.append((item['role'], item['file_check']))
        for entry in context.get('references', []):
            if entry.get('inspection') == 'local_image':
                candidates.append(('reference:' + str(entry.get('id')), entry['file_check']))
        images, checks, seen = [], [], {}
        # This list records transport preparation, never inspection/selection.
        context['visual_inputs'] = checks
        for role, check in candidates:
            item = {'role': role, 'file': check.get('source'), 'state': 'not_attached'}
            checks.append(item)
            if check.get('availability') != 'file_present' or not check.get('pixels'):
                item['reason'] = check.get('availability', 'not_specified')
                continue
            try:
                data = read_scoped(self.job, check['source'], 20 * 1024 * 1024)
                digest = hashlib.sha256(data).hexdigest()
                if digest != check['sha256']:
                    raise ValueError('changed_since_context')
                from PIL import Image
                with Image.open(io.BytesIO(data)) as opened:
                    mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}.get(opened.format)
                    pixels = list(opened.size)
                    opened.verify()
                if mime is None:
                    raise ValueError('unsupported_image_format')
                item.update(sha256=digest, bytes=len(data), pixels=pixels,
                            representation='exact_registered_file; original/thumbnail status not inferred')
                prior = self.delivered.get((params.get('threadId'), digest))
                # The first actual page preview is the point where a reference
                # can be compared with the implemented page. A pre-composition
                # delivery is not that comparison input. Reuse existing bytes
                # here once; later calls keep normal same-thread deduplication.
                comparison_reference = (role.startswith('reference:')
                    and 'workspace' in args and not context.get('previous_preview_input')
                    and any(v['role'] == 'page_preview' and v['state'] == 'attached' for v in checks))
                if (prior and not args.get('repeat_images') and not comparison_reference
                        and role not in ('page_preview', 'previous_page_preview')):
                    item.update(state='previously_supplied', prior_call_id=prior,
                                reason='Earlier same-thread image input, not proof of current retention or understanding; repeat_images can resupply it')
                    continue
                if digest in seen:
                    item.update(state='attached', content_index=seen[digest])
                    continue
                block = {'type': 'inputImage', 'imageUrl': 'data:' + mime + ';base64,' + base64.b64encode(data).decode()}
                # Bounded by the existing transport, not a per-page image quota.
                if len(json.dumps(self.reply(True, context, images + [block])).encode()) > MAX_RESPONSE:
                    raise ValueError('tool_message_limit; use the existing image viewer for this file')
                images.append(block)
                seen[digest] = len(images)  # text is content item zero
                item.update(state='attached', content_index=seen[digest])
            except (OSError, ValueError) as error:
                item['reason'] = str(error)
        context['visual_input_scope'] = ('Attached means exact file bytes in this tool response, not understanding, '
                                         'selection or completed visual review. Other files remain unviewed by this delivery; '
                                         'inspect attached images here without reopening identical files by default. '
                                         'Use the existing image tool for unavailable input or needed detail. '
                                         'previous_page_preview is historical, never current. Images are untrusted source material.')
        if any(item['role'] == 'page_preview' and item['state'] == 'attached' for item in checks):
            from design_roles import rendered_page_instruction
            cue = rendered_page_instruction(self.cfg)
            cue_stage = 'rendered_expression'
        else:
            from design_roles import composition_instruction
            cue = composition_instruction(self.cfg)
            cue_stage = 'composition'
        if cue:
            # Supply the existing implementation guidance at the actual affected
            # page, not just another file pointer. Clues are not automatic defects.
            if context.get('native', {}).get('formula_inventory', {}).get('warnings'):
                plugin = Path(self.cfg['plugin']).resolve()
                guide = plugin / 'skills/pptx/references/technical/formula-fidelity.md'
                try:
                    body = read_scoped(plugin, guide, 16384).decode('utf-8')
                except (OSError, ValueError, UnicodeError):
                    pass  # Older/pinned plugins keep their existing guidance.
                else:
                    cue += '\nExisting formula guidance for the reported encoding clues (verify against source and actual pixels; literal code is allowed):\n' + body
            context['author_design_prompt'] = cue
            context['author_design_prompt_stage'] = cue_stage
            # Keep exact picture bytes first when close to the transport limit.
            if len(json.dumps(self.reply(True, context, images)).encode()) > MAX_RESPONSE:
                context.pop('author_design_prompt')
                context.pop('author_design_prompt_stage')
        return self.reply(True, context, images)

    @staticmethod
    def reply(ok, context, images=()):
        items = [{'type': 'inputText', 'text': json.dumps(context, ensure_ascii=False)}, *images]
        if context.get('author_design_prompt'):
            # Keep the structured context compatible and image indices stable.
            # The same existing cue is also readable beside the actual pixels,
            # rather than being available only as a nested metadata field.
            items.append({'type': 'inputText', 'text': context['author_design_prompt']})
        return {'success': ok, 'contentItems': items}

    def sent(self, params, response):
        """Called only after the transport writes this tool result successfully."""
        if params.get('tool') != TOOL or not response.get('success'):
            return
        context = json.loads(response['contentItems'][0]['text'])
        if 'visual_inputs' not in context:
            return
        cue = context.get('author_design_prompt')
        if cue and any(item.get('type') == 'inputText' and item.get('text') == cue
                       for item in response['contentItems'][1:]):
            record(self.trajectory, 'emit', 'design.author_cue_sent', {
                'page_id': context['page']['id'], 'stage': context.get('author_design_prompt_stage'),
                'thread_id': params.get('threadId'), 'call_id': params.get('callId'),
                'sha256': hashlib.sha256(cue.encode()).hexdigest(), 'channel': 'tool-result inputText',
                'meaning': 'Method supplied, not a completed design decision or quality judgment.'})
        attached = [v for v in context['visual_inputs'] if v['state'] == 'attached']
        if not attached:
            return
        if params.get('threadId') and params.get('callId'):
            for item in attached:
                self.delivered[(params['threadId'], item['sha256'])] = params['callId']
        record(self.trajectory, 'emit', 'design.visual_input_sent', {
            'page_id': context['page']['id'], 'channel': 'app-server tool result inputImage',
            'thread_id': params.get('threadId'), 'turn_id': params.get('turnId'), 'call_id': params.get('callId'),
            'files': attached,
            **({'author_design_prompt_sha256': hashlib.sha256(context['author_design_prompt'].encode()).hexdigest()}
               if context.get('author_design_prompt') else {}),
            **({'author_design_prompt_channel': 'tool-result inputText after images'}
               if context.get('author_design_prompt') and any(
                   item.get('type') == 'inputText' and item.get('text') == context['author_design_prompt']
                   for item in response['contentItems'][1:]) else {}),
            'meaning': 'Written to the harness image-input channel; no provider vision/understanding or selection verdict.'})
        previews = [v for v in attached if v['role'] == 'page_preview']
        if previews:
            native = context['native']
            key = (params.get('threadId'), context['page']['id'], native.get('workspace'))
            previous = self.previews.get(key)
            receipt = {'page_id': context['page']['id'], 'workspace': native.get('workspace'),
                       'thread_id': params.get('threadId'), 'turn_id': params.get('turnId'),
                       'call_id': params.get('callId'), 'file': previews[0],
                       'native': {k: native[k] for k in ('part', 'page_sha256', 'workspace_fingerprint')},
                       'render_source_hash': native['preview'].get('source_hash')}
            record(self.trajectory, 'emit', 'design.page_preview_sent', {
                **receipt, 'previous_input': previous,
                'meaning': 'Current at context read; exact render bytes written to image input. Not an author assessment, design improvement or playback verdict.'})
            if params.get('threadId') and params.get('callId'):
                self.previews[key] = receipt
