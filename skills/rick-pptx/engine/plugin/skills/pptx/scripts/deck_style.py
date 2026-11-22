"""Deck-wide style tokens (deck-style.json in the task root) shared by every page.

The author writes the file once before page 1. Native batches and edits accept "@name"
colours (e.g. "@primary", "@text") that resolve to it, so every page draws from one
palette; layout checks flag colours that are not in it.

  {"register": "restrained",              # restrained | standard | expressive | celebratory
   "colors": {"background": "FFFFFF", "text": "1F2329", "muted": "8A9099",
              "primary": "1F5FBF", "accent": "E8590C", "positive": "2E7D32", "negative": "C62828"},
   "type": {"title": 36, "subtitle": 24, "body": 18, "caption": 12},
   "margin": 0.6,
   "layouts": ["cover", "section", "text + picture", "data", "comparison", "summary"],
   "references": ["references/browse/1.jpg"],
   "rhythm": {"cover": "peak", "growth": "working", "risk": "peak", "next-week": "rest"},
   "quiet_system": {"ground": "左侧四分之一铺浅灰色带", "display": "用浅色超大章节数字压在文字后面",
                    "mark": "在每页右下页码旁放一个红点"},
   "devices": {"red square": "starts the one key figure on a page",
               "hairline stack": "texture that marks section openers",
               "vertical tab": "page meta at the left edge"}}
"""
import json
import re
from pathlib import Path

FILE = 'deck-style.json'
REGISTERS = ('restrained', 'standard', 'expressive', 'celebratory')
HEX = re.compile(r'[0-9A-Fa-f]{6}')
QUIET_EXAMPLE = {'ground': '左侧四分之一铺浅灰色带', 'display': '用浅色超大章节数字压在文字后面',
                 'mark': '在每页右下页码旁放一个红点'}


def find(start):
    """deck-style.json in the task root, found from the task root or any folder below it."""
    path = Path(start).resolve()
    for folder in (path, *path.parents):
        candidate = folder / FILE
        if candidate.is_file():
            return candidate
        if (folder / 'request.json').is_file():
            return None
    return None


def load(start, require_quiet=False):
    path = find(start)
    style = json.loads(path.read_text()) if path is not None else None
    if require_quiet:
        quiet = style.get('quiet_system') if isinstance(style, dict) else None
        if not isinstance(quiet, dict) or any(not isinstance(quiet.get(k), str) or len(quiet[k].strip()) < 8
                                              for k in QUIET_EXAMPLE):
            raise ValueError('deck-style.json 的 quiet_system 中 ground、display、mark 各需至少 8 个字符。完整示例：'
                             + json.dumps({'quiet_system': QUIET_EXAMPLE}, ensure_ascii=False))
    if path is None:
        return None
    colors = style.get('colors') if isinstance(style, dict) else None
    if not isinstance(colors, dict) or not all(isinstance(v, str) and HEX.fullmatch(v) for v in colors.values()):
        raise ValueError('deck-style.json colors must map names to RRGGBB values')
    if style.get('register') not in REGISTERS:
        raise ValueError('deck-style.json register must be restrained, standard, expressive or celebratory')
    # devices and type are optional author notes; only their shape is checked when present
    # (2026-11-21: required counts produced perfunctory entries, so they are no longer enforced).
    devices = style.get('devices')
    if devices is not None and not (isinstance(devices, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in devices.items())):
        raise ValueError('deck-style.json "devices", when given, maps a device name to its job')
    sizes = style.get('type')
    if sizes is not None and not (isinstance(sizes, dict) and all(type(v) in (int, float) for v in sizes.values())):
        raise ValueError('deck-style.json "type", when given, maps type roles to point sizes')
    return style


def resolve(value, style):
    """Replace "@name" colours (in strings, lists and dicts) with the deck palette."""
    if isinstance(value, str) and value.startswith('@'):
        if style is None:
            raise ValueError(f'{value} needs deck-style.json in the task root')
        name = value[1:]
        if name not in style['colors']:
            raise ValueError(f'{value} is not in deck-style.json colors ({", ".join(style["colors"])})')
        return style['colors'][name].upper()
    if isinstance(value, list):
        return [resolve(v, style) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, style) for k, v in value.items()}
    return value


def palette(style):
    return {v.upper() for v in style['colors'].values()} if style else set()
