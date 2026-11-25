#!/usr/bin/env python3
"""Tag template-library pages with style / treatment / idea fields.

Adds mood, light, palette, composition, treatment, motif, metaphor, borrowable and
borrow_kind to index.json so action=inspire can find pages worth borrowing even when
their layout does not fit (2026-11-24).

    python3 tools/annotate-template-library.py --limit 12        # pilot
    python3 tools/annotate-template-library.py --batch 6 --workers 3
    python3 tools/annotate-template-library.py --overwrite --ids t1234abcd-03

Calls the local Claude CLI (default model "sonnet"). Every batch is written back, so
an interrupted run resumes where it stopped. A backup of index.json is kept once.
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runner'))
import claude_vision  # noqa: E402

DEFAULT = Path.home() / '.rick-ppt/reference-library/templates'
MOOD = ['安静', '戏剧', '温暖', '冷峻', '怀旧', '克制', '浓烈', '清透', '厚重', '轻盈', '无']
LIGHT = ['自然光', '硬光', '柔光', '逆光', '阴影', '雾', '无']
COMPOSITION = ['对角线', '居中', '左右分置', '上下分层', '满版出血', '负空间', '框架', '密集', '网格', '对称', '不对称']
TREATMENT = ['雾化', '褪色', '裁切', '叠压', '单色', '高对比', '拼贴', '纹理', '无']
BORROW_KIND = ['structure', 'visual_grammar', 'treatment', 'motif', 'mood', 'idea']

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['pages'], 'properties': {'pages': {
    'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['id', 'mood', 'light', 'palette', 'composition', 'treatment', 'motif', 'metaphor',
                     'borrowable', 'borrow_kind'],
        'properties': {
            'id': {'type': 'string'},
            'mood': {'type': 'string', 'enum': MOOD},
            'light': {'type': 'string', 'enum': LIGHT},
            'palette': {'type': 'string', 'maxLength': 24, 'description': '主色 + 明度关系，如“深绿压白”“黑白灰”“暖米+赭”'},
            'composition': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'enum': COMPOSITION}},
            'treatment': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'enum': TREATMENT}},
            'motif': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'maxLength': 12},
                      'description': '画面母题，如 一条路径 / 重复 / 孤点 / 框 / 层叠 / 空白'},
            'metaphor': {'type': 'string', 'maxLength': 40, 'description': '这页在说什么，不是题材'},
            'borrowable': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'maxLength': 60},
                           'description': '可执行的视觉决定，不是形容词'},
            'borrow_kind': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'enum': BORROW_KIND}}}}}}}

PROMPT = """你是版面研究助手。下面每张图是模板库中的一页幻灯片，按文件名顺序给出。
只看画面本身，不要猜题材、品牌或文字含义；为每一页填写风格与手法标签。

要求：
1. mood / light / composition / treatment 从给定选项里选，没有就写“无”。
2. palette 写主色与明度关系（如“深绿压白”“黑白灰”“暖米+赭色”），不要写色号。
3. motif 写画面的组织母题（如“一条路径”“重复”“孤点”“框”“层叠”“空白”）。
4. metaphor 用一句话说这页在表达什么关系，不是题材（如“一条路穿过密林，其余退后”）。
5. borrowable 写 2–3 条“这页能借什么”，必须具体到能执行：
   例如“右图左缘用白渐变洗淡背景，给标题腾出半幅”
        “标题 60pt 极细、字距拉开，下面配 12pt 中文小字”
        “五个等宽列，只用一列反色突出重点”
   不要写“简洁大气”“高级感”这类形容词。
6. borrow_kind 按借用的性质多选：structure 版式关系、visual_grammar 比例/色彩/明度、
   treatment 照片处理、motif 母题、mood 气质、idea 思路。
7. 如果这页是版权、字体、素材说明、二维码、图标库或空白示例页：
   mood 写“无”，borrowable 与 borrow_kind 都写 []。
