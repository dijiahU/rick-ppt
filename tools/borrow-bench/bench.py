#!/usr/bin/env python3
"""Borrow bench: one reference image -> one slide, measured against a no-reference control.

  bench.py prepare [--from DIR]            fetch/copy the 15 reference images into refs/
  bench.py submit TAG [--arm ref|control|both] [--cases ID,...] [--fast]
  bench.py wait TAG                        poll the local site, download finished decks
  bench.py render TAG                      LibreOffice (Docker renderer) -> PNG per deck
  bench.py judge TAG [--model opus]        blind Claude judge: reference + both arms (random order)
  bench.py report TAG                      runs/TAG/report.html side-by-side with scores

Runs against the local website (http://127.0.0.1:3000, mock sign-in). Judge-only notes in cases.json
('learnable', 'traps') are never sent to the author.
"""
import argparse, hashlib, http.cookiejar, json, random, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFS = HERE / 'refs'
RUNS = HERE / 'runs'
SITE = 'http://127.0.0.1:3000'
LIBRARY = Path.home() / '.rick-ppt/reference-library/templates/pages'
COMMONS = {
    'wave': 'Great Wave off Kanagawa2.jpg',
    'wedge': 'Beat the Whites with the Red Wedge.jpg',
    'mondrian': 'Piet Mondriaan, 1930 - Mondrian Composition II in Red, Blue, and Yellow.jpg',
    'hammershoi': 'Vilhelm Hammershøi - Interior from Strandgade with Sunlight on the Floor.jpg',
    'hiroshige': 'Hiroshige, Sudden shower over Shin-Ōhashi bridge and Atake, 1857.jpg',
    'haeckel': 'Haeckel Discomedusae 8.jpg',
    'vermeer': 'Johannes Vermeer - Het melkmeisje - Google Art Project.jpg',
    'minard': 'Minard.png',
    'ando': 'Church of Light.JPG',
    'hohlwein': 'Ludwig Hohlwein, Yellowstone Park, 1910, poster.jpg',
}
UA = {'User-Agent': 'borrow-bench/1.0 (research use)'}

BRIEF_REF = """做 1 页 PPT（中文，16:9），这是单页练习，只交这一页。

页面标题：{title}
页面内容：{content}

设计参考：附件里的图片是这一页唯一的设计参考。它的题材和本页内容无关——不要照搬它的画面、文字或题材元素；要读懂并转化它的艺术设计（构图结构、尺度对比、色彩关系、字体层级、留白、图形手法），用到本页内容上。本页不再另外搜索设计参考、模板或灵感图；内容本身需要的配图可以自己找或生成。"""

BRIEF_CONTROL = """做 1 页 PPT（中文，16:9），这是单页练习，只交这一页。

页面标题：{title}
页面内容：{content}

设计：按你的判断设计这一页。本页不搜索设计参考、模板或灵感图；内容本身需要的配图可以自己找或生成。"""


def cases(only=None):
    data = json.loads((HERE / 'cases.json').read_text())['cases']
    if only:
        keep = set(only.split(','))
        data = [c for c in data if c['id'] in keep or c['id'].split('-')[0] in keep]
    return data


def ref_path(case):
    hits = sorted(REFS.glob(case['id'] + '.*'))
    return hits[0] if hits else None


def _get(url):
    for attempt in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise
        except urllib.error.URLError:
            pass
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f'download failed: {url}')


def prepare(args):
    REFS.mkdir(exist_ok=True)
    manifest = {}
    for case in cases():
        src = case['source']
        if src['kind'] == 'template':
            origin = LIBRARY / (src['page'] + '.jpg')
            target = REFS / (case['id'] + '.jpg')
            shutil.copy(origin, target)
            info = {'origin': f'template-library:{src["page"]}', 'license': 'local template library (internal use)'}
        else:
            key = src['file']
            local = sorted(Path(args.src).glob(key + '.*')) if args.src else []
            api = ('https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata'
                   '&iiurlwidth=1280&format=json&titles=' + urllib.parse.quote('File:' + COMMONS[key]))
            page = next(iter(json.loads(_get(api))['query']['pages'].values()))['imageinfo'][0]
            meta = page.get('extmetadata', {})
            url = (page.get('thumburl') or page['url']).split('?')[0]
            ext = url.rsplit('.', 1)[-1].lower()
            target = REFS / f'{case["id"]}.{ext}'
            target.write_bytes(local[0].read_bytes() if local else _get(url))
            info = {'origin': page.get('descriptionurl'), 'license': (meta.get('LicenseShortName') or {}).get('value'),
                    'date': ((meta.get('DateTimeOriginal') or {}).get('value') or '')[:40]}
            time.sleep(3)
        info.update(file=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        manifest[case['id']] = info
        print(case['id'], info['license'])
    (REFS / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))


