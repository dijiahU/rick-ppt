"""Map a library template's fonts to deployment fonts, keeping weight and role (2026-11-21).

47 of the 64 WPS library templates set most text in WPS cloud fonts (思源黑体/宋体, 汉仪, 方正,
MiSans, HarmonyOS, Lato...). Their library previews were rendered with those fonts, but the job
renderer, PowerPoint and recipients' Windows machines fall back to a regular face: the template's
heavy display titles turn thin and calligraphy turns into SimSun. A deck built on such a template
looked worse than the template the author chose. Library copies are therefore mapped to approved
fonts that ship with Windows and Office for Mac, preserving weight (heavy → bold) and role
(sans / serif / script / Latin). User-supplied templates are never passed through this.

  map_pptx(path) -> {'mapped': {old: new}, 'install': [font ids], 'bolded': n}
"""
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

KEEP = {'wingdings', 'wingdings 2', 'wingdings 3', 'webdings', 'symbol', 'marlett'}
APPROVED = {'times new roman', 'simsun', '宋体', 'dengxian', 'dengxian light', '等线', '等线 light', 'arial', 'microsoft yahei',
            'microsoft yahei light', '微软雅黑', '微软雅黑 light', 'simhei', '黑体', 'kaiti', '楷体', 'fangsong', '仿宋', 'calibri',
            'cambria', 'georgia', 'century gothic', 'verdana', 'tahoma', 'arial black', 'calibri light'}
SCRIPT = ('行书', '行楷', '毛笔', '手书', '书法', '手写', '楷', '说文', '說文', '篆', '隶', '隸', '佛系', '草', 'calligraph', 'brush', 'script', 'hand')
SERIF = ('宋', '明朝', 'serif', '刻本', '古籍', '木兰', '仿宋', 'song', 'ming', 'garamond', 'didot', 'bodoni', 'playfair',
         'baskerville', 'times', 'georgia')
HEAVY = ('heavy', 'black', 'blk', 'extrabold', 'ultra', 'bebas', 'impact', 'oswald', 'anton', '特粗', '超粗', 'w8', 'w9', '85', '75', '95')
BOLD = ('bold', 'semibold', 'demibold', 'medium', '中粗', '粗', 'w6', 'w7', '65')
LIGHT = ('extralight', 'ultralight', 'thin', 'light', '细', 'w1', 'w2', 'w3', '25', '35', '45')


def _has_cjk(text):
    return any('\u3400' <= ch <= '\u9fff' for ch in text)


def classify(family):
    """-> (new family, weight) or None to keep."""
    low = family.lower().strip()
    if not low or low.startswith('+') or low in KEEP or low in APPROVED:
        return None
    weight = ('heavy' if any(k in low for k in HEAVY) else 'bold' if any(k in low for k in BOLD)
              else 'light' if any(k in low for k in LIGHT) else 'regular')
    cjk = _has_cjk(family) or any(k in low for k in ('han ', 'cn', 'sc', 'misans', 'harmonyos', 'alibaba', 'puhui', 'pingfang'))
    if any(k in low for k in SCRIPT):
        return ('KaiTi' if cjk else 'Georgia'), weight
    if '仿宋' in family:
        return 'FangSong', weight
    if any(k in low for k in SERIF):
        return ('SimSun' if cjk else 'Georgia'), weight
    if cjk:
        return ('Microsoft YaHei Light' if weight == 'light' else 'Microsoft YaHei'), weight
    return 'Arial', weight


INSTALL = {('Microsoft YaHei', 'regular'): 'microsoft-yahei-regular', ('Microsoft YaHei', 'bold'): 'microsoft-yahei-bold',
           ('Microsoft YaHei', 'heavy'): 'microsoft-yahei-bold', ('Microsoft YaHei Light', 'light'): 'microsoft-yahei-light',
           ('KaiTi', None): 'kaiti-regular', ('FangSong', None): 'fangsong-regular', ('Georgia', 'bold'): 'georgia-bold',
           ('Georgia', 'heavy'): 'georgia-bold', ('Georgia', None): 'georgia-regular', ('SimSun', None): 'simsun-regular',
           ('Arial', 'bold'): 'arial-bold', ('Arial', 'heavy'): 'arial-bold', ('Arial', None): 'arial-regular'}

# Only fonts that set text: theme <a:font script=...> rows are per-script fallbacks and stay.
FONT_REF = re.compile(r'(<a:(?:latin|ea|cs|sym|buFont)\b[^>]*?typeface=")([^"]*)(")')
RUN_PROPS = re.compile(r'<a:(rPr|defRPr|endParaRPr)\b((?:[^>/]|/(?!>))*)>(.*?)</a:\1>', re.S)


def _rewrite(xml, mapping, counters):
    def props(match):
        tag, attrs, body = match.groups()
        heavy = False
        for ref in FONT_REF.finditer(body):
            if ref.group(2) in mapping and mapping[ref.group(2)][1] in ('heavy', 'bold'):
                heavy = True
        if heavy and not re.search(r'\bb="1"', attrs):
            attrs = re.sub(r'\s*\bb="0"', '', attrs) + ' b="1"'
            counters['bolded'] += 1
        return f'<a:{tag}{attrs}>{body}</a:{tag}>'
    xml = RUN_PROPS.sub(props, xml)
    return FONT_REF.sub(lambda m: m.group(1) + (mapping[m.group(2)][0] if m.group(2) in mapping else m.group(2)) + m.group(3), xml)


def map_pptx(path):
    path = Path(path)
    with zipfile.ZipFile(path) as source:
        names = [n for n in source.namelist() if n.startswith('ppt/') and n.endswith('.xml')]
        families = set()
        for name in names:
            families.update(m.group(2) for m in FONT_REF.finditer(source.read(name).decode('utf-8', 'ignore')))
        mapping = {f: c for f in families if (c := classify(f))}
        if not mapping:
            return {'mapped': {}, 'install': [], 'bolded': 0}
        counters = {'bolded': 0}
        handle, temp = tempfile.mkstemp(suffix=".pptx", dir=path.parent)
        import os; os.close(handle)
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename in names:
                    data = _rewrite(data.decode('utf-8'), mapping, counters).encode('utf-8')
                target.writestr(item, data)
    shutil.move(temp, path)
    install = sorted({INSTALL.get((new, weight)) or INSTALL.get((new, None)) for new, weight in mapping.values()} - {None})
    return {'mapped': {old: new + (' (bold)' if weight in ('heavy', 'bold') else '') for old, (new, weight) in sorted(mapping.items())},
            'install': install, 'bolded': counters['bolded']}


def preview_note(path):
    """One line for template search results when mapping visibly changes the look, else None."""
    with zipfile.ZipFile(path) as source:
        families = set()
        for name in source.namelist():
            if name.startswith('ppt/slides/') and name.endswith('.xml'):
                families.update(m.group(2) for m in FONT_REF.finditer(source.read(name).decode('utf-8', 'ignore')))
    # A plain 楷体 (方正楷体, 华康楷体) already looks like KaiTi; only real lettering changes the look.
    script = sorted(f for f in families if (c := classify(f)) and c[0] in ('KaiTi', 'Georgia')
                    and any(k in f.lower() for k in SCRIPT) and '楷体' not in f)
    if script:
        return (f"Its calligraphy/handwritten fonts ({', '.join(script[:3])}) become KaiTi/Georgia in the editable copy; "
                'the preview shows lettering the deck will not have. Choose it for layout, not for that lettering.')
    return None
