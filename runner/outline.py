"""Small public outline contract; never publishes arbitrary task files."""
import hashlib
import json
import re

MAX_SLIDES = 50
MAX_OUTLINE_BYTES = 2 * 1024 * 1024
MAX_JOURNAL_BYTES = 32 * 1024 * 1024
MAX_BOUND_EMU = 2_147_483_647
PRESENTATION_MODES = {'native', 'interactive', 'hybrid'}


def clean(value, limit, optional=False):
    if optional and value is None:
        return ''
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid outline text')
    value = ' '.join(value.split())
    if re.search(r'(?:/Users/|/private/|/tmp/|[A-Z]:\\)|(?i:bearer\s+\S+|sk-[\w-]{10,}|(?:password|api[_-]?key|secret)\s*[:=]\s*\S+)', value):
        raise ValueError('Outline must contain only public presentation content')
    return value


def validate_interaction(value):
    """Public metadata only: a scene ID and optional native-slide EMU rectangle."""
    if not isinstance(value, dict):
        raise ValueError('Outline interaction must be an object')
    scene = value.get('scene')
    if not isinstance(scene, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,95}', scene):
        raise ValueError('Outline interaction scene must be a scene ID')
    result = {'scene': scene, 'purpose': clean(value.get('purpose'), 1600)}
    if 'bounds' in value:
        bounds = value['bounds']
        if not isinstance(bounds, dict):
            raise ValueError('Outline interaction bounds must be an EMU rectangle')
        rectangle = {}
        for key in ('x', 'y', 'width', 'height'):
            number = bounds.get(key)
            if type(number) is not int or not (0 if key in ('x', 'y') else 1) <= number <= MAX_BOUND_EMU:
                raise ValueError('Invalid outline interaction EMU bounds')
            rectangle[key] = number
        if rectangle['x'] + rectangle['width'] > MAX_BOUND_EMU or rectangle['y'] + rectangle['height'] > MAX_BOUND_EMU:
            raise ValueError('Outline interaction bounds overflow')
        result['bounds'] = rectangle
    return result


def validate_outline(value, expected_pages=None):
    if not isinstance(value, dict):
        raise ValueError('Outline object required')
    slides = value.get('slides')
    if not isinstance(slides, list) or not 1 <= len(slides) <= MAX_SLIDES:
        raise ValueError(f'Outline must have 1–{MAX_SLIDES} pages')
    if expected_pages and len(slides) != expected_pages:
        raise ValueError('Outline page count differs from the requested count')
    result = {'title': clean(value.get('title'), 200), 'purpose': clean(value.get('purpose'), 1600)}
    if value.get('style'):
        result['style'] = clean(value['style'], 1200)
    result['slides'] = []
    ids = set()
    for item in slides:
        if not isinstance(item, dict):
            raise ValueError('Invalid outline page')
        ident = item.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('Outline page IDs must be unique and stable')
        ids.add(ident)
        page = {'id': ident, 'title': clean(item.get('title'), 200), 'summary': clean(item.get('summary'), 2400)}
        if item.get('section'):
            page['section'] = clean(item['section'], 200)
        if 'presentationMode' in item:
            mode = item['presentationMode']
            if not isinstance(mode, str) or mode not in PRESENTATION_MODES:
                raise ValueError('Invalid outline presentationMode')
            page['presentationMode'] = mode
        if 'interaction' in item:
            page['interaction'] = validate_interaction(item['interaction'])
        result['slides'].append(page)
    result['revision'] = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return result


def page_version(outline, slide):
    if not outline or not 1 <= slide <= len(outline['slides']):
        return None
    payload = {'style': outline.get('style', ''), 'page': outline['slides'][slide - 1]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