8. 一页最多借 3 条；宁可少写，也不要凑数。"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--library', type=Path, default=DEFAULT)
    ap.add_argument('--limit', type=int, default=0, help='Tag at most N pages')
    ap.add_argument('--batch', type=int, default=6, help='Pages per Claude call')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--model', default='sonnet')
    ap.add_argument('--quality-min', type=float, default=0)
    ap.add_argument('--ids', nargs='*', default=[])
    ap.add_argument('--overwrite', action='store_true', help='Re-tag pages that already have mood')
    ap.add_argument('--dry-run', action='store_true', help='Do not write index.json')
    args = ap.parse_args()

    index_path = args.library / 'index.json'
    index = json.loads(index_path.read_text())
    wanted = set(args.ids)
    pages = [p for p in index['pages']
             if (p['id'] in wanted if wanted else (args.overwrite or not p.get('mood')))
             and (p.get('quality') or 3) >= args.quality_min]
    pages.sort(key=lambda p: (-(p.get('quality') or 3), p['id']))
    if args.limit:
        pages = pages[:args.limit]
    if not pages:
        print('nothing to tag')
        return

    print(f'tagging {len(pages)} pages, batch {args.batch}, model {args.model}, workers {args.workers}')
    lock = threading.Lock()
    counts = {'done': 0, 'failed': 0, 'cost': 0.0}
    stamp = datetime.now().strftime('%Y-%m-%d')
    backed_up = False

    def tag_batch(batch):
        ids = [p['id'] for p in batch]
        images = [args.library / p['file'] for p in batch]
        label = 'pages=' + ','.join(ids)
        prompt = PROMPT + '\n\n本批页面 id 依次为：' + ', '.join(ids) + '。每页返回一个对象，id 必须与之一一对应。'
        try:
            result = claude_vision.ask({'claude_model': args.model}, prompt, images, SCHEMA, timeout=420)
            rows = (result.get('structured') or {}).get('pages') or []
            by_id = {r.get('id'): r for r in rows if isinstance(r, dict)}
        except Exception as error:  # keep the run alive; the batch is retried on the next run
            with lock:
                counts['failed'] += len(batch)
            print(f'  FAIL {label}: {type(error).__name__}: {error}', flush=True)
            return
        ok = 0
        with lock:  # mutate and write under one lock: json.dumps must not see a page change size
            for page in batch:
                row = by_id.get(page['id'])
                if not row:
                    continue
                for key in ('mood', 'light', 'palette', 'metaphor'):
                    if isinstance(row.get(key), str) and row[key].strip():
                        page[key] = row[key].strip()
                for key in ('composition', 'treatment', 'motif', 'borrowable', 'borrow_kind'):
                    value = row.get(key)
                    if isinstance(value, list):
                        page[key] = [str(v).strip() for v in value if str(v).strip()][:3]
                page['annotated'] = stamp
                ok += 1
            counts['done'] += ok
            counts['failed'] += len(batch) - ok
            counts['cost'] += result.get('cost_usd') or 0
            print(f'  {ok}/{len(batch)} {label[:70]}  ({result.get("seconds")}s)', flush=True)
            if not args.dry_run:
                nonlocal_backup[0] = write(index_path, index, nonlocal_backup[0])

    nonlocal_backup = [False]
    batches = [pages[i:i + args.batch] for i in range(0, len(pages), args.batch)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(tag_batch, batches))
    print(f"\ntagged {counts['done']}, failed {counts['failed']}, cost ${counts['cost']:.3f}, "
          f"{time.monotonic() - started:.0f}s")
    if args.dry_run:
        print('dry run; index.json untouched')
    else:
        write(index_path, index, True)
        print(f'written: {index_path}')


def write(index_path, index, backed_up):
    if not backed_up:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = index_path.with_name(f'index.backup-{stamp}.json')
        backup.write_bytes(index_path.read_bytes())
        print(f'  backup {backup.name}', flush=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    return True


if __name__ == '__main__':
    main()