def opener():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.open(SITE + '/signin-with-chatgpt?return_to=/api/account', timeout=30).read()
    return op


def submit(args):
    run = RUNS / args.tag
    run.mkdir(parents=True, exist_ok=True)
    jobs_file = run / 'jobs.json'
    jobs = json.loads(jobs_file.read_text()) if jobs_file.exists() else {}
    op = opener()
    headers = {'Origin': SITE, 'X-UI-Language': 'zh-CN'}
    arms = ['ref', 'control'] if args.arm == 'both' else [args.arm]
    for case in cases(args.cases):
        for arm in arms:
            key = f'{case["id"]}:{arm}'
            if key in jobs:
                continue
            request_key = str(uuid.uuid4())
            uploads = []
            if arm == 'ref':
                ref = ref_path(case)
                if ref is None:
                    sys.exit(f'missing reference for {case["id"]}; run prepare first')
                url = SITE + '/api/uploads?' + urllib.parse.urlencode({'scope': 'job:' + request_key, 'name': '设计参考' + ref.suffix})
                reply = op.open(urllib.request.Request(url, data=ref.read_bytes(), headers={**headers, 'Content-Type': 'application/octet-stream'}))
                uploads.append(json.loads(reply.read())['id'])
            brief = (BRIEF_REF if arm == 'ref' else BRIEF_CONTROL).format(**case)
            body = {'title': f'[借鉴测评 {case["id"][:3]} {arm}] {case["title"]}', 'brief': brief, 'pages': 1, 'style': '',
                    'language': 'zh-CN', 'requestKey': request_key, 'uploadIds': uploads}
            if args.fast:
                body['fast'] = True
            try:
                reply = op.open(urllib.request.Request(SITE + '/api/jobs', data=json.dumps(body).encode(),
                                                       headers={**headers, 'Content-Type': 'application/json'}))
            except urllib.error.HTTPError as error:
                print(key, 'HTTP', error.code, error.read()[:300])
                continue
            jobs[key] = json.loads(reply.read())['id']
            jobs_file.write_text(json.dumps(jobs, indent=1))
            print(key, jobs[key], flush=True)


def wait(args):
    run = RUNS / args.tag
    jobs = json.loads((run / 'jobs.json').read_text())
    status_file = run / 'status.json'
    done = json.loads(status_file.read_text()) if status_file.exists() else {}
    started = time.time()
    while len(done) < len(jobs) and time.time() - started < args.hours * 3600:
        try:
            op = opener()
            account = {j['id']: j for j in json.loads(op.open(SITE + '/api/account', timeout=30).read())['jobs']}
        except Exception as error:  # site restarting
            print('site error', error, flush=True)
            time.sleep(60)
            continue
        for key, job_id in jobs.items():
            job = account.get(job_id, {})
            if key in done or job.get('status') not in ('complete', 'failed', 'cancelled'):
                continue
            case_id, arm = key.split(':')
            if job.get('download'):
                target = run / arm / f'{case_id}.pptx'
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(op.open(SITE + f'/api/jobs/{job_id}/download', timeout=120).read())
            done[key] = {'status': job['status'], 'minutes': job.get('durationMinutes')}
            status_file.write_text(json.dumps(done, indent=1))
            print(time.strftime('%H:%M'), key, job['status'], flush=True)
        time.sleep(60)
    print('finished', len(done), 'of', len(jobs))


def render(args):
    run = RUNS / args.tag
    fonts = REPO / 'runner/font-cache.local/fonts'
    office = Path('/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts')
    for deck in sorted(run.glob('*/*.pptx')):
        png = deck.with_suffix('.png')
        if png.exists():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy(deck, tmp / 'in.pptx')
            mounts = ['-v', f'{fonts}:/usr/share/fonts/rick:ro'] + (['-v', f'{office}:/usr/share/fonts/office:ro'] if office.exists() else [])
            subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--tmpfs', '/tmp:exec,mode=1777', '-e', 'HOME=/tmp',
                            '-v', f'{tmp}:/w', *mounts, '-w', '/w', '--entrypoint', 'sh', 'pptx-lab-renderer:1', '-c',
                            'fc-cache -f >/dev/null 2>&1; soffice -env:UserInstallation=file:///tmp/lo --headless --convert-to pdf --outdir /w in.pptx >/dev/null 2>&1'],
                           capture_output=True, timeout=600)
            if not (tmp / 'in.pdf').exists():
                print('render failed', deck)
                continue
            subprocess.run(['pdftoppm', '-png', '-r', '96', '-f', '1', '-l', '1', '-singlefile', str(tmp / 'in.pdf'), str(tmp / 'p')], check=True)
            shutil.copy(tmp / 'p.png', png)
            print('rendered', deck.relative_to(run))


