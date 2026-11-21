"""Host tools for icon and open-licence image libraries.

Tasks have no network. These tools query fixed public APIs on the host and
return candidates with licences plus a preview sheet the model can see:

* pptx_icons: Iconify search over curated, permissively licensed sets. Chosen
  icons are converted to native editable path layers (assets/icons/*.json) for
  native_canvas.add_icon -- recolourable vectors, not raster stand-ins.
* pptx_open_images: Wikimedia Commons, The Met and the Art Institute of Chicago
  open-access search. Candidates carry direct media URLs, source pages and
  licences; the author imports a chosen one through web-media-proxy.py.

API responses and thumbnails are untrusted data. Only fixed HTTPS hosts are
contacted; nothing here grants the task network access.
"""
import base64
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode, urlsplit, quote

from icon_geometry import IconError, convert, render
from trajectory import record
from web_media import WebMediaBroker, local_proxy, proxy_args

ICON_TOOL = 'pptx_icons'
IMAGE_TOOL = 'pptx_open_images'
TOOLS = (ICON_TOOL, IMAGE_TOOL)
USER_AGENT = 'RickPPT-asset-search/1.0 (presentation authoring tool)'
API_HOSTS = {'api.iconify.design', 'commons.wikimedia.org', 'collectionapi.metmuseum.org', 'api.artic.edu', 'api.openverse.org'}
WIKIMEDIA_MEDIA = {'upload.wikimedia.org', 'thumb.wikimedia.org'}
THUMB_HOSTS = WIKIMEDIA_MEDIA | {'images.metmuseum.org', 'www.artic.edu', 'api.openverse.org'}
# Consistent, actively maintained sets. Licences are still checked live.
ICON_SETS = ('material-symbols', 'tabler', 'lucide', 'ph', 'fluent', 'carbon', 'mdi', 'ri', 'heroicons',
             'iconoir', 'mingcute', 'solar')
ICON_LICENSES = {'MIT', 'Apache-2.0', 'ISC', 'CC0-1.0', 'CC-BY-4.0'}
ICON_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*')
MAX_FETCH = 12
IMAGE_SOURCES = ('openverse', 'wikimedia', 'met', 'artic')
# Creative Commons licences that allow adaptation (cropping, overlays); ND is excluded.
OPENVERSE_LICENSES = 'by,by-sa,by-nc,by-nc-sa,cc0,pdm'


LOW_RESOLUTION = 1000  # long side in px; below this a picture blurs when shown large


def enabled(cfg):
    policy = cfg.get('asset_libraries', True)
    return policy is not False and not cfg.get('_customer_funded') and not (cfg.get('_model_profile') or {}).get('customer_funded')