JUDGE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['A', 'B', 'more_transfer', 'better_page', 'reason'],
    'properties': {
        **{side: {'type': 'object', 'additionalProperties': False,
                  'required': ['structure', 'scale', 'color', 'typography', 'devices', 'content_fit', 'readability', 'literal_copy', 'ai_look', 'borrowed', 'missed'],
                  'properties': {
                      'structure': {'type': 'integer'},
                      'scale': {'type': 'integer'},
                      'color': {'type': 'integer'},
                      'typography': {'type': 'integer'},
                      'devices': {'type': 'integer'},
                      'content_fit': {'type': 'integer'},
                      'readability': {'type': 'integer'},
                      'literal_copy': {'type': 'boolean'},
                      'ai_look': {'type': 'array', 'items': {'type': 'string'}},
                      'borrowed': {'type': 'string'},
                      'missed': {'type': 'string'}}} for side in ('A', 'B')},
        'more_transfer': {'type': 'string', 'enum': ['A', 'B', 'tie']},
        'better_page': {'type': 'string', 'enum': ['A', 'B', 'tie']},
        'reason': {'type': 'string'}}}

JUDGE_PROMPT = """你在评估“从一张参考图借鉴艺术设计做一页 PPT”的能力。第一张图 reference 是参考图，它的题材与页面内容无关；A、B 是同一内容的两页 PPT，其中至多一页看过参考图，你不知道是哪一页。

页面内容：{title}——{content}

参考图里值得转化的设计（评审用，作者看不到）：
{learnable}
常见误用：
{traps}

对 A、B 分别按 1–5 打分（3=普通合格，5=专业设计师水准）：
- structure：页面结构/构图是否转化了参考图的结构关系（不是照抄位置，而是关系）
- scale：尺度对比、主次关系的转化
- color：色彩关系（主色/强调色比例、明暗）的转化，并适合本内容
- typography：字体层级与排字方式
- devices：参考图里的图形手法是否被换成适合本内容的等价手法
- content_fit：设计是否服务内容，信息完整准确
- readability：投影/阅读可读性
literal_copy：是否照搬了参考图的题材画面、文字或符号（照搬为 true）。
ai_look：列出你看到的全部“AI 生成 PPT 味”特征（如低饱和卡片堆叠、米白底、四平八稳的模板布局、装饰性图标），没有就空数组。
borrowed：一句话说这页实际借到了什么；missed：一句话说最该借却没借到的。
more_transfer：哪页更明显地学到参考图的设计；better_page：只看页面本身，哪页更好。reason 简述。
没有参考图影响的页面在借鉴维度上可以低分，这是正常的。"""


def judge(args):
    sys.path.insert(0, str(REPO / 'runner'))
    import claude_vision
    run = RUNS / args.tag
    out_file = run / 'judge.json'
    results = json.loads(out_file.read_text()) if out_file.exists() else {}
    for case in cases(args.cases):
        ref_png, ctl_png = run / 'ref' / f'{case["id"]}.png', run / 'control' / f'{case["id"]}.png'
        if case['id'] in results or not ref_png.exists() or not ctl_png.exists():
            continue
        flip = random.random() < 0.5
        a, b = (ctl_png, ref_png) if flip else (ref_png, ctl_png)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ref = ref_path(case)
            images = [tmp / ('reference' + ref.suffix), tmp / 'A.png', tmp / 'B.png']
            for src, dst in zip((ref, a, b), images):
                shutil.copy(src, dst)
            prompt = JUDGE_PROMPT.format(title=case['title'], content=case['content'],
                                         learnable='\n'.join('- ' + x for x in case['learnable']),
                                         traps='\n'.join('- ' + x for x in case['traps']))
            prompt += ('\n\n只输出一个 JSON 对象，不要其他文字，结构符合这个 JSON Schema：\n' + json.dumps(JUDGE_SCHEMA, ensure_ascii=False))
            reply = claude_vision.ask({}, prompt, images, None, model=args.model, timeout=600)
        text = reply['text']
        verdict = json.loads(text[text.index('{'):text.rindex('}') + 1])
        arm_of = {'A': 'control' if flip else 'ref', 'B': 'ref' if flip else 'control'}
        results[case['id']] = {'arms': {arm_of[s]: verdict[s] for s in 'AB'},
                               'more_transfer': arm_of.get(verdict['more_transfer'], 'tie'),
                               'better_page': arm_of.get(verdict['better_page'], 'tie'),
                               'reason': verdict['reason'], 'judge_model': reply['model']}
        out_file.write_text(json.dumps(results, ensure_ascii=False, indent=1))
        print(case['id'], 'transfer→', results[case['id']]['more_transfer'], 'better→', results[case['id']]['better_page'], flush=True)
    summarize(results)


DIMS = ('structure', 'scale', 'color', 'typography', 'devices', 'content_fit', 'readability')


def summarize(results):
    if not results:
        return
    n = len(results)
    for arm in ('ref', 'control'):
        rows = [r['arms'][arm] for r in results.values()]
        avg = {d: round(sum(x[d] for x in rows) / n, 2) for d in DIMS}
        print(arm, avg, 'literal_copy', sum(x['literal_copy'] for x in rows), 'ai_look_tells', sum(len(x['ai_look']) for x in rows))
    for key in ('more_transfer', 'better_page'):
        tally = {}
        for r in results.values():
            tally[r[key]] = tally.get(r[key], 0) + 1
        print(key, tally)


def report(args):
    import html
    run = RUNS / args.tag
    results = json.loads((run / 'judge.json').read_text()) if (run / 'judge.json').exists() else {}
    rows = []
    for case in cases():
        ref = ref_path(case)
        if ref is None:
            continue
        cells = [f'<img src="../../refs/{ref.name}">']
        for arm in ('ref', 'control'):
            png = run / arm / f'{case["id"]}.png'
            score = results.get(case['id'], {}).get('arms', {}).get(arm)
            note = ''
            if score:
                note = (' · '.join(f'{d} {score[d]}' for d in DIMS) + f'<br>借到：{html.escape(score["borrowed"])}'
                        f'<br>没借到：{html.escape(score["missed"])}' + (f'<br>AI味：{html.escape("；".join(score["ai_look"]))}' if score['ai_look'] else ''))
            cells.append((f'<img src="{arm}/{png.name}">' if png.exists() else '<div class="empty">无</div>') + f'<p>{note}</p>')
        verdict = results.get(case['id'])
        head = f'<h2>{case["id"]} · {html.escape(case["title"])}</h2><p class="src">{html.escape(case["source"]["desc"])}</p>'
        if verdict:
            head += f'<p>更像参考：<b>{verdict["more_transfer"]}</b> · 页面更好：<b>{verdict["better_page"]}</b> — {html.escape(verdict["reason"])}</p>'
        rows.append(head + '<div class="row">' + ''.join(f'<div>{c}</div>' for c in cells) + '</div>')
    page = ('<!doctype html><meta charset="utf-8"><title>借鉴测评 ' + args.tag + '</title><style>'
            'body{font:14px/1.5 sans-serif;margin:24px;background:#fff;color:#111}.row{display:grid;grid-template-columns:1fr 1.4fr 1.4fr;gap:12px}'
            '.row img{width:100%;border:1px solid #ddd}.src{color:#666}.empty{height:200px;background:#eee}h2{margin-top:40px}</style>'
            '<h1>借鉴测评 ' + args.tag + '</h1><p>列：参考图 ｜ 看过参考（ref） ｜ 未看参考（control）</p>' + ''.join(rows))
    (run / 'report.html').write_text(page)
    print(run / 'report.html')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--from', dest='src'); p.set_defaults(fn=prepare)
    p = sub.add_parser('submit'); p.add_argument('tag'); p.add_argument('--arm', default='both', choices=['ref', 'control', 'both'])
    p.add_argument('--cases'); p.add_argument('--fast', action='store_true'); p.set_defaults(fn=submit)
    p = sub.add_parser('wait'); p.add_argument('tag'); p.add_argument('--hours', type=float, default=6); p.set_defaults(fn=wait)
    p = sub.add_parser('render'); p.add_argument('tag'); p.set_defaults(fn=render)
    p = sub.add_parser('judge'); p.add_argument('tag'); p.add_argument('--cases'); p.add_argument('--model', default='opus'); p.set_defaults(fn=judge)
    p = sub.add_parser('report'); p.add_argument('tag'); p.set_defaults(fn=report)
    args = parser.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