def http_get(url, *, limit=4 * 1024 * 1024, hosts=API_HOSTS, timeout=25):
    """Bounded HTTPS GET to fixed hosts through the host's local proxy, if any."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in hosts or parts.username or parts.password:
        raise ValueError('Host not permitted for asset search')
    command = ['/usr/bin/curl', '-q', '--silent', '--show-error', '--fail', *proxy_args(local_proxy()),
               '--proto', '=https', '--max-redirs', '0', '--connect-timeout', '8', '--max-time', str(timeout),
               '--max-filesize', str(limit), '--retry', '1', '--user-agent', USER_AGENT, '--url', url]
    run = subprocess.run(command, capture_output=True, timeout=timeout + 10, env={'PATH': '/usr/bin:/bin'})
    if run.returncode or len(run.stdout) > limit:
        raise OSError('Asset library request failed')
    return run.stdout


def get_json(url):
    return json.loads(http_get(url))


def _text(value, limit=300):
    value = re.sub(r'<[^>]+>', ' ', str(value or ''))
    return re.sub(r'\s+', ' ', value).strip()[:limit]


def _https(value, hosts):
    if not isinstance(value, str):
        return None
    parts = urlsplit(value)
    if parts.scheme != 'https' or parts.hostname not in hosts or parts.username or parts.password:
        return None
    return parts._replace(query='', fragment='').geturl()


class AssetLibraries:
    def __init__(self, cfg, job, *, trajectory=None, reporter=None, fetch=None):
        self.cfg, self.job = cfg, Path(job).resolve(strict=True)
        self.trajectory, self.reporter = trajectory, reporter
        self.fetch = fetch or get_json
        self.licenses = {}

    def specs(self):
        if not enabled(self.cfg):
            return []
        return [
            {'type': 'function', 'name': ICON_TOOL,
             'description': ('Find crisp, consistent icons and place them as native editable vectors. action=search: short English '
                             'object nouns matched against icon names (e.g. "user", "chart", "headset", "gift"), optional sets to keep one family, '
                             'returns numbered candidates and a preview sheet you can see. action=fetch: up to 12 icon ids '
                             '(prefix:name) converted into assets/icons/*.json for native_canvas.add_icon or the native batch '
                             '"icon" op; recolour to the deck palette. Keep one set per deck. Licences are permissive; '
                             'attribution lines are returned when required.'),
             'inputSchema': {'type': 'object', 'additionalProperties': False, 'properties': {
                 'action': {'type': 'string', 'enum': ['search', 'fetch']},
                 'query': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                 'sets': {'type': 'array', 'items': {'type': 'string', 'enum': list(ICON_SETS)}, 'maxItems': 4},
                 'limit': {'type': 'integer', 'minimum': 4, 'maximum': 32},
                 'icons': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': MAX_FETCH}},
                 'required': ['action']}},
            {'type': 'function', 'name': IMAGE_TOOL,
             'description': ('Search open-licence image libraries directly: openverse (hundreds of millions of Creative Commons '
                             'photos from Flickr, Wikimedia and museums; best first choice for real places, objects and scenes), '
                             'wikimedia (Wikimedia Commons: history, places, '
                             'science, maps, artefacts, people), met (The Met open access, public domain artworks/objects), '
                             'artic (Art Institute of Chicago, public domain). Returns numbered candidates with title, creator, '
                             'licence, source page and a direct media_url, plus a preview sheet you can see. Import a chosen '
                             'image with web-media-proxy.py MEDIA_URL --source-page SOURCE_PAGE --purpose ..., inspect it and '
                             'credit creator/licence on the slide or in notes as the licence requires.'),
             'inputSchema': {'type': 'object', 'additionalProperties': False, 'properties': {
                 'query': {'type': 'string', 'minLength': 1, 'maxLength': 150},
                 'source': {'type': 'string', 'enum': list(IMAGE_SOURCES)},
                 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 12}},
                 'required': ['query', 'source']}},
        ]

    @staticmethod
    def reply(ok, value, images=()):
        return {'success': ok, 'contentItems': [{'type': 'inputText', 'text': json.dumps(value, ensure_ascii=False)}, *images]}

    def handle(self, params):
        tool, args = params.get('tool'), params.get('arguments')
        if tool not in TOOLS or params.get('namespace') is not None or not enabled(self.cfg) or not isinstance(args, dict):
            return self.reply(False, {'status': 'unavailable', 'reason': 'Asset library tool unavailable'})
        try:
            if tool == ICON_TOOL:
                if args.get('action') == 'search':
                    return self.icon_search(args)
                if args.get('action') == 'fetch':
                    return self.icon_fetch(args)
                return self.reply(False, {'status': 'invalid', 'reason': 'Use action search or fetch'})
            return self.image_search(args)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            record(self.trajectory, 'emit', 'asset_library.failure', {'tool': tool, 'error_type': type(error).__name__})
            return self.reply(False, {'status': 'unavailable', 'reason': type(error).__name__,
                                      'meaning': 'The library could not be reached or returned invalid data. Continue with other routes; do not loop on this request.'})

    # ---- icons -------------------------------------------------------------
    def icon_license(self, prefixes):
        missing = [p for p in prefixes if p not in self.licenses]
        if missing:
            data = self.fetch('https://api.iconify.design/collections?' + urlencode({'prefixes': ','.join(missing)}))
            for prefix in missing:
                info = data.get(prefix) if isinstance(data, dict) else None
                license = (info or {}).get('license') or {}
                author = (info or {}).get('author') or {}
                self.licenses[prefix] = {'set': _text((info or {}).get('name'), 80), 'license': _text(license.get('spdx'), 30),
                                         'license_title': _text(license.get('title'), 80),
                                         'license_url': _https(license.get('url'), {urlsplit(str(license.get('url'))).hostname}) if isinstance(license.get('url'), str) else None,
                                         'author': _text(author.get('name'), 80)}
        return {p: self.licenses[p] for p in prefixes}

    def icon_bodies(self, ids):
        by_prefix = {}
        for ident in ids:
            prefix, name = ident.split(':')
            by_prefix.setdefault(prefix, []).append(name)
        out = {}
        for prefix, names in by_prefix.items():
            data = self.fetch(f'https://api.iconify.design/{quote(prefix)}.json?' + urlencode({'icons': ','.join(names)}))
            icons = data.get('icons') if isinstance(data, dict) else None
            for name in names:
                body = (icons or {}).get(name)
                if not isinstance(body, dict):
                    continue
                width = body.get('width', data.get('width', 16)); height = body.get('height', data.get('height', 16))
                try:
                    out[prefix + ':' + name] = convert(body.get('body'), width, height)
                except IconError as error:
                    out[prefix + ':' + name] = error
        return out

    def icon_search(self, args):
        query = args.get('query')
        if not isinstance(query, str) or not query.strip() or len(query) > 100:
            return self.reply(False, {'status': 'invalid', 'reason': 'Give 1–100 characters of English keywords'})
        sets = args.get('sets') or list(ICON_SETS)
        if not isinstance(sets, list) or any(s not in ICON_SETS for s in sets):
            return self.reply(False, {'status': 'invalid', 'reason': 'Unknown icon set', 'sets': list(ICON_SETS)})
        limit = args.get('limit', 24)
        if type(limit) is not int or not 4 <= limit <= 32:
            return self.reply(False, {'status': 'invalid', 'reason': 'limit must be 4–32'})
        # Iconify matches icon names: a phrase often finds nothing, so fall back
        # to the hyphenated phrase and then each word.
        words = re.findall(r'[a-z0-9]+', query.lower())
        attempts = list(dict.fromkeys([query.strip(), '-'.join(words), *words]))[:5]
        ids = []
        for attempt in attempts:
            if not attempt:
                continue
            data = self.fetch('https://api.iconify.design/search?' + urlencode(
                {'query': attempt, 'limit': min(96, max(32, limit * 3)), 'prefixes': ','.join(sets)}))
            ids += [i for i in (data.get('icons') or []) if isinstance(i, str) and ICON_ID.fullmatch(i) and i not in ids]
            if len(ids) >= limit * 2:
                break
        licenses = self.icon_license(sorted({i.split(':')[0] for i in ids}))
        ids = [i for i in ids if licenses[i.split(':')[0]]['license'] in ICON_LICENSES]
        converted = self.icon_bodies(ids[:limit * 2])
        candidates = []
        for ident in ids:
            icon = converted.get(ident)
            if isinstance(icon, dict):
                candidates.append((ident, icon))
            if len(candidates) >= limit:
                break
        record(self.trajectory, 'emit', 'asset_library.icon_search', {'query': query, 'sets': sets, 'returned': len(candidates)})
        if not candidates:
            return self.reply(True, {'status': 'no_results', 'query': query,
                                     'meaning': 'No convertible icon matched. Try simpler English nouns or another set.'})
        sheet = self.icon_sheet(candidates)
        result = {'status': 'results', 'query': query,
                  'candidates': [{'n': n + 1, 'id': ident, 'set': licenses[ident.split(':')[0]]['set'],
                                  'license': licenses[ident.split(':')[0]]['license'],
                                  'style': 'filled' if any(l['fill'] for l in icon['layers']) else 'line'}
                                 for n, (ident, icon) in enumerate(candidates)],
                  'preview': 'The attached sheet numbers each candidate as drawn after native conversion.',
                  'next': 'Fetch chosen ids with action=fetch; prefer one set across the deck.'}
        return self.reply(True, result, [sheet])

    def icon_sheet(self, candidates, tile=112, columns=8):
        from PIL import Image, ImageDraw
        rows = (len(candidates) + columns - 1) // columns
        sheet = Image.new('RGB', (tile * columns, (tile + 18) * rows), 'white')
        draw = ImageDraw.Draw(sheet)
        for n, (ident, icon) in enumerate(candidates):
            x, y = (n % columns) * tile, (n // columns) * (tile + 18)
            sheet.paste(render(icon, tile - 16), (x + 8, y + 4))
            draw.text((x + 6, y + tile - 6), f'{n + 1} {ident}'[:20], fill=(90, 90, 90))
        buffer = io.BytesIO(); sheet.save(buffer, 'PNG')
        return {'type': 'inputImage', 'imageUrl': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()}

    def icon_fetch(self, args):
        ids = args.get('icons')
        if (not isinstance(ids, list) or not 1 <= len(ids) <= MAX_FETCH
                or any(not isinstance(i, str) or not ICON_ID.fullmatch(i) or i.split(':')[0] not in ICON_SETS for i in ids)):
            return self.reply(False, {'status': 'invalid', 'reason': f'Give 1–{MAX_FETCH} ids like tabler:user from the curated sets'})
        ids = list(dict.fromkeys(ids))
        licenses = self.icon_license(sorted({i.split(':')[0] for i in ids}))
        converted = self.icon_bodies([i for i in ids if licenses[i.split(':')[0]]['license'] in ICON_LICENSES])
        files, failures = [], []
        for ident in ids:
            icon = converted.get(ident)
            if not isinstance(icon, dict):
                failures.append({'id': ident, 'reason': str(icon) if isinstance(icon, IconError) else 'not found or licence not permitted'})
                continue
            prefix, name = ident.split(':')
            lic = licenses[prefix]
            stem = prefix + '--' + name
            document = {'schema': 'native-icon/v1', 'id': ident, **icon, 'set': lic['set'], 'license': lic['license'],
                        'license_title': lic['license_title'], 'author': lic['author'],
                        'source_page': f'https://icon-sets.iconify.design/{prefix}/{name}/'}
            data = json.dumps(document, ensure_ascii=False).encode()
            self.publish('assets/icons', stem + '.json', data)
            preview = io.BytesIO(); render(icon, 256).save(preview, 'PNG')
            self.publish('assets/icons', stem + '.png', preview.getvalue())
            attribution = (f'Icon "{name}" from {lic["set"]} by {lic["author"]}, {lic["license"]}'
                           if lic['license'] == 'CC-BY-4.0' else None)
            files.append({'id': ident, 'file': f'assets/icons/{stem}.json', 'preview': f'assets/icons/{stem}.png',
                          'sha256': hashlib.sha256(data).hexdigest(), 'license': lic['license'],
                          'layers': len(icon['layers']), 'attribution_required': attribution})
        record(self.trajectory, 'emit', 'asset_library.icon_fetch', {'files': files, 'failures': failures})
        return self.reply(bool(files), {'status': 'fetched' if files else 'unavailable', 'files': files, 'failures': failures,
            'use': ('native_canvas.add_icon(parts, slide, ICON_FILE, [x,y,w,h], ink="RRGGBB", name=...) or batch op '
                    '{"op":"icon","icon":ICON_FILE,"box":[...],"ink":"RRGGBB","name":...}. The icon keeps its aspect ratio '
                    'inside the box; line icons scale stroke width with size. Record id/licence in source-notes.md.')})

    def publish(self, folder, name, data):
        target = self.job
        for part in Path(folder).parts:
            target = target / part
            if target.is_symlink():
                raise ValueError('Asset folder symlink forbidden')
            target.mkdir(exist_ok=True)
        fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            WebMediaBroker.publish(fd, name, data)
        finally:
            os.close(fd)

    # ---- open images -------------------------------------------------------
    def image_search(self, args):
        query, source = args.get('query'), args.get('source')
        limit = args.get('limit', 8)
        if (not isinstance(query, str) or not query.strip() or len(query) > 150 or source not in IMAGE_SOURCES
                or type(limit) is not int or not 1 <= limit <= 12):
            return self.reply(False, {'status': 'invalid', 'reason': 'Give query (≤150 chars), source wikimedia/met/artic and limit 1–12'})
        query = query.strip()
        candidates = getattr(self, 'search_' + source)(query, limit)
        record(self.trajectory, 'emit', 'asset_library.image_search', {'source': source, 'query': query, 'returned': len(candidates)})
        if not candidates:
            return self.reply(True, {'status': 'no_results', 'source': source, 'query': query,
                                     'meaning': 'Nothing open-licensed matched. Try other keywords (English works best) or another source.'})
        for item in candidates:
            size = item.get('size') or []
            if len(size) == 2 and all(type(v) is int for v in size):
                item['low_resolution'] = max(size) < LOW_RESOLUTION
        images = []
        sheet = self.image_sheet(candidates)
        if sheet:
            images.append(sheet)
        for n, item in enumerate(candidates):
            item['n'] = n + 1
            item.pop('thumb', None)
        return self.reply(True, {'status': 'results', 'source': source, 'query': query, 'candidates': candidates,
            'preview': 'The attached sheet numbers candidate thumbnails with pixel size (red = low resolution, only for small placements); inspect the imported file before use.' if sheet else 'Previews unavailable; import a candidate to inspect it.',
            'import': 'python web-media-proxy.py MEDIA_URL --source-page SOURCE_PAGE --purpose "..."',
            'rights': 'Licence data comes from the library. Keep creator/licence/source with the asset; CC BY/BY-SA need visible credit.'},
            images)

    def search_wikimedia(self, query, limit):
        data = self.fetch('https://commons.wikimedia.org/w/api.php?' + urlencode({
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': query + ' filetype:bitmap',
            'gsrnamespace': 6, 'gsrlimit': limit, 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata',
            'iiurlwidth': 1600, 'iiextmetadatafilter': 'LicenseShortName|LicenseUrl|Artist|ObjectName|ImageDescription|Credit'}))
        pages = sorted(((data.get('query') or {}).get('pages') or {}).values(), key=lambda p: p.get('index', 0))
        out = []
        for page in pages:
            info = (page.get('imageinfo') or [{}])[0]
            meta = info.get('extmetadata') or {}
            value = lambda key: (meta.get(key) or {}).get('value')
            if info.get('mime') not in ('image/jpeg', 'image/png', 'image/gif', 'image/tiff', 'image/webp'):
                continue
            media = _https(info.get('thumburl') or info.get('url'), WIKIMEDIA_MEDIA)
            license = _text(value('LicenseShortName'), 60)
            if not media or not license:
                continue
            # Commons serves only standard thumbnail widths; 330px is one.
            if re.search(r'/\d+px-[^/]+$', media):
                thumb = re.sub(r'/\d+px-([^/]+)$', r'/330px-\1', media)
            else:
                match = re.match(r'https://upload\.wikimedia\.org/wikipedia/commons/([0-9a-f]/[0-9a-f]{2}/)([^/]+)$', media)
                thumb = (f'https://thumb.wikimedia.org/wikipedia/commons/thumb/{match[1]}{match[2]}/330px-{match[2]}'
                         + ('.jpg' if match[2].lower().endswith(('.tif', '.tiff')) else '')) if match else None
            out.append({'title': _text(value('ObjectName') or page.get('title', '').removeprefix('File:'), 200),
                        'creator': _text(value('Artist'), 200), 'license': license,
                        'license_url': _https(value('LicenseUrl'), {'creativecommons.org', 'commons.wikimedia.org', 'en.wikipedia.org'}),
                        'description': _text(value('ImageDescription'), 160),
                        'size': [info.get('width'), info.get('height')],
                        'source_page': 'https://commons.wikimedia.org/wiki/' + quote(page.get('title', '').replace(' ', '_'), safe=':/'),
                        'media_url': media, 'thumb': thumb})
        return out

    def search_openverse(self, query, limit):
        data = self.fetch('https://api.openverse.org/v1/images/?' + urlencode(
            {'q': query, 'page_size': min(20, limit), 'license': OPENVERSE_LICENSES, 'mature': 'false'}))
        out = []
        for item in data.get('results') or []:
            media = item.get('url')
            if not isinstance(media, str) or not media.startswith('https://') or not item.get('license'):
                continue
            version = item.get('license_version') or ''
            license = ('CC0' if item['license'] == 'cc0' else 'Public domain' if item['license'] == 'pdm'
                       else 'CC ' + item['license'].upper() + (' ' + version if version else ''))
            out.append({'title': _text(item.get('title'), 200), 'creator': _text(item.get('creator'), 200),
                        'license': license, 'license_url': item.get('license_url'),
                        'size': [item.get('width'), item.get('height')], 'provider': item.get('source'),
                        'source_page': item.get('foreign_landing_url'), 'media_url': media,
                        'thumb': _https(item.get('thumbnail'), {'api.openverse.org'})})
        return out

    def search_met(self, query, limit):
        data = self.fetch('https://collectionapi.metmuseum.org/public/collection/v1.1/search?' + urlencode(
            {'q': query, 'hasImages': 'true', 'limit': min(40, limit * 3)}))
        out = []
        for ident in (data.get('objectIDs') or [])[:limit * 3]:
            if type(ident) is not int:
                continue
            try:
                item = self.fetch(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{ident}')
            except (OSError, ValueError):
                continue
            media = _https(item.get('primaryImage') or item.get('primaryImageSmall'), {'images.metmuseum.org'})
            if not item.get('isPublicDomain') or not media:
                continue
            out.append({'title': _text(item.get('title'), 200),
                        'creator': _text(item.get('artistDisplayName') or item.get('culture'), 200),
                        'date': _text(item.get('objectDate'), 80), 'license': 'CC0 (Met Open Access, public domain)',
                        'license_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
                        'source_page': _https(item.get('objectURL'), {'www.metmuseum.org'}),
                        'media_url': media, 'thumb': _https(item.get('primaryImageSmall'), {'images.metmuseum.org'}) or media})
            if len(out) >= limit:
                break
        return out

    def search_artic(self, query, limit):
        data = self.fetch('https://api.artic.edu/api/v1/artworks/search?' + urlencode({
            'q': query, 'query[term][is_public_domain]': 'true', 'limit': limit,
            'fields': 'id,title,artist_display,image_id,date_display'}))
        out = []
        for item in data.get('data') or []:
            image = item.get('image_id')
            if not isinstance(image, str) or not re.fullmatch(r'[0-9a-f-]{36}', image) or type(item.get('id')) is not int:
                continue
            out.append({'title': _text(item.get('title'), 200), 'creator': _text(item.get('artist_display'), 200),
                        'date': _text(item.get('date_display'), 80), 'license': 'CC0 (Art Institute of Chicago, public domain)',
                        'license_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
                        'source_page': f'https://www.artic.edu/artworks/{item["id"]}',
                        'media_url': f'https://www.artic.edu/iiif/2/{image}/full/1686,/0/default.jpg',
                        'thumb': f'https://www.artic.edu/iiif/2/{image}/full/240,/0/default.jpg'})
        return out

    def image_sheet(self, candidates, tile=200, columns=4):
        from PIL import Image, ImageDraw
        # Size is known before decoding; check it here instead of lowering PIL's process-wide limit,
        # which every concurrent job in this worker shares.
        thumbs = []
        for item in candidates:
            thumb = None
            if item.get('thumb'):
                try:
                    data = http_get(item['thumb'], limit=1024 * 1024, hosts=THUMB_HOSTS, timeout=15)
                    with Image.open(io.BytesIO(data)) as opened:
                        if opened.format not in ('JPEG', 'PNG', 'GIF', 'WEBP') or opened.width * opened.height > 4_000_000:
                            raise ValueError('format or size')
                        opened.thumbnail((tile, tile)); thumb = opened.convert('RGB')
                except (OSError, ValueError, subprocess.SubprocessError, Image.DecompressionBombError):
                    thumb = None
            thumbs.append(thumb)
        if not any(thumbs):
            return None
        rows = (len(candidates) + columns - 1) // columns
        sheet = Image.new('RGB', (tile * columns, (tile + 20) * rows), 'white')
        draw = ImageDraw.Draw(sheet)
        for n, thumb in enumerate(thumbs):
            x, y = (n % columns) * tile, (n // columns) * (tile + 20)
            if thumb:
                sheet.paste(thumb, (x + (tile - thumb.width) // 2, y + (tile - thumb.height) // 2))
            else:
                draw.rectangle((x + 4, y + 4, x + tile - 4, y + tile - 4), outline=(200, 200, 200))
            size = item.get('size') or [None, None]
            label = str(n + 1) + (f'  {size[0]}x{size[1]}' if all(size) else '')
            draw.text((x + 6, y + tile + 4), label, fill=(200, 40, 40) if item.get('low_resolution') else (60, 60, 60))
        buffer = io.BytesIO(); sheet.save(buffer, 'JPEG', quality=82)
        return {'type': 'inputImage', 'imageUrl': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()}
